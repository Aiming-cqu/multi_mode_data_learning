#!/bin/sh
''':'
exec pixi run -e prod -- serve-fe "$0" "$@"
# Streamlit 应用：Skill Demo — 从 Plain LLM 到 Skill 系统的五阶段演示
':'''
#!/usr/bin/env -S pixi run -e prod -- serve-fe

from __future__ import annotations

import os

import logfire
import streamlit as st

NAME: str = os.environ.setdefault('OTEL_SERVICE_NAME', 'skill-demo')

from lib.utils.streamlit_utils import st_paramed_selectbox

from _shared import STAGES, render_comparison_table, render_sidebar_config
from stage0_plain import render as render_stage0
from stage1_rag import render as render_stage1
from stage2_toolcall import render as render_stage2
from stage3_mcp import render as render_stage3
from stage4_skill import render as render_stage4


def main():
    """主入口：Stage 选择路由。"""
    logfire.configure()
    logfire.instrument_pydantic_ai()
    logfire.instrument_httpx()

    st.set_page_config(
        page_title='Skill Demo — RAG to Skill',
        page_icon='🎓',
        layout='wide',
    )

    st.title('🎓 从 Plain LLM 到 Skill 系统')
    st.caption('AI Tech Talk Demo — 同一个问题，不同阶段的回答质量')

    config = render_sidebar_config()

    with st.sidebar:
        stage = st_paramed_selectbox('stage', '🗂 Stage 选择', STAGES)

    if stage == STAGES[0]:
        render_stage0(config)
    elif stage == STAGES[1]:
        render_stage1(config)
    elif stage == STAGES[2]:
        render_stage2(config)
    elif stage == STAGES[3]:
        render_stage3(config)
    elif stage == STAGES[4]:
        render_stage4(config)

    st.divider()

    with st.expander('📊 Stage 对比总览', expanded=False):
        render_comparison_table()

    with st.expander('📚 相关文档', expanded=False):
        st.markdown(
            '- [RAG → Skill 技术分享文档](../../docs/guides/ai-tech-talks/rag-to-skill.md)\n'
            '- [Cooper 文档读取技能](../../docs/skills/reading-cooper-documents/SKILL.md)\n'
            '- [pydantic-ai 文档](https://ai.pydantic.dev/)\n'
            '- [MCP 协议规范](https://modelcontextprotocol.io/specification)',
        )


if __name__ == '__main__':
    logfire.configure()
    main()
