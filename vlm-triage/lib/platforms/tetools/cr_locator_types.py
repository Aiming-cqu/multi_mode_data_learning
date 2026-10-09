from __future__ import absolute_import, annotations

import typing as tp

from pydantic import BaseModel, ConfigDict, Field

from ...utils.pydantic_compat import HttpUrlStr


DiffType: tp.TypeAlias = tp.Literal["F2P", "P2F"]
r"""Type alias for diff types: F2P (Failure to Pass) or P2F (Pass to Failure)."""

TaskIdType: tp.TypeAlias = int
r"""Type alias for task identifiers."""

ScenarioIdType: tp.TypeAlias = str
r"""Type alias for scenario identifiers."""

CRLocatorIdType: tp.TypeAlias = int
r"""Type alias for CR locator identifiers."""


class TaskInfo(BaseModel):
    r"""
    Task information model for CR locator.

    Attributes:
        id: Task identifier.
        animation: URL for animation playback.
        vlm_animation_task: Optional task ID for VLM-specific layout animation.
        vlm_animation: Optional URL for VLM-specific layout animation.
    """

    id: TaskIdType
    animation: tp.Annotated[
        HttpUrlStr,
        Field(description='动画 **播放** 链接'),
    ]
    vlm_animation: tp.Annotated[
        tp.Optional[HttpUrlStr],
        Field(description='视觉模型专用 layout 动画链接'),
    ] = None
    vlm_animation_task: tp.Annotated[
        tp.Optional[TaskIdType],
        Field(description='视觉模型专用 layout 动画生产 task'),
    ] = None

    model_config = ConfigDict(extra="allow")


class CommitInfo(BaseModel):
    r"""
    Commit information model.

    Attributes:
        commit: Commit hash or identifier.
    """

    commit: str

    model_config = ConfigDict(extra="allow")


class CRInfo(BaseModel):
    r"""
    CR information model.

    Attributes:
        binary: Binary identifier.
        commit: Commit information.
        task_id: Associated task information.
    """

    binary: int
    commit: CommitInfo
    task_id: TaskInfo


class CRLocatorDiffData(BaseModel):
    r"""
    CR locator diff data model.

    Represents the comparison data between base and feature tasks.

    Attributes:
        base_task: Base task identifier.
        feature_task: Feature task identifier.
        diff_type: Type of diff (F2P or P2F).
        base_vlm_animation: Optional URL for base VLM animation.
        feature_vlm_animation: Optional URL for feature VLM animation.
    """

    base_task: TaskIdType
    feature_task: TaskIdType
    diff_type: DiffType
    base_vlm_animation: tp.Annotated[
        tp.Optional[HttpUrlStr],
        Field(description='端到端 base 视觉模型专用 layout 动画链接'),
    ] = None
    feature_vlm_animation: tp.Annotated[
        tp.Optional[HttpUrlStr],
        Field(description='端到端 feature 视觉模型专用 layout 动画链接'),
    ] = None


class CRLocatorData(BaseModel):
    r"""
    CR locator data model.

    Represents the complete CR locator result including metrics,
    diff data, and identified CRs per scenario.

    Attributes:
        id: CR locator identifier.
        type: Locator type (type=9 brute locator doesn't support positioning).
        metrics: List of metric names analyzed.
        diff_data: Comparison data between base and feature.
        result: Mapping of scenario IDs to lists of CR info.
        blame_cr: Mapping of scenario IDs to blame commit info.
    """

    id: CRLocatorIdType
    type: tp.Annotated[
        int,
        Field(description='目前 type=9 代表的 brute locator 不支持定位'),
    ]
    metrics: list[str]
    diff_data: CRLocatorDiffData
    result: tp.Annotated[
        dict[ScenarioIdType, list[CRInfo]],
        Field(description='key 为场景，value 为该场景下的 CR 列表'),
    ]
    blame_cr: tp.Annotated[
        dict[ScenarioIdType, CommitInfo],
        Field(description='key 为场景，value 为该场景下的 blame CR'),
    ]

    model_config = ConfigDict(extra="allow")
