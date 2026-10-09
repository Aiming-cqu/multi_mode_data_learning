#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import typing as tp
import httpx

from tenacity import retry, stop_after_attempt
from urllib.parse import quote

from .cr_locator_types import (
    CRLocatorIdType,
    CRLocatorData,
    DiffType,
    ScenarioIdType,
)

if tp.TYPE_CHECKING:
    from tenacity.stop import StopBaseT


BASE_URL_PROD: str = "http://10.78.128.39/release"
BASE_URL_DEV: str = "http://10.190.55.60:8001"
BASE_URL: str = BASE_URL_PROD

CR_LOCATOR_PATH: str = "/regression/locator/query?id={id:d}"
CR_BLAME_PATH: str = "/regression/locator/extractor?id={id:d}&metric={metric:s}&diff_type={diff_type:s}"  # fmt: skip

STOP_POLICY: 'StopBaseT' = stop_after_attempt(3)

_client = httpx.AsyncClient(base_url=BASE_URL)


@retry(stop=STOP_POLICY, reraise=True)
async def get_cr_locator_data(locator_id: CRLocatorIdType) -> CRLocatorData:
    r"""
    Get CR locator data by ID from TE Tools service.

    Fetches CR locator results including identified CRs
    and blame information for regression analysis.

    Args:
        locator_id: Unique identifier for the CR locator job.

    Returns:
        Validated CRLocatorData object containing locator results.

    Raises:
        ValueError: If the API returns an error response.

    Examples:
        >>> await_(get_cr_locator_data(4358069))
        CRLocatorData(id=4358069, type=6, metrics=['dpe_collision'], ...)

        >>> await_(get_cr_locator_data(4541951))
        CRLocatorData(id=4541951, type=6, metrics=['dpe_collision'], diff_data=CRLocatorDiffData(base_task=3628143100002159, feature_task=3628143700002157, diff_type='F2P', base_vlm_animation='https://s3-nmg-inter.didistatic.com/orion-nmg-cn/all_data/ares_animation_videos/task_3657595700000000_0.mp4', feature_vlm_animation='https://s3-nmg-inter.didistatic.com/orion-nmg-cn/all_data/ares_animation_videos/task_3657595700000001_0.mp4'), ...)
    """
    url = CR_LOCATOR_PATH.format(id=locator_id)
    res = (await _client.get(url)).raise_for_status().json()
    if res["errno"] != 0:
        raise ValueError(f'API error {res["errno"]} on {locator_id=}: {res["msg"]}')
    return CRLocatorData.model_validate(res["data"])


@retry(stop=STOP_POLICY, reraise=True)
async def get_cr_blame_info(
    locator_id: CRLocatorIdType, *, metric: str, diff_type: DiffType
) -> tp.Mapping[ScenarioIdType, tp.Any]:
    r"""
    Get CR blame information for a specific metric and diff type.

    Fetches detailed blame information for a CR locator job,
    filtered by metric name and diff type.

    Args:
        locator_id: Unique identifier for the CR locator job.
        metric: Metric name to query blame info for.
        diff_type: Type of diff (F2P or P2F).

    Returns:
        Mapping of scenario IDs to blame information.
    """
    url = CR_BLAME_PATH.format(id=locator_id, metric=quote(metric), diff_type=quote(diff_type))
    res = (await _client.get(url)).raise_for_status().json()
    return res
