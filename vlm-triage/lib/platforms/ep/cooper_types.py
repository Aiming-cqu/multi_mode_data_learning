from __future__ import absolute_import, annotations

import datetime as dt, typing as tp

from pydantic import BaseModel, ConfigDict


class FileInfo(BaseModel):
    r"""
    Metadata for a single file returned by the Cooper list-directory API.

    Attributes:
        id: Numeric Cooper file ID (used for download).
        display_name: Human-readable filename shown in Cooper UI.
        create_time: Creation timestamp parsed from Cooper's ``YYYY-MM-DD HH:MM:SS`` format.
    """

    id: int
    display_name: str
    create_time: dt.datetime
    modify_time: dt.datetime
    type: int
    has_child: bool
    create_by: str
    create_by_cn: str

    model_config = ConfigDict(extra="allow")
