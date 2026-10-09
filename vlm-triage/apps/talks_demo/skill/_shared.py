"""Shared utilities for the Skill Demo stages."""

from __future__ import annotations

import asyncio
import dataclasses as dc
import os
import typing as tp
from pathlib import Path

import logfire
import streamlit as st
from openai import AsyncOpenAI

DEFAULT_API_BASE: str = os.environ['TRIAGE_MODEL_ROUTER_URL']
DEFAULT_MODEL: str = os.getenv('DEMO_MODEL', 'luban-0/model-1')
DEFAULT_API_KEY: str = os.getenv('DEMO_API_KEY', 'EMPTY')

EXAMPLE_COOPER_URL: str = 'https://cooper.didichuxing.com/docs2/document/2207460511730'

PROJECT_ROOT: str = os.environ.get(
    'PROJECT_ROOT',
    str(Path(__file__).resolve().parents[2]),
)

STAGES: list[str] = [
    '🧠 Stage 0: Plain LLM',
    '📚 Stage 1: RAG',
    '🔧 Stage 2: Tool Call',
    '🔌 Stage 3: MCP',
    '📜 Stage 4: Skill',
]

DEMO_QUESTIONS: list[str] = [
    '帮我总结这篇 Cooper 文档的核心结论',
    '列出文档中的关键设计决策和理由',
    '提取文档中所有 TODO 和待办事项',
]


@dc.dataclass
class DemoConfig:
    """Configuration for demo stages."""

    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    api_key: str = DEFAULT_API_KEY
    cooper_url: str = EXAMPLE_COOPER_URL

    @property
    def resource_id(self) -> int:
        """Extract resource_id from Cooper URL."""
        from lib.platforms.ep.cooper import parse_docs2_url

        return parse_docs2_url(self.cooper_url)


def get_openai_client(config: DemoConfig) -> AsyncOpenAI:
    """Create an AsyncOpenAI client from config."""
    return AsyncOpenAI(base_url=config.api_base, api_key=config.api_key)


def get_model(config: DemoConfig):
    """Create a pydantic-ai Model from config."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    with logfire.span(
        'get_model',
        model=config.model,
        api_base=config.api_base,
    ):
        provider = OpenAIProvider(openai_client=get_openai_client(config))
        model = OpenAIChatModel(config.model, provider=provider)
        logfire.info('model created: {model_name}', model_name=config.model)
        return model


def run_async(coro: tp.Coroutine[tp.Any, tp.Any, tp.Any]) -> tp.Any:
    """Run an async coroutine in Streamlit's sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def fetch_cooper_markdown(resource_id: int) -> str:
    """Export → normalize → markitdown, using Python API where possible.

    Steps:
      1. ``cooper.export_stream`` — download docx bytes via Cooper API
      2. ``cooper.normalize_docx_file`` — fix malformed styles.xml
      3. ``pixi exec markitdown`` — convert docx → markdown (CLI only)
    """
    import io

    from lib.platforms.ep.cooper import export_stream, normalize_docx_file

    with logfire.span('fetch_cooper_markdown', resource_id=resource_id):
        # 1. Export docx bytes
        with logfire.span('cooper.export_stream'):
            async with export_stream(resource_id) as resp:
                docx_bytes = await resp.aread()
            logfire.info(
                'export done: {n} bytes', n=len(docx_bytes),
            )

        # 2. Normalize docx in-memory
        with logfire.span('cooper.normalize_docx'):
            normalized = io.BytesIO()
            patched = normalize_docx_file(
                io.BytesIO(docx_bytes), normalized,
            )
            normalized_bytes = normalized.getvalue()
            logfire.info(
                'normalize done: patched {n} styles, {out} bytes',
                n=patched,
                out=len(normalized_bytes),
            )

        # 3. markitdown (not a Python library — CLI only)
        cmd = ['pixi', 'run', '--as-is', 'markitdown']
        with logfire.span('markitdown', cmd=cmd):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=PROJECT_ROOT,
            )
            stdout, stderr = await proc.communicate(
                input=normalized_bytes,
            )
            if proc.returncode != 0:
                msg = stderr.decode()
                logfire.error(
                    'markitdown failed: exit={rc} stderr={err}',
                    rc=proc.returncode,
                    err=msg,
                )
                raise RuntimeError(
                    f'markitdown failed (exit {proc.returncode}): {msg}',
                )
            md = stdout.decode('utf-8')
            logfire.info(
                'markitdown done: {n} chars', n=len(md),
            )
            return md


def render_sidebar_config() -> DemoConfig:
    """Render shared sidebar config and return DemoConfig."""
    config = DemoConfig()

    with st.sidebar:
        st.markdown('### ⚙️ 配置')
        config.api_base = st.text_input('API Base URL', value=DEFAULT_API_BASE)
        config.model = st.text_input('模型名称', value=DEFAULT_MODEL)
        config.cooper_url = st.text_input('Cooper 文档 URL', value=EXAMPLE_COOPER_URL)

        try:
            st.caption(f'`resource_id`: **{config.resource_id}**')
        except Exception:
            st.caption('`resource_id`: ⚠️ 无法解析')

        st.divider()
        st.markdown(
            '> **提示**：确保 `COOPER_USERNAME` 环境变量已配置。\n'
            '> Stage 2/4 需要网络访问 Cooper API。',
        )

    return config


def render_comparison_table():
    """Render the stage comparison table."""
    st.markdown(
        """
| 维度 | Stage 0 | Stage 1 (RAG) | Stage 2 (Tool) | Stage 3 (MCP) | Stage 4 (Skill) |
|:-----|:-------:|:-------------:|:--------------:|:-------------:|:---------------:|
| 获取文档 | ❌ 编造 | ⚠️ 被动检索 | ✅ 主动获取 | ✅ 动态发现 | ✅ 自主学习 |
| 工具来源 | — | 预建索引 | 硬编码 | MCP Server | SKILL.md |
| 添加能力 | — | 重建索引 | 改代码+部署 | 改 Server | 加 .md 文件 |
| 跨模型 | — | ❌ | ❌ 绑定框架 | ⚠️ 需 MCP 支持 | ✅ 复制即用 |
""",
    )


def render_message_log(messages: tp.Sequence[tp.Any], *, key: str = 'msg'):
    """Render pydantic-ai message history in a collapsible section.

    Displays user prompts, system prompts, assistant text, tool calls,
    tool returns, and thinking blocks with appropriate icons.
    """
    from pydantic_ai.messages import ModelRequest, ModelResponse

    with st.expander('💬 完整对话日志', expanded=False):
        for msg in messages:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    kind = part.part_kind
                    if kind == 'user-prompt':
                        c = part.content
                        content = c if isinstance(c, str) else str(c)
                        st.chat_message('user').markdown(content[:2000])
                    elif kind == 'system-prompt':
                        with st.chat_message('assistant', avatar='⚙️'):
                            st.caption('System Prompt')
                            st.markdown(part.content[:1000])
                    elif kind == 'tool-return':
                        with st.chat_message('assistant', avatar='📦'):
                            st.caption(f'Tool Return: `{part.tool_name}`  ({part.outcome})')
                            content_str = str(part.content)
                            if len(content_str) > 500:
                                content_str = content_str[:500] + '…'
                            st.code(content_str, language=None)
                    elif kind == 'retry-prompt':
                        with st.chat_message('assistant', avatar='🔄'):
                            st.caption('Retry')
                            st.text(str(getattr(part, 'content', '')))

            elif isinstance(msg, ModelResponse):
                for part in msg.parts:
                    kind = part.part_kind
                    if kind == 'text':
                        st.chat_message('assistant').markdown(part.content)
                    elif kind == 'tool-call':
                        with st.chat_message('assistant', avatar='🔧'):
                            args = part.args
                            if isinstance(args, dict):
                                import json
                                args = json.dumps(args, ensure_ascii=False, indent=2)
                            st.caption(f'Tool Call: `{part.tool_name}`')
                            if args:
                                st.code(str(args)[:1000], language='json')
                    elif kind == 'thinking':
                        with st.chat_message('assistant', avatar='💭'):
                            st.caption('Thinking')
                            st.text(part.content[:500])
