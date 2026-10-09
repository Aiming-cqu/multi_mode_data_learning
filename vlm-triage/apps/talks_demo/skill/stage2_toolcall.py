"""Stage 2: Tool Call — pydantic-ai Agent + 预定义工具。"""

from __future__ import annotations

import dataclasses as dc
import time
import typing as tp

import logfire
import streamlit as st
from pydantic_ai import Agent, RunContext

from _shared import (
    DemoConfig,
    DEMO_QUESTIONS,
    fetch_cooper_markdown,
    get_model,
    render_message_log,
    run_async,
)


@dc.dataclass
class CooperDeps:
    """Agent dependencies — credentials stay out of model context."""

    resource_id: int
    log: tp.Callable[[str], None]


def _build_agent(config: DemoConfig) -> Agent[CooperDeps, str]:
    """Build a pydantic-ai Agent with Cooper document tool."""
    agent = Agent(
        get_model(config),
        deps_type=CooperDeps,
        system_prompt=(
            '你是一个文档分析助手。用户会问你关于 Cooper 文档的问题。'
            '你有一个工具可以获取 Cooper 文档内容。'
            '请先使用工具获取文档，然后基于真实内容回答。'
        ),
    )

    @agent.tool
    async def read_cooper_document(
        ctx: RunContext[CooperDeps],
        url: tp.Optional[str] = None,
    ) -> str:
        """读取 Cooper 协作文档，返回 Markdown 格式内容。

        调用此工具来获取用户提到的 Cooper 文档的完整内容。
        url 参数可选，实际读取通过依赖注入的 resource_id 完成。

        Args:
            url: 文档 URL（可选，仅供模型传递，实际不使用）。
        """
        _ = url  # DI: 实际用 ctx.deps.resource_id
        ctx.deps.log('📥 正在从 Cooper 导出文档...')
        md_content = await fetch_cooper_markdown(ctx.deps.resource_id)
        ctx.deps.log(f'✅ 文档获取成功，共 {len(md_content)} 字符')
        if len(md_content) > 30000:
            md_content = md_content[:30000] + '\n\n...(文档已截断)...'
            ctx.deps.log('⚠️ 文档超过 30000 字符，已截断')
        return md_content

    return agent


def render(config: DemoConfig):
    """Render Stage 2 demo page."""
    st.header('🔧 Stage 2: Tool Call (pydantic-ai)')
    st.markdown(
        '> Agent 拥有**预定义的工具**：`read_cooper_document`。\n'
        '> 模型自主决定是否调用工具，参数由模型推理生成。',
    )

    question = st.selectbox('选择问题', DEMO_QUESTIONS, key='s2_question')
    custom_q = st.text_input('或自定义问题', key='s2_custom', placeholder='输入你的问题...')
    if custom_q:
        question = custom_q

    full_prompt = f'{question}\n\n文档链接: {config.cooper_url}'

    if not st.button('🚀 发送', key='s2_run'):
        with st.expander('ℹ️ 原理说明', expanded=True):
            st.code(
                '@agent.tool\n'
                'async def read_cooper_document(\n'
                '    ctx: RunContext[CooperDeps],\n'
                ') -> str:\n'
                '    """读取 Cooper 协作文档，返回 Markdown 格式内容。"""\n'
                '    md = await fetch_cooper_markdown(ctx.deps.resource_id)\n'
                '    return md',
                language='python',
            )
            st.markdown(
                '**工作流程**：\n'
                '```\n'
                '用户 → Agent → 模型决定调用工具 → 执行 Python 函数\n'
                '                                  → Cooper API\n'
                '                                  → normalize docx\n'
                '                                  → markitdown 转 Markdown\n'
                '       ← 基于真实内容的回答 ←────────┘\n'
                '```\n\n'
                '**关键**：`CooperDeps` 中的凭证通过**依赖注入**传递，\n'
                '不进入模型上下文，确保安全性。',
            )
        return

    log_container = st.container()
    logs: list[str] = []

    def log_fn(msg: str):
        logs.append(msg)

    with st.status('正在执行 Agent...', expanded=True) as status:
        st.write(f'📤 **Prompt**: {full_prompt[:200]}...')
        st.write(f'🤖 **Model**: `{config.model}`')
        st.write('🔧 **Tools**: `read_cooper_document`')

        agent = _build_agent(config)
        deps = CooperDeps(resource_id=config.resource_id, log=log_fn)

        t0 = time.monotonic()
        try:
            result = run_async(agent.run(full_prompt, deps=deps))
            elapsed = time.monotonic() - t0
            status.update(label=f'✅ Agent 完成 ({elapsed:.1f}s)', state='complete')
        except Exception as exc:
            logfire.error('stage2 failed', _exc_info=exc)
            status.update(label='❌ Agent 执行失败', state='error')
            st.exception(exc)
            return

    with log_container:
        st.markdown('### 📋 执行日志')
        for msg in logs:
            st.write(msg)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('### 📝 模型输出')
        st.markdown(result.output)
    with col2:
        st.markdown('### ✅ 判定')
        st.success('🟢 **准确**')
        st.markdown(
            '模型通过工具获取了\n**真实文档内容**，\n输出基于事实。',
        )

    with st.expander('🔍 Tool Call 详情'):
        st.markdown(
            '**Agent 内部流程**：\n\n'
            '1. 模型分析用户问题\n'
            '2. 决定调用 `read_cooper_document` 工具\n'
            '3. pydantic-ai 框架执行工具函数\n'
            '4. 工具通过 DI 获取 `resource_id`（不暴露给模型）\n'
            '5. Cooper API → normalize → markitdown\n'
            '6. 模型收到 Markdown 内容\n'
            '7. 基于真实内容生成回答\n\n'
            '**安全性**：`CooperDeps.resource_id` 通过 `RunContext` 注入，\n'
            '模型上下文中**看不到**凭证和 API 细节。',
        )

    with st.expander('⚠️ 局限性'):
        st.markdown(
            '**这个方案的问题**：\n\n'
            '1. `read_cooper_document` 是**人工预定义**的\n'
            '2. 每增加一个能力，需要写代码 + 部署\n'
            '3. 工具绑定了 pydantic-ai 框架，其他 Agent 框架不能直接复用\n'
            '4. 如果换了模型（比如从 GPT 换到 Claude），工具代码要一起迁移\n\n'
            '→ 进入 **Stage 4: Skill** 看看如何解决这些问题',
        )

    render_message_log(result.all_messages(), key='s2')
