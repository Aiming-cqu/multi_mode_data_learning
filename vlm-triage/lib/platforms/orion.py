#!/usr/bin/env -S pixi run -e voyager-dev -- test

from __future__ import absolute_import, annotations

import logging, typing as tp
import requests

from functools import lru_cache
from orion.db_accessor.task_accessor import TaskAccessor
from orion.utils.storage_locator import StorageLocator
from tenacity import retry, stop_after_attempt
from voy_data_utils.regions import Regions

from .orion_types import TaskIdType, TaskData

if tp.TYPE_CHECKING:
    from tenacity.stop import StopBaseT


STOP_POLICY: 'StopBaseT' = stop_after_attempt(3)

logger: logging.Logger = logging.getLogger(name=__name__)


@lru_cache()
@retry(stop=STOP_POLICY, reraise=True)
def gift3_to_url(loc: str) -> str:
    r"""
    Convert a gift3 storage location to a download URL.

    Uses the StorageLocator to generate a temporary download URL for
    gift3-stored resources.

    Args:
        loc: Gift3 storage location string.

    Returns:
        Temporary download URL for the resource.
    """
    return StorageLocator.from_string(loc).get_download_url()


@lru_cache()
@retry(stop=STOP_POLICY, reraise=True)
def fetch_maybe_gift3(url: str):
    r"""
    Fetch data from URL, handling gift3 locations automatically.

    If the URL doesn't start with 'http://', it's treated as a gift3
    location and converted to a download URL first.

    Args:
        url: HTTP URL or gift3 location string.

    Returns:
        JSON-decoded response data.
    """
    if not url.startswith('http://'): url = gift3_to_url(url)  # fmt: skip
    return requests.get(url).json()


@retry(stop=STOP_POLICY, reraise=True)
def get_task_data(task_id: TaskIdType) -> TaskData:
    r"""
    Get task data by task ID from Orion platform.

    Queries the Orion task database and returns structured task data
    including results and task arguments.

    Args:
        task_id: Unique identifier for the task.

    Returns:
        Validated TaskData object containing task information.

    Raises:
        ValueError: If the query returns zero or multiple results.

    Examples:
        >>> get_task_data(3417612500000085)
        TaskData(id=3417612500000085, result=...)
    """

    logger.info('get task_id: %r', task_id)
    ress: list[tp.Mapping[str, tp.Any]] = TaskAccessor.query(
        params={
            "id": task_id,
            "extra_fields": ','.join(["result", "task_args"]),
        },
        region=Regions.CN,
    )
    if len(ress) != 1:
        raise ValueError(f'Length is {len(ress)} != 1, {task_id=} {ress=}')
    return TaskData.validate(ress[0])
