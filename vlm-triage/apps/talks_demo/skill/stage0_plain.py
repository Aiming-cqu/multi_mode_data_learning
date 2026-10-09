"""Stage 0: Plain LLM — 无工具，展示模型幻觉。"""

from __future__ import annotations

import logfire
import streamlit as st
from pydantic_ai import Agent

from _shared import DemoConfig, DEMO_QUESTIONS, get_model, render_message_log, run_async


def render(config: DemoConfig):
    """Render Stage 0 demo page."""
    st.header('🧠 Stage 0: Plain LLM')
    st.markdown(
        '> 直接向大模型提问关于 Cooper 文档的内容。\n'
        '> 模型**没有任何工具**，只能凭训练数据"编造"答案。',
    )

    question = st.selectbox('选择问题', DEMO_QUESTIONS, key='s0_question')
    custom_q = st.text_input('或自定义问题', key='s0_custom', placeholder='输入你的问题...')
    if custom_q:
        question = custom_q

    full_prompt = f'{question}\n\n文档链接: {config.cooper_url}'

    if not st.button('🚀 发送', key='s0_run'):
        with st.expander('ℹ️ 原理说明', expanded=True):
            st.markdown(
                '**Plain LLM 的问题**：\n\n'
                '1. 模型从未见过你的内部文档\n'
                '2. 模型无法访问网络获取文档\n'
                '3. 但模型会"自信地"生成看似合理的回答\n'
                '4. 这就是**幻觉 (Hallucination)**\n\n'
                '```\n'
                '用户 → 模型 → 编造的回答\n'
                '         ↑\n'
                '    没有真实数据\n'
                '```',
            )
        return

    with st.status('正在调用模型...', expanded=True) as status:
        st.write(f'📤 **Prompt**: {full_prompt[:200]}...')
        st.write(f'🤖 **Model**: `{config.model}`')
        st.write('⏳ 等待模型响应（无工具调用）...')

        agent = Agent(
            get_model(config),
            system_prompt=('你是一个文档助手。用户会问你关于内部文档的问题。直接回答用户的问题。'),
        )
        try:
            result = run_async(agent.run(full_prompt))
            status.update(label='✅ 模型响应完成', state='complete')
        except Exception as exc:
            logfire.error('stage0 failed', _exc_info=exc)
            status.update(label='❌ 调用失败', state='error')
            st.exception(exc)
            return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('### 📝 模型输出')
        st.markdown(result.output)
    with col2:
        st.markdown('### ⚠️ 判定')
        st.error('🔴 **幻觉**')
        st.markdown(
            '模型输出了看似合理的内容，\n'
            '但**完全是编造的**。\n\n'
            '它无法访问 Cooper 文档，\n'
            '所以所有具体细节都是虚构的。',
        )

    with st.expander('🔍 过程分析'):
        st.markdown(
            '**执行流程**：\n'
            '1. 用户输入包含 Cooper URL 的问题\n'
            '2. 模型没有工具可以获取文档\n'
            '3. 模型凭训练数据生成回答\n'
            '4. 回答中的具体细节是编造的\n\n'
            '**核心问题**：模型无法突破自身知识边界',
        )

    render_message_log(result.all_messages(), key='s0')
