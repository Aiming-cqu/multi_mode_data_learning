r"""
Type definitions for Trail platform data models.

This module defines Pydantic models for Trail (Auto Scene Mining) issue data,
with compatibility handling for both Pydantic v1 and v2.

Attributes:
    -
"""

from __future__ import absolute_import, annotations

import typing as tp

from pydantic import BaseModel, Field

try:
    from pydantic.version import VERSION as PYDANTIC_VERSION

    IS_PYDANTIC_V1: bool = PYDANTIC_VERSION.startswith('1.')
except (ImportError,):
    IS_PYDANTIC_V1: bool = True

if not IS_PYDANTIC_V1:
    from pydantic import ConfigDict


IssueIdType: tp.TypeAlias = str
r"""Type alias for Trail issue identifiers."""


class IssueDetail(BaseModel):
    r"""
    Pydantic model for Trail issue details.

    Represents an issue with its associated trip information,
    timing data, and animation storage location.

    Attributes:
        id: Unique issue identifier.
        trip_id: Associated trip identifier string.
        issue_time: Issue timestamp in milliseconds (接管时间点).
        ares_bag_animation: Gift3 storage location for animation data.
        description: Optional issue description text.
    """
    id: IssueIdType
    trip_id: str
    issue_time: tp.Annotated[
        int,
        Field(description='接管时间点，单位毫秒'),
    ]
    ares_bag_animation: tp.Annotated[
        str,
        Field(description='动画 gift3 存储位置'),
    ]
    description: str = ''

    if IS_PYDANTIC_V1:

        class Config:
            extra = "allow"
    else:
        model_config = ConfigDict(extra="allow")
