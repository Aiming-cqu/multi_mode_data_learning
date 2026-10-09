r"""
Type definitions for Orion platform data models.

This module defines Pydantic models for Orion task data and related types,
with compatibility handling for both Voyager and non-Voyager environments.
"""

from __future__ import absolute_import, annotations

import typing as tp

from pydantic import BaseModel, Field

from ..utils.pydantic_compat import HttpUrlStr

try:
    from orion.model.result import TaskResult

    IS_VOYAGER_ENV: bool = True
except (ImportError,):
    from pydantic import ConfigDict

    IS_VOYAGER_ENV: bool = False

    class TaskResult(BaseModel):
        animation_time_range_ms: tuple[int, int]

        model_config = ConfigDict(extra="allow")


TaskIdType: tp.TypeAlias = int
r"""Type alias for Orion task identifiers."""


class TaskData(BaseModel):
    r"""
    Pydantic model for Orion task data.

    Represents a task with its results, arguments, and associated URLs
    for animation and DPE output data.

    Attributes:
        id: Unique task identifier.
        result: Task result data including animation time range.
        task_args: Mapping of task argument names to values.
        animation_url: Optional URL to task animation data.
        dpe_output_url: Optional URL to DPE output data.
    """

    id: TaskIdType
    result: TaskResult
    task_args: dict[str, tp.Any]
    animation_url: tp.Optional[HttpUrlStr] = None
    dpe_output_url: tp.Optional[HttpUrlStr] = None

    if IS_VOYAGER_ENV:

        class Config:
            extra = "allow"
            json_encoders = {
                TaskResult: TaskResult.as_dict,
            }
    else:
        model_config = ConfigDict(extra="allow")
