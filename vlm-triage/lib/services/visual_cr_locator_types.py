from __future__ import absolute_import, annotations

import typing as tp, uuid

from pydantic import BaseModel, Field, ConfigDict

from ..platforms.tetools.cr_locator_types import (
    CRInfo,
    CRLocatorIdType,
    ScenarioIdType,
    TaskIdType,
    DiffType,
)
from ..utils.pydantic_compat import HttpUrlStr


class LocatorConfig(BaseModel):
    r"""
    Configuration parameters for visual CR locator sampling.

    Args:
        max_windows: Maximum number of event windows to sample.
        window_duration: Duration of each sampling window in milliseconds.
        window_offset: Time offset after event for window end in milliseconds.
        sample_interval: Sampling interval within window in milliseconds.
        sample_wh: Image sample width and height in pixels.
        sample_xy: Image sample center point in pixels.
        sample_xy_e2e: End-to-end image sample center point in pixels.
        return_images: Whether to return reference images in results.
        return_excels: Debug option to return Excel files.
    """

    max_windows: int = 3
    window_duration: tp.Annotated[
        int,
        Field(description='每个窗口采样时长，单位毫秒'),
    ] = 3010
    window_offset: tp.Annotated[
        int,
        Field(description='窗口结束于事件后的时间，单位毫秒'),
    ] = 1500
    sample_interval: tp.Annotated[
        int,
        Field(description='窗口内采样间隔，单位毫秒'),
    ] = 500
    sample_wh: tp.Annotated[
        tuple[int, int],
        Field(description='图像采样宽高，单位像素'),
    ] = (300, 400)
    sample_xy: tp.Annotated[
        tuple[int, int],
        Field(description='图像采样中心点，单位像素'),
    ] = (904, 528)
    sample_xy_e2e: tp.Annotated[
        tuple[int, int],
        Field(description='端到端图像采样中心点，单位像素'),
    ] = (904, 528)
    use_vlm_animation: tp.Annotated[
        bool,
        Field(description='使用视觉模型专用 layout 动画'),
    ] = True
    text: tp.Annotated[
        str,
        Field(description='VL embedding 模型的文本引导，非空时启用 VL 模型路由'),
    ] = ''
    return_images: tp.Annotated[
        bool,
        Field(description='返回结果或错误参考图像'),
    ] = False
    return_excels: tp.Annotated[
        bool,
        Field(description='返回调试或标注用 excel 表格'),
    ] = False

    model_config = ConfigDict(frozen=True)


class SampleImageInfo(BaseModel):
    r"""标注网格中的单个图片单元。"""
    # TODO: update annotation descriptions and examples

    cr_index: int
    cr_desc: str  # task + commit
    window_index: str
    window_desc: str  # window + time
    sample_index: str
    sample_desc: str  # sample + relative time
    image_url: HttpUrlStr


class AnnotationInfo(BaseModel):
    r"""标注网格数据：图片网格 + 关联链接 + 指标信息。"""

    locator_id: CRLocatorIdType
    locator_url: HttpUrlStr
    metrics: list[str]
    diff_type: DiffType
    diff_url: HttpUrlStr
    base_task_id: TaskIdType
    feat_task_id: TaskIdType

    images: tp.Optional[dict[ScenarioIdType, list[SampleImageInfo]]] = None
    excels: tp.Optional[dict[ScenarioIdType, list[HttpUrlStr]]] = None


class LocatorScenarioResult(BaseModel):
    r"""
    Visual CR locator result for a single scenario.

    Args:
        cr_index: Index of the identified inflection point in the CR list.
        commit: Commit information for the identified CR.
        images_url: Mapping of image names to URLs.
        excels_url: Mapping of Excel file names to URLs.
    """

    cr_indices: tp.Annotated[
        list[int],
        Field(description='定位拐点在 CR 列表中的序号'),
    ]
    commits: tp.Annotated[
        list[CRInfo],
        Field(description='定位拐点 CR 信息'),
    ]

    cr_index: tp.Annotated[
        int,
        Field(description='Top-1 拐点在 CR 列表中的序号（兼容旧接口）'),
    ]
    commit: tp.Annotated[
        CRInfo,
        Field(description='Top-1 拐点 CR 信息（兼容旧接口）'),
    ]

    images: tp.Optional[list[SampleImageInfo]] = None
    excels: tp.Optional[list[HttpUrlStr]] = None


LocatorResult: tp.TypeAlias = tp.Mapping[ScenarioIdType, LocatorScenarioResult]
r"""Type alias for complete visual CR locator results across all scenarios."""

TicketType: tp.TypeAlias = str
r"""Type alias for ticket identifiers."""


class LocatorResponse(BaseModel):
    r"""
    API response model for visual CR locator service.

    Args:
        ticket: Unique ticket identifier for tracking the request.
        status: Processing status (pending, running, success, error).
        message: Status message or error description.
        result: Optional locator results when processing is complete.
    """

    ticket: tp.Annotated[
        TicketType,
        Field(default_factory=(lambda: uuid.uuid4().hex[:12]), kw_only=True),
    ]
    status: tp.Literal["pending", "running", "success", "error"] = "pending"
    message: str = ''
    result: tp.Optional[LocatorResult] = None
