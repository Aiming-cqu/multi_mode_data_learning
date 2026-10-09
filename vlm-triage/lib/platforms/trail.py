#!/usr/bin/env -S pixi run -e voyager-dev -- test

from __future__ import absolute_import, annotations

import logging, typing as tp

from auto_scene_mining.utility.issue_accessor import IssuePoolAccessor
from tenacity import retry, stop_after_attempt

from .trail_types import IssueIdType, IssueDetail

if tp.TYPE_CHECKING:
    from tenacity.stop import StopBaseT


STOP_POLICY: 'StopBaseT' = stop_after_attempt(3)

logger: logging.Logger = logging.getLogger(name=__name__)


@retry(stop=STOP_POLICY, reraise=True)
def get_issue_detail(issue_id: IssueIdType) -> IssueDetail:
    r"""
    Get issue detail by issue ID from Trail platform.

    Queries the Auto Scene Mining issue pool and returns structured
    issue details including trip information and animation location.

    Args:
        issue_id: Unique identifier for the issue (e.g., 'cn18732285').

    Returns:
        Validated IssueDetail object containing issue information.

    Examples:
        >>> get_issue_detail('cn18732285')
        IssueDetail(id='cn18732285', trip_id='17166_20250529_090920', ...)
    """

    logger.info('get issue_id: %r', issue_id)
    res: tp.Mapping[str, tp.Any] = IssuePoolAccessor.detail(
        {
            "source_id": 1,
            "issue_id": issue_id,
            "preserving_name_for_enums": True,
        },
    )
    return IssueDetail.validate({**res, "id": issue_id})
