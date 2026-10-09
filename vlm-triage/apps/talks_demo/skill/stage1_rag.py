"""Stage 1: RAG — 检索增强生成，展示 RAG 的流水线和局限性。"""

from __future__ import annotations

import time
import typing as tp

import logfire
import streamlit as st
from pydantic_ai import Agent

from _shared import DemoConfig, DEMO_QUESTIONS, get_model, render_message_log, run_async

# 模拟向量库中预索引的文档片段
# 故意包含一些无关片段来展示检索偏差
_MOCK_CHUNKS: list[dict[str, tp.Any]] = [
    {
        'id': 'chunk_001',
        'source': '会议纪要_2024Q3.docx',
        'score': 0.82,
        'text': (
            '## Q3 路测问题总结\n\n'
            '本季度共发现 47 个路测异常，其中 12 个与感知模块相关...\n'
            '建议下季度重点优化 corner case 处理流程。'
        ),
    },
    {
        'id': 'chunk_002',
        'source': '技术方案_DPE优化.docx',
        'score': 0.78,
        'text': (
            '## DPE 参数调优方案\n\n'
            'DPE（Dynamic Path Evaluation）在高速弯道场景下存在延迟...\n'
            '方案一：增加预测窗口；方案二：引入模型辅助判断。'
        ),
    },
    {
        'id': 'chunk_003',
        'source': '周报_第42周.docx',
        'score': 0.71,
        'text': (
            '## 本周工作进展\n\n'
            '1. 完成了仿真环境 v2.3 的部署\n'
            '2. 修复了 3 个 CI 流水线问题\n'
            '3. TODO: 需要和算法组对齐下周计划'
        ),
    },
]


def render(config: DemoConfig):
    """Render Stage 1 demo page."""
    st.header('📚 Stage 1: RAG Pipeline')
    st.markdown(
        '> 预先索引文档 → Embedding 查询 → 检索相似片段 → 注入上下文。\n'
        '> 模型只能**被动接受**检索系统返回的内容。',
    )

    question = st.selectbox('选择问题', DEMO_QUESTIONS, key='s1_question')
    custom_q = st.text_input(
        '或自定义问题',
        key='s1_custom',
        placeholder='输入你的问题...',
    )
    if custom_q:
        question = custom_q

    if not st.button('🚀 发送', key='s1_run'):
        with st.expander('ℹ️ 原理说明', expanded=True):
            st.markdown(
                '**RAG 流水线**：\n\n'
                '```\n'
                '离线阶段：\n'
                '  文档集 → 分块 → Embedding → 向量数据库\n'
                '                   ↑\n'
                '              小模型（如 BGE-M3）\n'
                '\n'
                '在线阶段：\n'
                '  用户问题 → Embedding → 向量检索 → Top-K 片段\n'
                '                                      ↓\n'
                '                         Prompt + 检索片段 → LLM → 回答\n'
                '```\n\n'
                '**核心问题**：\n'
                '1. 检索质量取决于 Embedding 模型（通常比 LLM 小得多）\n'
                '2. 模型被动接受检索结果，无法主动"换个方式搜"\n'
                '3. 需要预先索引所有文档（新文档需重建索引）\n'
                '4. 分块策略影响结果质量（太大浪费上下文，太小丢信息）',
            )
        return

    # 模拟 RAG pipeline
    with st.status('正在执行 RAG 流水线...', expanded=True) as status:
        st.write('**Step 1/4**: 🔤 Query Embedding')
        st.write(f'  将问题转为向量: "{question[:50]}..."')
        st.write('  使用 Embedding 模型（模拟）...')
        time.sleep(0.5)  # 模拟延迟

        st.write('**Step 2/4**: 🔍 向量检索')
        st.write('  在预索引的文档库中搜索相似片段...')
        st.write('  共索引 3 个文档片段，返回 Top-3')
        time.sleep(0.3)

        st.write('**Step 3/4**: 📋 构建 Prompt')
        # 展示检索到的片段
        for chunk in _MOCK_CHUNKS:
            st.write(
                f'  - [{chunk["source"]}] score={chunk["score"]:.2f}',
            )
        time.sleep(0.2)

        st.write('**Step 4/4**: 🤖 LLM 生成回答')
        context = '\n\n---\n\n'.join(
            f'[来源: {c["source"]}, 相关度: {c["score"]}]\n{c["text"]}' for c in _MOCK_CHUNKS
        )
        rag_prompt = (
            f'基于以下检索到的参考文档回答用户问题。'
            f'只使用参考文档中的信息，不要编造。\n\n'
            f'## 参考文档\n\n{context}\n\n'
            f'## 用户问题\n\n{question}\n\n'
            f'文档链接: {config.cooper_url}'
        )

        agent = Agent(
            get_model(config),
            system_prompt='你是一个文档问答助手。只基于提供的参考文档回答。',
        )

        t0 = time.monotonic()
        try:
            result = run_async(agent.run(rag_prompt))
            elapsed = time.monotonic() - t0
            status.update(
                label=f'✅ RAG 流水线完成 ({elapsed:.1f}s)',
                state='complete',
            )
        except Exception as exc:
            logfire.error('stage1 failed', _exc_info=exc)
            status.update(label='❌ 调用失败', state='error')
            st.exception(exc)
            return

    # 结果展示
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('### 📝 模型输出')
        st.markdown(result.output)
    with col2:
        st.markdown('### ⚠️ 判定')
        st.warning('🟡 **部分准确**')
        st.markdown(
            '模型基于检索片段回答，\n'
            '但检索到的**可能不是**\n'
            '用户实际想要的文档。\n\n'
            '检索质量 = 回答质量的天花板。',
        )

    with st.expander('🔍 检索结果详情'):
        for chunk in _MOCK_CHUNKS:
            with st.container(border=True):
                st.markdown(
                    f'**{chunk["source"]}** (相关度: {chunk["score"]:.2f})',
                )
                st.markdown(chunk['text'])

    with st.expander('⚠️ RAG 的核心局限'):
        st.markdown(
            '### 被动 Context 注入\n\n'
            '```\n'
            'RAG = 被动的上下文注入器\n'
            '\n'
            '模型无法：\n'
            '  ❌ 主动要求"换个关键词搜"\n'
            '  ❌ 判断检索结果是否足够\n'
            '  ❌ 请求更多上下文\n'
            '  ❌ 访问未索引的文档\n'
            '\n'
            '模型被小 Embedding 模型"卡脖子"：\n'
            '  LLM 能力 >> Embedding 模型能力\n'
            '  但检索质量由 Embedding 模型决定\n'
            '```\n\n'
            '### 流水线复杂度\n\n'
            '| 组件 | 需要维护 |\n'
            '|:-----|:--------|\n'
            '| Embedding 模型 | 选型、部署、更新 |\n'
            '| 向量数据库 | 存储、索引、查询优化 |\n'
            '| 分块策略 | 块大小、重叠、边界处理 |\n'
            '| 检索器 | Top-K、重排序、过滤 |\n'
            '| Prompt 模板 | 上下文拼接、长度控制 |\n\n'
            '→ 进入 **Stage 2: Tool Call** 看模型如何主动获取信息',
        )

    render_message_log(result.all_messages(), key='s1')
