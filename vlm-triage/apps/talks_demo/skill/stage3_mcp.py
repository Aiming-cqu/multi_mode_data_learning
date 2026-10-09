"""Stage 3: MCP — 通过 MCP 协议动态发现和调用工具。"""

from __future__ import annotations

import time
import typing as tp

import logfire
import streamlit as st
from pydantic_ai import Agent

from _shared import DemoConfig, DEMO_QUESTIONS, get_model, render_message_log, run_async


def _mcp_available() -> bool:
    """Check if pydantic-ai MCP support is installed."""
    try:
        from pydantic_ai.mcp import MCPServerStdio  # noqa: F401

        return True
    except ImportError:
        return False


def _run_with_mcp(
    config: DemoConfig, prompt: str, log_fn: tp.Callable[[str], None],
) -> tuple[str, list[tp.Any]]:
    """Run the Agent with intranet-fetcher MCP server via stdio."""
    from pydantic_ai.mcp import MCPServerStdio

    server = MCPServerStdio(
        'npx',
        ['-y', '--registry=http://npm.intra.xiaojukeji.com/', '@didi/intranet-fetcher-mcp'],
    )

    agent = Agent(
        get_model(config),
        system_prompt=(
            '你是一个文档分析助手。你可以通过 MCP 工具获取网页内容。'
            '请先使用可用的工具获取用户提到的文档链接，'
            '然后基于真实内容回答。'
        ),
        toolsets=[server],
    )

    async def _run():
        async with agent:
            log_fn('🔌 MCP 连接已建立 (intranet-fetcher)')
            result = await agent.run(prompt)
            log_fn('✅ Agent 完成')
            return result.output, list(result.all_messages())

    return run_async(_run())


def _run_simulated(
    config: DemoConfig, prompt: str, log_fn: tp.Callable[[str], None],
) -> tuple[str, list[tp.Any]]:
    """Simulated MCP flow — shows the protocol, uses direct tool call underneath."""
    from _shared import fetch_cooper_markdown

    log_fn('🔌 [MCP] initialize → Cooper Document Server')
    log_fn('📋 [MCP] tools/list → 发现 1 个工具: cooper_read')
    log_fn('📝 [MCP] tools/list response:')
    log_fn('    {"name": "cooper_read", "description": "读取 Cooper 协作文档..."}')

    log_fn(f'🔨 [MCP] tools/call → cooper_read(url="{config.cooper_url}")')
    md_content = run_async(fetch_cooper_markdown(config.resource_id))
    log_fn(f'✅ [MCP] tool result: {len(md_content)} 字符')

    if len(md_content) > 30000:
        md_content = md_content[:30000] + '\n\n...(文档已截断)...'

    agent = Agent(
        get_model(config),
        system_prompt='你是一个文档分析助手。基于提供的文档内容回答用户问题。',
    )

    full_prompt = f'{prompt}\n\n## 文档内容\n\n{md_content}'
    result = run_async(agent.run(full_prompt))
    return result.output, list(result.all_messages())


def render(config: DemoConfig):
    """Render Stage 3 demo page."""
    st.header('🔌 Stage 3: MCP (Model Context Protocol)')
    st.markdown(
        '> 工具由 **MCP Server** 动态提供，Agent 通过协议**自动发现**。\n'
        '> 工具不再硬编码在 Agent 中，实现了解耦。',
    )

    has_mcp = _mcp_available()
    if not has_mcp:
        st.info(
            '💡 `mcp` 包未安装，使用模拟 MCP 流程演示。'
            '安装方法: `pixi add --pypi mcp --feature prod`',
        )

    question = st.selectbox('选择问题', DEMO_QUESTIONS, key='s3_question')
    custom_q = st.text_input(
        '或自定义问题',
        key='s3_custom',
        placeholder='输入你的问题...',
    )
    if custom_q:
        question = custom_q

    full_prompt = f'{question}\n\n文档链接: {config.cooper_url}'

    if not st.button('🚀 发送', key='s3_run'):
        with st.expander('ℹ️ 原理说明', expanded=True):
            st.markdown(
                '**MCP 架构**：\n\n'
                '```\n'
                'Agent (MCP Client)       intranet-fetcher Server\n'
                '       │                           │\n'
                '       ├── initialize ──────────────┤\n'
                '       ├── tools/list ──────────────┤\n'
                '       │   ← [fetch, ...]           │\n'
                '       │                           │\n'
                '       ├── tools/call ──────────────┤\n'
                '       │   (fetch, url=...)         │\n'
                '       │   ← 网页内容               │\n'
                '       │                           │\n'
                '```\n\n'
                '**关键区别**（vs Stage 2）：\n'
                '- Stage 2: 工具硬编码在 Agent 代码中\n'
                '- Stage 3: 工具由独立的 Server 提供，Agent 动态发现\n'
                '- 更换/升级工具 → 只改 Server，Agent 无需修改\n'
                '- 多个 Agent 可以共享同一个 MCP Server',
            )

            st.markdown('**intranet-fetcher MCP Server 配置**：')
            st.code(
                '"intranet-fetcher": {\n'
                '  "command": "npx",\n'
                '  "args": ["-y", "--registry=...", "@didi/intranet-fetcher-mcp"]\n'
                '}',
                language='json',
            )
        return

    log_container = st.container()
    logs: list[str] = []

    def log_fn(msg: str):
        logs.append(msg)

    with st.status('正在执行 MCP Agent...', expanded=True) as status:
        st.write(f'📤 **Prompt**: {full_prompt[:200]}...')
        st.write(f'🤖 **Model**: `{config.model}`')
        mode = 'MCP (真实)' if has_mcp else 'MCP (模拟)'
        st.write(f'🔌 **模式**: {mode}')

        t0 = time.monotonic()
        all_messages: list[tp.Any] = []
        try:
            if has_mcp:
                output, all_messages = _run_with_mcp(config, full_prompt, log_fn)
            else:
                output, all_messages = _run_simulated(config, full_prompt, log_fn)
            elapsed = time.monotonic() - t0
            status.update(
                label=f'✅ MCP Agent 完成 ({elapsed:.1f}s)',
                state='complete',
            )
        except Exception as exc:
            logfire.error('stage3 failed', _exc_info=exc)
            status.update(label='❌ MCP Agent 失败', state='error')
            st.exception(exc)
            return

    with log_container:
        st.markdown('### 📋 MCP 协议日志')
        for msg in logs:
            st.write(msg)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('### 📝 模型输出')
        st.markdown(output)
    with col2:
        st.markdown('### ✅ 判定')
        st.success('🟢 **准确 + 解耦**')
        st.markdown(
            '通过 MCP 协议，\n工具由 Server 提供，\nAgent 动态发现。\n\n**解耦 = 可替换**。',
        )

    with st.expander('🔍 MCP vs Tool Call'):
        st.markdown(
            '| | Stage 2 (Tool Call) | Stage 3 (MCP) |\n'
            '|:--|:--|:--|\n'
            '| 工具定义 | Agent 代码内 | 独立 Server |\n'
            '| 发现方式 | 编译时绑定 | 运行时发现 |\n'
            '| 更新工具 | 改 Agent + 部署 | 改 Server 即可 |\n'
            '| 共享工具 | 复制代码 | 连接同一 Server |\n'
            '| 协议 | 框架私有 | 开放标准 (JSON-RPC) |\n\n'
            '**但 MCP 仍有局限**：\n'
            '- 工具仍需人工开发和部署\n'
            '- 新能力需要写代码（Server 端）\n'
            '- 工具的创建者必须是开发者\n\n'
            '→ **Stage 4: Skill** 解决这个问题',
        )

    render_message_log(all_messages, key='s3')
