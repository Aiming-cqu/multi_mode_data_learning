#!/bin/sh
''':'
exec pixi run -e prod -- serve-fe "$0" "$@"
# Streamlit 应用：CR Locator 工具集（可视化 + 标注）
':'''
#!/usr/bin/env -S pixi run -e prod -- serve-fe

from __future__ import absolute_import, annotations

import os
import logfire
import streamlit as st

NAME: str = os.environ.setdefault('OTEL_SERVICE_NAME', 'visual-cr-locator-fe')

from lib.utils.streamlit_utils import st_paramed_selectbox

from _page_annotation import page_annotation
from _page_locator import page_locator

_TASKS = ['🔍 CR Locator 可视化', '🏷️ CR Locator 标注']


def main():
    r"""主入口：任务选择路由。"""
    logfire.configure()

    st.set_page_config(
        page_title='CR Locator 工具集',
        page_icon='🔍',
        layout='wide',
    )

    with st.sidebar:
        task = st_paramed_selectbox('task', '🗂 任务', _TASKS)

    if task == _TASKS[0]:
        page_locator()
    else:
        page_annotation()


if __name__ == '__main__':
    logfire.configure()
    main()
