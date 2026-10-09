#!/bin/sh
""":"
# prod
exec pixi run -e voyager -- env OTEL_ENVIRONMENT_NAME=prod python "$0" "$@"
# dev
pixi shell -e voyager-dev
env OTEL_ENVIRONMENT_NAME=dev fastapi dev --host 0.0.0.0 --port "${TRIAGE_VOYAGER_PROXY_PORT}" main.py
"""
#!/usr/bin/env -S pixi run -e voyager -- python

from __future__ import absolute_import, annotations

import os

NAME: str = os.environ.setdefault("OTEL_SERVICE_NAME", "voyager-proxy")

from conflog import LOGGING_FORMAT_TID, configure_logging

configure_logging(force=True, logging_format=LOGGING_FORMAT_TID)

import logging, os, typing as tp

from data_analysis.constants.dpe_metric_constants import METRIC_EVENT_MAPPING
from fastapi import (
    FastAPI,
    Request,
    Response,
)

from lib.platforms.orion import (
    TaskIdType,
    TaskData,
    get_task_data,
    gift3_to_url,
)
from lib.platforms.trail import get_issue_detail


app = FastAPI(
    title='Voyager Proxy',
    description='Voyager API as micro service.',
)
logger: logging.Logger = logging.getLogger(name=__name__)

app.add_api_route(
    '/trail/issue/{issue_id}',
    get_issue_detail,
    methods=["GET"],
)


@app.get('/orion/task_data/{task_id}')
def get_orion_task_data(task_id: TaskIdType) -> TaskData:
    task_data: TaskData = get_task_data(task_id)
    if len(locations := task_data.result.dpe_output_locations) > 0:
        task_data.dpe_output_url = gift3_to_url(locations[0])
    if len(locations := task_data.result.animation_locations) > 0:
        task_data.animation_url = gift3_to_url(locations[0])
    return task_data


@app.get('/dpe/constants/METRIC_EVENT_MAPPING')
def get_dpe_METRIC_EVENT_MAPPING() -> tp.Mapping[str, str]:
    return METRIC_EVENT_MAPPING


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        "main:app",
        host='0.0.0.0',
        port=int(os.environ["TRIAGE_VOYAGER_PROXY_PORT"]),
        workers=int(os.environ["TRIAGE_VOYAGER_PROXY_WORKERS"]),
    )
