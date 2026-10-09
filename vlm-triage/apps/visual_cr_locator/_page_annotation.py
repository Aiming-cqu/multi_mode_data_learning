from __future__ import absolute_import, annotations

import hashlib, json, os, posixpath, re, typing as tp
import httpx
import logfire
import streamlit as st

from pathlib import Path
from urllib.parse import unquote, urlparse

from lib.services.visual_cr_locator_types import (
    AnnotationInfo,
    LocatorConfig,
    SampleImageInfo,
)
from lib.utils.streamlit_utils import st_paramed, st_report


from _shared import (
    LOCATOR_PAGE_URL,
    ROW_LABEL_MAP,
    _cached_annotation,
    _cached_annotation_meta,
    _parse_locator_ids,
    _row_sort_key,
    st_config_fields,
)


# =============================================================================
# 配置
# =============================================================================

NAME: str = os.environ.get('OTEL_SERVICE_NAME', 'visual-cr-locator-fe')
DATA_DIR: Path = Path(os.environ['TRIAGE_DATA_DIR'])

DIFF_TYPE_OPTIONS: list[str] = ['', 'P2F', 'F2P', 'P2P', 'F2F']
RANK_OPTIONS: list[str] = ['', '关键', '次要', '轻微']
SCENE_INVALID_OPTIONS: list[str] = [
    '',
    '其他（备注）',
    '端到端无效',
    '非链路拐点',
    '链路需展开',
    '采样问题（其他）',
    '采样问题（感知跳变）',
    '采样问题（时间范围）',
]
NON_ANNOTATABLE: frozenset[int] = frozenset({-1, -2})

_STICKY_TABS_CSS = """
<style>
[data-testid="stTabs"] > div:first-child > div:first-child {
    position: sticky;
    top: 3.5rem;
    z-index: 999;
}
[data-testid="stTabs"] [data-testid="stTabs"] > div:first-child > div:first-child {
    top: 6.3rem;
}
</style>
"""


# =============================================================================
# JSON 存储
# =============================================================================


def _annotation_dir() -> Path:
    r"""标注 JSON 存储目录: DATA_DIR/{OTEL_SERVICE_NAME}/annotations/"""
    # 去掉末尾的 /annotations，因为后面还会拼接
    return DATA_DIR / NAME / 'annotations'


def _sample_config_hash(config: LocatorConfig) -> str:
    r"""采样配置的短 hash，区分不同配置生成的标注。"""
    return hashlib.md5(
        config.model_copy(update={"return_excels": False}).model_dump_json().encode()
    ).hexdigest()[:12]


def _annotation_path(
    locator_id: int,
    scenario_id: str,
    config: LocatorConfig,
) -> Path:
    r"""单个场景的标注 JSON 文件路径。

    格式: DATA_DIR/{OTEL_SERVICE_NAME}/annotations/{locator_id}/locator_id={id}-scenario_id={sid}.{hash}.json
    """
    h = _sample_config_hash(config)
    return (
        _annotation_dir()
        / str(locator_id)
        / f'locator_id={locator_id}-scenario_id={scenario_id}.{h}.json'
    )


AnnKey = tuple[int, str, str]

_IMAGE_NAME_PATTERN = re.compile(
    r'^locator_id=(?P<locator_id>\d+)'
    r'-scenario_id=(?P<scenario_id>[^-]+)'
    r'-cr_index=(?P<cr_index>-?\d+)'
    r'-task_id=(?P<task_id>\d+)'
    r'(?:-commit=(?P<commit>[^-]+))?'
    r'-window_index=(?P<window_index>\d+)'
    r'-window_time=(?P<window_time>\d+)'
    r'-sample_index=(?P<sample_index>\d+)'
    r'-sample_time=(?P<sample_time>\d+)'
    r'\.jpg$',
)


def _annotation_files(locator_id: int) -> list[Path]:
    r"""按 locator_id 定位本地标注文件（兼容任意采样配置 hash）。

    文件名格式: locator_id={id}-scenario_id=*.json
    """
    base_dir = _annotation_dir()
    if not base_dir.exists():
        return []
    # 先在嵌套目录中查找: annotations/{locator_id}/
    locator_dir = base_dir / str(locator_id)
    if locator_dir.exists():
        return sorted(locator_dir.glob(f'locator_id={locator_id}-scenario_id=*.json'))
    # 兼容旧格式: annotations/locator_id={id}-scenario_id=*.json
    return sorted(base_dir.glob(f'locator_id={locator_id}-scenario_id=*.json'))


def _to_s3_data_path(path_or_url: str) -> str:
    r"""将 URL/绝对路径/相对路径统一为 data 前缀路径。"""
    source = path_or_url.strip()
    if not source:
        return ''
    parsed = urlparse(source)
    path = unquote(parsed.path if parsed.scheme else source)
    data_anchor = f'/{DATA_DIR.name}/'
    if data_anchor in path:
        suffix = path.split(data_anchor, maxsplit=1)[1].lstrip('/')
        return f'{DATA_DIR.name}/{suffix}'
    path = path.lstrip('/')
    if path.startswith(f'{DATA_DIR.name}/'):
        return path
    return path


def _infer_s3_prefix(image_paths: list[str]) -> str:
    r"""根据图片路径推断共同的 s3 前缀目录。"""
    if not image_paths:
        return ''
    if len(image_paths) == 1:
        return posixpath.dirname(image_paths[0])
    common = posixpath.commonpath(image_paths)
    if common.endswith('.jpg'):
        return posixpath.dirname(common)
    return common


def _normalize_annotation_payload(path: Path, data: dict) -> dict:
    r"""回填已标注数据中的 image_s3_prefix，并归一化图片路径。"""
    changed = False
    image_paths = list[str]()
    for rec in data.get('annotations', []):
        if not isinstance(rec, dict):
            continue
        if not isinstance((image_url := rec.get('image_url')), str):
            continue
        normalized = _to_s3_data_path(image_url)
        if not normalized:
            continue
        image_paths.append(normalized)
        if normalized != image_url:
            rec['image_url'] = normalized
            changed = True

    raw_prefix = data.get('image_prefix', '')
    prefix = _to_s3_data_path(raw_prefix) if isinstance(raw_prefix, str) else ''
    if not prefix:
        prefix = _infer_s3_prefix(image_paths)
    if prefix and data.get('image_prefix') != prefix:
        data['image_prefix'] = prefix
        changed = True

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return data


def _load_annotation_json(path: Path) -> tp.Optional[dict]:
    r"""读取并规范化标注 JSON。"""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        logfire.warning('failed to read annotation file {path}: {exc!r}', path=path, exc=exc)
        return None
    if not isinstance(data, dict):
        logfire.warning('annotation file is not an object: {path}', path=path)
        return None
    return _normalize_annotation_payload(path, data)


def _resolve_s3_prefix_dir(image_prefix: str) -> Path:
    r"""将 data 前缀转换为本地挂载目录。"""
    prefix = image_prefix.strip().lstrip('/')
    if not prefix:
        return DATA_DIR
    if image_prefix.startswith('/'):
        return Path(image_prefix)
    if prefix.startswith(f'{DATA_DIR.name}/'):
        return DATA_DIR.parent / prefix
    return DATA_DIR / prefix


import streamlit as st


@st.cache_data(persist=True, show_spinner=False)
def _load_image_data(image_path: str) -> bytes:
    r"""缓存图片数据，避免重复加载"""
    with open(image_path, 'rb') as f:
        return f.read()


def _build_sample_image(image_path: Path) -> tp.Optional[tuple[str, AnnKey, SampleImageInfo]]:
    r"""从语义化图片文件名还原 SampleImageInfo。"""
    match = _IMAGE_NAME_PATTERN.match(image_path.name)
    if not match:
        return None
    scenario_id = match.group('scenario_id')
    cr_index = int(match.group('cr_index'))
    task_id = match.group('task_id')
    commit = match.group('commit') or ''
    window_index = match.group('window_index')
    sample_index = match.group('sample_index')
    window_time = int(match.group('window_time'))
    sample_time = int(match.group('sample_time'))
    sample_rel_time = sample_time - window_time

    # 预加载图片数据
    image_data = _load_image_data(str(image_path))

    sample = SampleImageInfo.model_construct(
        cr_index=cr_index,
        cr_desc=f'{task_id} / {commit}' if commit else f'{task_id}',
        window_index=window_index,
        window_desc=f'W{window_index} @ {window_time}ms',
        sample_index=sample_index,
        sample_desc=f'S{sample_index} @ {sample_rel_time:+d}ms',
        image_url=str(image_path),
        image_data=image_data,
    )
    key: AnnKey = (cr_index, window_index, sample_index)
    return scenario_id, key, sample


def _load_images_from_saved_s3(
    locator_id: int,
) -> dict[str, list[SampleImageInfo]]:
    r"""从已标注 JSON 记录的 s3 前缀恢复 locator 的全部图片。"""
    prefixes = {
        data['image_prefix']
        for file_path in _annotation_files(locator_id)
        if (data := _load_annotation_json(file_path))
        and isinstance(data.get('image_prefix'), str)
        and data['image_prefix']
    }
    if not prefixes:
        return {}

    images_by_scenario = dict[str, dict[AnnKey, SampleImageInfo]]()
    for image_prefix in sorted(prefixes):
        image_dir = _resolve_s3_prefix_dir(image_prefix)
        if not image_dir.exists():
            logfire.warning(
                'annotation image prefix not found on disk: {image_dir}',
                image_dir=image_dir,
            )
            continue
        pattern = f'locator_id={locator_id}-scenario_id=*-cr_index=*-task_id=*.jpg'
        # 优化图片加载：批量处理文件
        image_paths = sorted(image_dir.glob(pattern))
        if not image_paths:
            continue

        # 使用批量处理提高效率
        for image_path in image_paths:
            parsed = _build_sample_image(image_path)
            if not parsed:
                continue
            scenario_id, key, sample = parsed
            images_by_scenario.setdefault(scenario_id, {})[key] = sample

        # 批量加载后添加日志
        logfire.debug(f'Loaded {len(image_paths)} images from {image_dir}')

    if not images_by_scenario:
        return {}
    return {
        scenario_id: sorted(
            cells.values(),
            key=lambda c: (_row_sort_key(c.cr_index), c.window_index, c.sample_index),
        )
        for scenario_id, cells in images_by_scenario.items()
    }


def load_annotations(
    locator_id: int,
    scenario_id: str,
    config: LocatorConfig,
) -> tuple[dict[AnnKey, str], dict[AnnKey, str], str, str]:
    r"""加载已有标注。加载或解析失败时静默返回空结构。

    Returns:
        (annotations, ranks, comment, scene_invalid)
        annotations: {(cr_index, window_index, sample_index): diff_type}
        ranks:       {(cr_index, window_index, sample_index): rank}
        comment:     场景级备注
        scene_invalid: 场景无效标记
    """
    path = _annotation_path(locator_id, scenario_id, config)
    if not path.exists():
        return {}, {}, '', ''
    if not (data := _load_annotation_json(path)):
        return {}, {}, '', ''
    annotations: dict[AnnKey, str] = {}
    ranks: dict[AnnKey, str] = {}
    for rec in data.get('annotations', []):
        if not isinstance(rec, dict):
            continue
        cr_index_raw = rec.get('cr_index')
        window_index_raw = rec.get('window_index')
        sample_index_raw = rec.get('sample_index')
        if window_index_raw is None or sample_index_raw is None:
            continue
        try:
            cr_index = int(cr_index_raw)
        except (TypeError, ValueError):
            continue
        key: AnnKey = (
            cr_index,
            str(window_index_raw),
            str(sample_index_raw),
        )
        annotations[key] = str(rec.get('diff_type', ''))
        if rank := rec.get('rank'):
            ranks[key] = str(rank)
    return annotations, ranks, data.get('comment', ''), data.get('scene_invalid', '')


def save_annotations(
    locator_id: int,
    scenario_id: str,
    config: LocatorConfig,
    annotations: dict[AnnKey, str],
    ranks: dict[AnnKey, str],
    *,
    comment: str = '',
    scene_invalid: str = '',
    info: AnnotationInfo,
    cells: list[SampleImageInfo],
) -> Path:
    r"""保存标注结果为 JSON，同时写入 AnnotationInfo 和 SampleImageInfo 元数据。"""
    path = _annotation_path(locator_id, scenario_id, config)
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {'locator_id': locator_id, 'scenario_id': scenario_id}

    data['base_task_id'] = info.base_task_id
    data['feat_task_id'] = info.feat_task_id
    data['diff_type'] = info.diff_type
    data['metrics'] = info.metrics
    data['locator_url'] = info.locator_url
    data['diff_url'] = info.diff_url
    data['image_prefix'] = _infer_s3_prefix(
        [s3_path for c in cells if (s3_path := _to_s3_data_path(str(c.image_url)))],
    )

    if comment:
        data['comment'] = comment
    if scene_invalid:
        data['scene_invalid'] = scene_invalid

    cell_lookup: dict[AnnKey, SampleImageInfo] = {}
    for c in cells:
        cell_lookup[(c.cr_index, c.window_index, c.sample_index)] = c

    ann_list = []
    for key, value in sorted(annotations.items()):
        if not value:
            continue
        cell = cell_lookup[key]
        entry = cell.model_dump()
        if s3_path := _to_s3_data_path(str(cell.image_url)):
            entry['image_url'] = s3_path
        entry['diff_type'] = value
        rank = ranks.get(key, '')
        if rank:
            entry['rank'] = rank
        ann_list.append(entry)

    data['annotations'] = ann_list
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    logfire.info('saved annotations to {path}', path=path)
    return path


# =============================================================================
# UI
# =============================================================================


def render_annotation_scenario(
    locator_id: int,
    scenario_id: str,
    cells: list[SampleImageInfo],
    config: LocatorConfig,
    info: AnnotationInfo,
):
    r"""渲染单个场景的图片网格（按 window 分 tab），每张图下方一个标注下拉。"""
    if not cells:
        st.warning(f'场景 {scenario_id} 无图片数据')
        return

    existing, existing_ranks, existing_comment, existing_invalid = load_annotations(
        locator_id,
        scenario_id,
        config,
    )

    with st.container(border=True):
        st.subheader(f'场景: {scenario_id}')
        ann_state: dict[AnnKey, str] = {}
        rank_state: dict[AnnKey, str] = {}

        by_window: dict[str, list[SampleImageInfo]] = {}
        for c in cells:
            by_window.setdefault(c.window_index, []).append(c)

        sorted_windows = sorted(by_window.items(), key=lambda kv: kv[0])
        tab_labels = [items[0].window_desc for _, items in sorted_windows]
        tabs = st.tabs(tab_labels)

        for tab, (win_idx, win_cells) in zip(tabs, sorted_windows, strict=True):
            with tab:
                row_set = {(c.cr_index, c.cr_desc) for c in win_cells}
                rows = sorted(row_set, key=lambda r: _row_sort_key(r[0]))
                sample_indices = sorted({c.sample_index for c in win_cells})

                url_map: dict[tuple[int, str], str] = {}
                desc_map: dict[tuple[int, str], str] = {}
                for c in win_cells:
                    url_map[(c.cr_index, c.sample_index)] = c.image_url
                    desc_map[(c.cr_index, c.sample_index)] = c.sample_desc

                for cr_index, cr_desc in rows:
                    label = ROW_LABEL_MAP.get(cr_index, f'CR {cr_index}')
                    if cr_index not in NON_ANNOTATABLE:
                        has_annotation = any(
                            existing.get((cr_index, win_idx, samp_idx))
                            or st.session_state.get(
                                f'ann_{scenario_id}_{cr_index}_{win_idx}_{samp_idx}',
                            )
                            for samp_idx in sample_indices
                        )
                    else:
                        has_annotation = False
                    if has_annotation:
                        highlight_style = (
                            'background:#d4edda;padding:4px 10px;border-radius:4px;margin:2px 0'
                        )
                        st.markdown(
                            f'<div style="{highlight_style}">'
                            f'<strong>{label}</strong> — <code>{cr_desc}</code></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f'**{label}** — `{cr_desc}`')

                    img_cols = st.columns(len(sample_indices))
                    for ci, samp_idx in enumerate(sample_indices):
                        cell_key: AnnKey = (cr_index, win_idx, samp_idx)
                        with img_cols[ci]:
                            img_url = url_map.get((cr_index, samp_idx))
                            if img_url:
                                st.image(
                                    img_url,
                                    caption=desc_map.get((cr_index, samp_idx), samp_idx),
                                    use_container_width=True,
                                )
                            else:
                                st.write('—')
                            if cr_index not in NON_ANNOTATABLE:
                                default_idx = 0
                                existing_val = existing.get(cell_key, '')
                                if existing_val in DIFF_TYPE_OPTIONS:
                                    default_idx = DIFF_TYPE_OPTIONS.index(existing_val)
                                ann_state[cell_key] = st.selectbox(
                                    f'{label} S{samp_idx}',
                                    options=DIFF_TYPE_OPTIONS,
                                    index=default_idx,
                                    label_visibility='collapsed',
                                    key=f'ann_{scenario_id}_{cr_index}_{win_idx}_{samp_idx}',
                                )
                                existing_rank = existing_ranks.get(cell_key, '')
                                rank_idx = (
                                    RANK_OPTIONS.index(existing_rank)
                                    if existing_rank in RANK_OPTIONS
                                    else 0
                                )
                                rank_state[cell_key] = st.selectbox(
                                    f'{label} S{samp_idx} rank',
                                    options=RANK_OPTIONS,
                                    index=rank_idx,
                                    label_visibility='collapsed',
                                    key=f'rank_{scenario_id}_{cr_index}_{win_idx}_{samp_idx}',
                                    help='留空=按关键处理（默认）；关键=关键拐点；次要=行为变化但不影响指标；轻微=噪声级别难以察觉',
                                )

        col_invalid, col_comment = st.columns([1, 2])
        with col_invalid:
            invalid_idx = 0
            if existing_invalid in SCENE_INVALID_OPTIONS:
                invalid_idx = SCENE_INVALID_OPTIONS.index(existing_invalid)
            scene_invalid = st.selectbox(
                '场景无效',
                options=SCENE_INVALID_OPTIONS,
                index=invalid_idx,
                key=f'invalid_{scenario_id}',
                help='标记场景为无效（可选）',
            )

        with col_comment:
            scene_comment = st.text_area(
                '场景备注',
                value=existing_comment,
                key=f'comment_{scenario_id}',
                placeholder='可选：场景级的备注或说明…',
            )

        if st.button(f'💾 保存标注 ({scenario_id})', key=f'save_{scenario_id}'):
            path = save_annotations(
                locator_id,
                scenario_id,
                config,
                ann_state,
                rank_state,
                comment=scene_comment,
                scene_invalid=scene_invalid,
                info=info,
                cells=cells,
            )
            st.success(f'已保存至 {path}')


def _render_locator_tab(
    locator_id: int,
    info: AnnotationInfo,
    config: LocatorConfig,
):
    r"""渲染单个 locator_id 的完整标注内容（元信息 + 场景列表）。"""
    meta_cols = st.columns(3)
    meta_cols[0].markdown(f'[🔗 Locator 页面]({info.locator_url})')
    meta_cols[1].markdown(f'[🔗 E2E Diff]({info.diff_url})')
    meta_cols[2].markdown(f'**{info.diff_type}** · Metrics: {", ".join(info.metrics)}')
    st.caption(f'Base: `{info.base_task_id}` · Feature: `{info.feat_task_id}`')

    if info.excels:
        with st.expander('📊 Excel 报告'):
            for scenario_id, urls in info.excels.items():
                st.markdown(f'**{scenario_id}**')
                for url in urls:
                    st.link_button('⬇️ 下载', url, use_container_width=True)

    if not info.images:
        st.warning('无图片数据')
        return

    for scenario_id, cells in info.images.items():
        render_annotation_scenario(locator_id, scenario_id, cells, config, info=info)


# =============================================================================
# 页面入口
# =============================================================================


def _load_and_render_tab(lid: int, config: LocatorConfig, render: bool = True):
    r"""加载单个 locator_id 的标注数据并渲染（含 spinner）。"""
    locator_url = LOCATOR_PAGE_URL.format(locator_id=lid)
    try:
        with st.spinner('正在获取标注网格…'):
            from_saved_s3 = False
            if images := _load_images_from_saved_s3(lid):
                meta = _cached_annotation_meta(lid)
                data = meta.model_copy(update={'images': images})
                from_saved_s3 = True
            else:
                data = _cached_annotation(lid, config)

        if not render:
            return

        if from_saved_s3:
            st.info('已从历史标注 S3 路径恢复图片，未重新请求图片 API。')
        _render_locator_tab(lid, data, config)
    except httpx.HTTPError as exc:
        logfire.exception('fetch annotation error', lid=lid)
        st.error(f'API 请求失败: {exc!r}')
        st.write(f'[🔗 Locator 页面]({locator_url})')
    except Exception as exc:
        logfire.exception('fetch annotation error', lid=lid)
        st.error(f'发生错误: {exc!r}')
        st.write(f'[🔗 Locator 页面]({locator_url})')


def page_annotation():
    r"""CR 标注页面。"""
    st.markdown(_STICKY_TABS_CSS, unsafe_allow_html=True)
    st.title('🏷️ CR 图片标注工具')

    with st.sidebar:
        locator_ids_str: str = st_paramed(
            'locator_ids',
            st.text_input,
            'Locator IDs (逗号/空格/换行分隔)',
            value='4551391',
        )
        output_cfg = st_config_fields(
            LocatorConfig,
            fields=['return_excels'],
        )
        load_button = st.button('🔄 加载标注', type='primary', use_container_width=True)

    if load_button:
        st.session_state['ann_loaded'] = True

    if not st.session_state.get('ann_loaded'):
        st.info('👈 请在左侧点击「加载标注」')
        return

    locator_ids = _parse_locator_ids(locator_ids_str)
    if not locator_ids:
        st.info('请在侧边栏输入 Locator ID')
        return

    locator_id = locator_ids[0]
    st.session_state.setdefault('locator_tab', str(locator_id))

    config = LocatorConfig(return_images=True, **output_cfg)

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
        _load_and_render_tab(locator_id, config)
    else:
        tabs = st.tabs(
            [str(lid) for lid in locator_ids],
            on_change='rerun',
            key='locator_tab',
        )
        for tab, lid in zip(tabs, locator_ids, strict=True):
            with tab:
                _load_and_render_tab(lid, config, render=tab.open)
