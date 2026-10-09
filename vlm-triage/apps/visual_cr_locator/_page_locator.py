from __future__ import absolute_import, annotations

import httpx
import logfire
import streamlit as st

from lib.services.visual_cr_locator_types import (
    LocatorConfig,
    LocatorScenarioResult,
    SampleImageInfo,
)
from lib.utils.streamlit_utils import st_paramed, st_report

from _shared import (
    LOCATOR_PAGE_URL,
    ROW_LABEL_MAP,
    _cached_annotation_meta,
    _cached_locate,
    _parse_locator_ids,
    _row_sort_key,
    st_config_fields,
)


# =============================================================================
# 图片网格
# =============================================================================


def render_image_grid(images: list[SampleImageInfo]):
    r"""按 window 分 tab，每 tab 内按 cr_index 排序的行 × sample_index 排序的列。"""
    if not images:
        st.info('无图片数据')
        return

    by_window: dict[str, list[SampleImageInfo]] = {}
    for img in images:
        by_window.setdefault(img.window_index, []).append(img)

    sorted_windows = sorted(by_window.items(), key=lambda kv: kv[0])
    tab_labels = [items[0].window_desc for _, items in sorted_windows]
    tabs = st.tabs(tab_labels)

    for tab, (_win_idx, cells) in zip(tabs, sorted_windows, strict=True):
        with tab:
            row_set = {(c.cr_index, c.cr_desc) for c in cells}
            rows = sorted(row_set, key=lambda r: _row_sort_key(r[0]))
            sample_indices = sorted({c.sample_index for c in cells})

            url_map: dict[tuple[int, str], str] = {}
            desc_map: dict[tuple[int, str], str] = {}
            for c in cells:
                url_map[(c.cr_index, c.sample_index)] = c.image_url
                desc_map[(c.cr_index, c.sample_index)] = c.sample_desc

            for cr_index, cr_desc in rows:
                label = ROW_LABEL_MAP.get(cr_index, f'CR {cr_index}')
                st.markdown(f'**{label}** — `{cr_desc}`')
                cols = st.columns(len(sample_indices))
                for ci, samp_idx in enumerate(sample_indices):
                    with cols[ci]:
                        img_url = url_map.get((cr_index, samp_idx))
                        if img_url:
                            st.image(
                                img_url,
                                caption=desc_map.get((cr_index, samp_idx), samp_idx),
                                use_container_width=True,
                            )
                        else:
                            st.write('—')


# =============================================================================
# 单个场景
# =============================================================================


def render_locator_scenario(scenario_id: str, result: LocatorScenarioResult):
    r"""渲染单个场景：metadata + image grid + excel links。"""
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f'场景: {scenario_id}')
        with col2:
            st.metric('CR 索引', result.cr_index if result.cr_index > 0 else '未定位')

        st.caption(f'commit: `{result.commit.commit.commit}`')
        st.caption(f'task: `{result.commit.task_id.id}`')
        st.caption(f'animation: `{result.commit.task_id.animation}`')

        if result.excels:
            for url in result.excels:
                st.link_button('⬇️ 下载 Excel', url, use_container_width=False)

        if result.images:
            render_image_grid(result.images)
        else:
            st.info('无图片 (return_images=False?)')

        with st.expander('Commit 详情'):
            st.json(result.commit.model_dump())


# =============================================================================
# 分析流程
# =============================================================================


def _run_locator(locator_id: int, config: LocatorConfig, render: bool = True):
    r"""单个 locator ID 的分析流程。"""

    locator_url = LOCATOR_PAGE_URL.format(locator_id=locator_id)

    try:
        meta = _cached_annotation_meta(locator_id, config)
        meta_cols = st.columns(3)
        meta_cols[0].markdown(
            f'[🔗 Locator 页面]({meta.locator_url})  \n[🔗 E2E Diff]({meta.diff_url})',
        )
        meta_cols[1].markdown(
            f'**Diff 类型:** {meta.diff_type}  \n**Metrics:** {", ".join(meta.metrics)}',
        )
        meta_cols[2].markdown(
            f'**Base:** `{meta.base_task_id}`  \n**Feature:** `{meta.feat_task_id}`',
        )

        with st.spinner('正在分析中，请稍候...'):
            response = _cached_locate(locator_id, config)

        if not render: return

        if response.message:
            st.warning(f'警告: {response.message}')

        if response.status == 'pending':
            st.warning('任务正在排队中...')
            return

        if not response.result:
            st.warning('未找到任何场景结果')
            return

        st.success(f'分析完成！共 {len(response.result)} 个场景')

        for scenario_id, scenario_result in response.result.items():
            render_locator_scenario(scenario_id, scenario_result)

    except httpx.HTTPError as exc:
        st.error(f'API 请求失败: {exc!r}')
        st.write(f'[🔗 Locator 页面]({locator_url})')
    except Exception as exc:
        logfire.exception('Unexpected error')
        st.error(f'发生错误: {exc!r}')
        st.write(f'[🔗 Locator 页面]({locator_url})')


# =============================================================================
# 页面入口
# =============================================================================

def page_locator():
    r"""CR Locator 可视化页面。"""
    st.title('🔍 CR Locator 可视化工具')

    with st.sidebar:
        st.header('⚙️ 配置')

        locator_ids_str: str = st_paramed(
            'locator_ids',
            st.text_input,
            'Locator IDs (逗号/空格/换行分隔)',
            value='4551391',
        )

        st.subheader('采样参数')
        main_cfg = st_config_fields(
            LocatorConfig,
            fields=[
                'use_vlm_animation',
                'max_windows',
                'window_duration',
                'window_offset',
                'sample_interval',
            ],
        )

        with st.expander('图像参数', expanded=False):
            image_cfg = st_config_fields(
                LocatorConfig,
                fields=['sample_wh', 'sample_xy', 'sample_xy_e2e'],
            )
            st.caption('若无 VLM 动画请尝试 1204 620 862 544')

        st.subheader('输出选项')
        output_cfg = st_config_fields(
            LocatorConfig,
            fields=['return_excels'],
        )

        run_button = st.button('🚀 运行分析', type='primary', use_container_width=True)

    if run_button:
        st.session_state['locator_ran'] = True

    if not st.session_state.get('locator_ran'):
        st.info('👈 请在左侧配置参数并点击「运行分析」')
        return

    locator_ids = _parse_locator_ids(locator_ids_str)
    if not locator_ids:
        st.error('请输入有效的 Locator ID')
        return

    locator_id = locator_ids[0]
    st.session_state.setdefault('locator_tab', str(locator_id))

    config = LocatorConfig(**main_cfg, **image_cfg, **output_cfg, return_images=True)

    with st.sidebar:
        if st.button('📝 Report'):
            locator_id = int(st.session_state['locator_tab'])
            st_report(
                {
                    'locator_id': locator_id,
                    'locator_ids': locator_ids,
                    'locator_url': LOCATOR_PAGE_URL.format(locator_id=locator_id),
                    'config': config.model_dump(),
                },
                type_options=('Error', 'Badcase', 'Goodcase'),
            )

    if len(locator_ids) == 1:
        _run_locator(locator_id, config)
    else:
        id_tabs = st.tabs(
            [str(lid) for lid in locator_ids],
            on_change='rerun',
            key='locator_tab',
        )
        for tab, lid in zip(id_tabs, locator_ids, strict=True):
            with tab:
                _run_locator(lid, config, render=tab.open)
