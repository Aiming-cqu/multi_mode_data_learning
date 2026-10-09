#!/bin/sh
""":"
# prod
exec pixi run -e prod -- env OTEL_ENVIRONMENT_NAME=prod python "$0" "$@"
# dev
pixi shell
env OTEL_ENVIRONMENT_NAME=dev fastapi dev --host 0.0.0.0 --port "${TRIAGE_LOCATOR_API_PORT}" main.py
"""
#!/usr/bin/env -S pixi run -e prod -- python

from __future__ import absolute_import, annotations

import os

NAME: str = os.environ.setdefault("OTEL_SERVICE_NAME", "visual-cr-locator-api")
ENV: str = os.getenv("OTEL_ENVIRONMENT_NAME", "prod")

from conflog import configure_logging, configure_auto_tracing

configure_logging(force=True)
configure_auto_tracing()

import asyncio, logging, os, typing as tp
import httpx
import logfire

from collections import OrderedDict
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Request,
    Response,
    BackgroundTasks,
)
from pydantic import BaseModel, Field

from lib.services.visual_cr_locator_types import (
    AnnotationInfo,
    TicketType,
    LocatorConfig,
    LocatorResponse,
)
from lib.services.visual_cr_locator_service import (
    LocatorService,
    LocatorFail,
    CRLocatorIdType,
)
from lib.tools.resources import resource_context
from lib.utils.pydantic_compat import HttpUrlStr


if tp.TYPE_CHECKING:
    from opentelemetry.metrics import Counter


TASK_LIMIT: int = int(os.getenv("TRIAGE_LOCATOR_TASK_LIMIT", 1024))


class Task(BaseModel):
    r""""""

    response: LocatorResponse
    callback_url: tp.Optional[HttpUrlStr] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> tp.AsyncGenerator[None, None]:
    with resource_context():
        yield


app = FastAPI(
    title='Visual based CR locator API',
    description='API for locating change CR using visual models.',
    lifespan=lifespan,
)
service = LocatorService()
undone_tasks = OrderedDict[TicketType, Task]()
done_tasks = OrderedDict[TicketType, Task]()
http_client = httpx.AsyncClient()
lock = asyncio.Lock()

logfire.instrument_aiohttp_client(capture_headers=True)
logfire.instrument_fastapi(app, capture_headers=True)
logfire.instrument_httpx(capture_headers=True)
logfire.instrument_pydantic(record="failure")

logger: logging.Logger = logging.getLogger(name=__name__)

locate_sync_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.requests.locate_sync',
    unit='1',
    description='Number of sync locate requests',
)
locate_async_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.requests.locate_async',
    unit='1',
    description='Number of async locate requests',
)
locate_success_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.counter.locate.success',
    unit='1',
    description='Number of successful locate requests',
)
locate_error_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.counter.locate.error',
    unit='1',
    description='Number of error locate requests',
)
locate_not_found_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.counter.locate.not_found',
    unit='1',
    description='Number of not found locate quries',
)


@logfire.instrument
async def locate_wrapper(ticket: TicketType, /, *args, **kwds):
    r"""
    Wrapper for async locateing of CR locator tasks.

    Handles the execution of a locator task, updates task status,
    and optionally sends callback notifications.

    Args:
        ticket: Unique ticket identifier for the task.
        *args: Positional arguments passed to service.locate().
        **kwds: Keyword arguments passed to service.locate().
    """
    async with lock:
        task: Task = undone_tasks[ticket]  # fmt: skip
        task.response.status = "running"
    logger.info('async locate ticket=%r', ticket)
    try:
        res = await service.locate(*args, **kwds, session_id=ticket)
        locate_success_counter.add(1)
        async with lock:
            task.response.result = res
            task.response.status = "success"
        if task.callback_url:
            try:
                await http_client.post(
                    task.callback_url,
                    content=task.response.model_dump_json(),
                )
            except (Exception,):
                logger.exception('callback failed ticket=%r', ticket)
    except (LocatorFail,) as exc:
        logger.exception('ticket=%r', ticket)
        locate_error_counter.add(1)
        async with lock:
            task.response.result = exc.result
            task.response.message = exc.message
            task.response.status = "error"
    except (Exception,) as exc:
        logger.exception('ticket=%r', ticket)
        locate_error_counter.add(1)
        async with lock:
            task.response.message = repr(exc)
            task.response.status = "error"

    async with lock:
        while len(done_tasks) > TASK_LIMIT:
            t, _ = done_tasks.popitem(last=False)
            logger.info('dropped task ticket=%r', t)
        done_tasks[ticket] = undone_tasks.pop(ticket)


@app.post('/locate')
async def locate(
    locator_id: tp.Annotated[CRLocatorIdType, Field(examples=[4391943])],
    *,
    config: LocatorConfig = LocatorConfig(),
) -> LocatorResponse:
    r"""
    Synchronously locate the CR causing regression.

    Args:
        locator_id: Identifier for the CR locator job.
        config: Configuration parameters for the visual locator.

    Returns:
        Response containing the locator results or error information.
    """
    locate_sync_counter.add(1)
    resp = LocatorResponse()
    logger.info('sync locate ticket=%r', resp.ticket)
    with logfire.span(f'locate({locator_id=}, {config=})', ticket=resp.ticket):
        try:
            resp.result = await service.locate(
                locator_id,
                config=config,
                session_id=resp.ticket,
            )
            resp.status = "success"
            locate_success_counter.add(1)
        except (LocatorFail,) as exc:
            logger.exception('ticket=%r', resp.ticket)
            locate_error_counter.add(1)
            resp.result = exc.result
            resp.message = exc.message
            resp.status = "error"
        except (Exception,) as exc:
            logger.exception('ticket=%r', resp.ticket)
            locate_error_counter.add(1)
            resp.message = repr(exc)
            resp.status = "error"
        return resp


@app.post('/locate/async')
async def locate_launch(
    background_tasks: BackgroundTasks,
    locator_id: tp.Annotated[CRLocatorIdType, Field(examples=[4391943])],
    *,
    config: LocatorConfig = LocatorConfig(),
    callback_url: tp.Optional[HttpUrlStr] = None,
) -> TicketType:
    r"""
    Asynchronously launch a CR locator task.

    Args:
        background_tasks: FastAPI background tasks handler.
        locator_id: Identifier for the CR locator job.
        config: Configuration parameters for the visual locator.
        callback_url: Optional URL to receive callback when task completes.

    Returns:
        Ticket identifier for tracking the async task.
    """
    locate_async_counter.add(1)
    resp = LocatorResponse()
    logger.info('enqueue ticket=%r', resp.ticket)
    with logfire.span(f'locate_launch({locator_id=}, {config=})', ticket=resp.ticket):
        task = Task(response=resp, callback_url=callback_url)
        async with lock: undone_tasks[resp.ticket] = task  # fmt: skip
        background_tasks.add_task(locate_wrapper, resp.ticket, locator_id, config=config)
        return resp.ticket


@app.get('/locate/async/{ticket}')
async def locate_query(ticket: TicketType) -> LocatorResponse:
    r"""
    Query the result of an asynchronous locator task.

    Args:
        ticket: Ticket identifier returned by locate_launch.

    Returns:
        Response containing the current status and results if available.
        Returns error status if ticket is not found.
    """
    logger.info('query ticket=%r', ticket)

    async with lock:
        try: return done_tasks[ticket].response  # fmt:skip
        except (KeyError,): pass  # fmt:skip
        try: return undone_tasks[ticket].response  # fmt:skip
        except (KeyError,): pass  # fmt:skip

    locate_not_found_counter.add(1)
    return LocatorResponse(ticket=ticket, status="error", message='ticket not found')


# =============================================================================
# 标注 API
# =============================================================================


@app.post('/annotation')
async def get_annotation_info(
    locator_id: tp.Annotated[CRLocatorIdType, Field(examples=[4391943])],
    *,
    config: LocatorConfig = LocatorConfig(),
) -> AnnotationInfo:
    return await service.get_annotation_info(locator_id, config=config)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app,
        host='0.0.0.0',
        port=int(os.environ["TRIAGE_LOCATOR_API_PORT"]),
    )
