from __future__ import absolute_import, annotations

import json, os, re, typing as tp

import httpx
import streamlit as st
from pydantic import BaseModel

from lib.services.visual_cr_locator_types import AnnotationInfo, LocatorConfig, LocatorResponse
from lib.utils.streamlit_utils import st_paramed


# =============================================================================
# 配置
# =============================================================================

API_BASE_URL: str = os.environ['TRIAGE_LOCATOR_API_URL']

api_client: httpx.Client = httpx.Client(base_url=API_BASE_URL, timeout=600.0)

LOCATOR_PAGE_URL: str = 'http://10.190.55.60:8000/pages/crlocator.html?id={locator_id}'

ROW_LABEL_MAP: dict[int, str] = {-1: 'base', -2: 'feature'}


# =============================================================================
# 辅助
# =============================================================================


def _row_sort_key(cr_index: int) -> tuple[int, int]:
    r"""base(-1) 在最前, feature(-2) 在最后, CR 按序号递增。"""
    if cr_index == -1:
        return (0, 0)
    if cr_index == -2:
        return (2, 0)
    return (1, cr_index)


def _parse_locator_ids(text: str) -> list[int]:
    r"""解析 locator ID 列表，支持逗号/空格/换行分隔。"""
    return [int(p) for p in re.split(r'[,\s]+', text) if p.isdigit()]


def st_config_fields(
    model_cls: type[BaseModel],
    *,
    fields: tp.Optional[list[str]] = None,
    excludes: frozenset[str] | set[str] = frozenset(),
    overrides: tp.Optional[dict[str, tp.Any]] = None,
    prefix: str = '',
) -> dict[str, tp.Any]:
    r"""从 Pydantic 模型自动生成 Streamlit 侧边栏表单控件。

    - `int` → number_input
    - `bool` → checkbox
    - `tuple[int, int]` → 两列 number_input（后缀 _wh 用 W/H，_xy 用 X/Y）

    默认值、类型、help 文本均从模型字段元数据自动抽取。
    所有控件通过 ``st_paramed`` 持久化到 URL query params。

    Args:
        model_cls: Pydantic 模型类。
        fields: 要渲染的字段名列表（保序）；None 表示渲染全部未排除字段。
        excludes: 跳过的字段名集合。
        overrides: 强制固定值（不渲染控件）的字段名 → 值映射。
        prefix: URL param key 的命名空间前缀。

    Returns:
        可直接解包为 ``model_cls(**result)`` 的字典。
    """
    defaults = model_cls()
    result: dict[str, tp.Any] = dict(overrides or {})
    target_fields = fields if fields is not None else list(model_cls.model_fields)

    for name in target_fields:
        if name in excludes or name in result:
            continue
        field_info = model_cls.model_fields[name]
        default = getattr(defaults, name)
        label = field_info.description or name
        param_key = f'{prefix}{name}' if prefix else name

        # Resolve inner type (unwrap Annotated[T, ...] → T)
        ann: type = field_info.annotation  # type: ignore[assignment]
        if tp.get_origin(ann) is tp.Annotated:
            ann = tp.get_args(ann)[0]
        inner_origin = tp.get_origin(ann)
        inner_args = tp.get_args(ann)

        if ann is bool:
            result[name] = bool(
                st_paramed(
                    param_key,
                    st.checkbox,
                    label,
                    value=default,
                    is_string_type=False,
                ),
            )
        elif ann is int:
            result[name] = int(
                st_paramed(
                    param_key,
                    st.number_input,
                    label,
                    value=default,
                    is_string_type=False,
                    step=1,
                ),
            )
        elif inner_origin is tuple and len(inner_args) == 2 and all(a is int for a in inner_args):
            sfx = ('W', 'H') if name.endswith('_wh') else ('X', 'Y')
            cols = st.columns(2)
            v0 = int(
                st_paramed(
                    f'{param_key}_0',
                    cols[0].number_input,
                    f'{label} {sfx[0]}',
                    value=default[0],
                    is_string_type=False,
                    step=1,
                ),
            )
            v1 = int(
                st_paramed(
                    f'{param_key}_1',
                    cols[1].number_input,
                    f'{label} {sfx[1]}',
                    value=default[1],
                    is_string_type=False,
                    step=1,
                ),
            )
            result[name] = (v0, v1)
        # else: unsupported type — skip silently

    return result


# =============================================================================
# 缓存包装
# =============================================================================


# @st.cache_data(max_entries=100, show_spinner=False)
def _cached_locate(locator_id: int, config: LocatorConfig) -> LocatorResponse:
    print(locator_id, config)
    r"""POST /locate → LocatorResponse。result 为 None 时抛出异常（不缓存）。"""
    resp = api_client.post(
        '/locate',
        params={'locator_id': locator_id},
        json=config.model_dump(),
        timeout=300.0,
    )
    resp.raise_for_status()
    data = LocatorResponse.model_validate(resp.json())
    if data.result is None:
        raise ValueError(
            f'Locator {locator_id} returned no result (status={data.status!r}): {data.message}',
        )
    return data


@st.cache_data(max_entries=100, show_spinner=False)
def _cached_annotation(locator_id: int, config: LocatorConfig) -> AnnotationInfo:
    r"""POST /annotation → AnnotationInfo。images 为 None 时抛出异常（不缓存）。"""
    resp = api_client.post(
        '/annotation',
        params={'locator_id': locator_id},
        json=config.model_dump(),
    )
    resp.raise_for_status()
    data = AnnotationInfo.model_validate(resp.json())
    if data.images is None:
        raise ValueError(f'Annotation {locator_id} returned no images')
    return data


@st.cache_data(max_entries=100, show_spinner=False)
def _cached_annotation_meta(locator_id: int, config: LocatorConfig) -> AnnotationInfo:
    r"""POST /annotation (meta only, no images/excels) → AnnotationInfo."""
    payload = config.model_copy(update=dict(return_images=False, return_excels=False)).model_dump()
    resp = api_client.post(
        '/annotation',
        params={'locator_id': locator_id},
        json=payload,
        timeout=60.0,
    )
    resp.raise_for_status()
    return AnnotationInfo.model_validate(resp.json())
