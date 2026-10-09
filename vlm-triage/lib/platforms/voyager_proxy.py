#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import os, typing as tp
import httpx

from async_lru import alru_cache
from tenacity import retry, stop_after_attempt

from .orion_types import TaskIdType, TaskData
from .trail_types import IssueIdType, IssueDetail

if tp.TYPE_CHECKING:
    from tenacity.stop import StopBaseT


STOP_POLICY: 'StopBaseT' = stop_after_attempt(3)

_client = httpx.AsyncClient(base_url=os.environ["TRIAGE_VOYAGER_PROXY_URL"])


@retry(stop=STOP_POLICY, reraise=True)
async def get_trail_issue_detail(issue_id: IssueIdType) -> IssueDetail:
    r"""
    Get issue detail by issue ID from Voyager proxy.

    Fetches issue details from the Trail platform via the Voyager proxy
    service with caching and automatic retry on failure.

    Args:
        issue_id: Unique identifier for the issue.

    Returns:
        Validated IssueDetail object containing issue information.

    Examples:
        >>> await_(get_trail_issue_detail('cn18732285'))
        IssueDetail(id='cn18732285', trip_id='17166_20250529_090920', ...)
    """

    url = f'/trail/issue/{issue_id}'
    res = (await _client.get(url)).raise_for_status().json()
    return IssueDetail.model_validate(res)


@retry(stop=STOP_POLICY, reraise=True)
async def get_orion_task_data(task_id: TaskIdType) -> TaskData:
    r"""
    Get task data by task ID from Voyager proxy.

    Fetches task data from the Orion platform via the Voyager proxy
    service with caching and automatic retry on failure.

    Args:
        task_id: Unique identifier for the task.

    Returns:
        Validated TaskData object containing task information.

    Examples:
        >>> await_(get_orion_task_data(3417612500000085))
        TaskData(id=3417612500000085, result=...)
    """

    url = f'/orion/task_data/{task_id}'
    res = (await _client.get(url)).raise_for_status().json()
    return TaskData.model_validate(res)


@alru_cache()
@retry(stop=STOP_POLICY, reraise=True)
async def get_dpe_METRIC_EVENT_MAPPING() -> tp.Mapping[str, str]:
    r"""
    Get DPE metric to event mapping from Voyager proxy.

    Fetches the mapping of DPE metric names to event identifiers
    with indefinite caching.

    Returns:
        Mapping of metric names to event strings.
    """
    url = '/dpe/constants/METRIC_EVENT_MAPPING'
    res = (await _client.get(url)).raise_for_status().json()
    return res
