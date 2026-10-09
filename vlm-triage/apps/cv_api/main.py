#!/bin/sh
""":"
# prod
exec pixi run -e opencv -- env OTEL_ENVIRONMENT_NAME=prod python "$0" "$@"
# dev
pixi shell -e opencv
env OTEL_ENVIRONMENT_NAME=dev fastapi dev --host 0.0.0.0 --port "${TRIAGE_CV_API_PORT}" main.py
"""
#!/usr/bin/env -S pixi run -e opencv -- python

from __future__ import absolute_import, annotations

import os

NAME: str = os.environ.setdefault("OTEL_SERVICE_NAME", "cv-api")
ENV: str = os.getenv("OTEL_ENVIRONMENT_NAME", "prod")

from conflog import LOGGING_FORMAT_TID, configure_logging, configure_auto_tracing

configure_logging(force=True, logging_format=LOGGING_FORMAT_TID)
configure_auto_tracing()

import itertools, os, typing as tp
import logfire

from fastapi import (
    FastAPI,
    Request,
    Response,
    Depends,
    Query,
    File,
)

from lib.services.cv_service import CvService

if tp.TYPE_CHECKING:
    from numpy.typing import NDArray as Tensor
    from opentelemetry.metrics import Counter


app = FastAPI(
    title='CV API',
    description='API for computing image similarities using traditional computer vision algorithms (SIFT, etc.).',
)
service = CvService()

logfire.instrument_fastapi(app, capture_headers=True)
logfire.instrument_pydantic(record="failure")


def get_algorithm_kwds(request: Request) -> tp.Mapping[str, tp.Any]:
    kwds = dict[str, tp.Any](request.query_params)
    kwds.pop("algorithm_names", None)
    kwds.pop("fmt", None)
    return kwds


compute_similarity_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.requests.compute_similarity',
    unit='1',
    description='Number of compute_similarity requests',
)
compute_similarity_image_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.counter.compute_similarity.num_images',
    unit='1',
    description='Number of images in compute_similarity requests',
)


@app.post('/compute_similarity')
def compute_images_similarity(
    image_files: tp.Annotated[
        list[bytes],
        File(media_type="image/*", max_length=(1024**2 * 2)),
    ],
    *,
    algorithm_kwds: tp.Annotated[
        tp.Mapping[str, tp.Any],
        Depends(dependency=get_algorithm_kwds),
    ],
    algorithm_names: tp.Annotated[tp.Sequence[str], Query()] = ("SIFT",),
    fmt: tp.Annotated[
        tp.Literal["arrow_tensor", "arrow_recordbatch", "parquet", "safetensors"],
        Query(),
    ] = "arrow_recordbatch",
) -> Response:
    r"""
    Compute image similarities using traditional CV algorithms.

    Args:
        image_files: List of uploaded image files (max 10MB each).
        algorithm_names: Sequence of CV algorithm names (e.g., "SIFT").
        algorithm_kwds: Additional keyword arguments for algorithms.
        fmt: Response format (arrow_tensor, arrow_recordbatch, parquet, or safetensors).

    Returns:
        Response containing similarity scores in the specified format.
        Shape: (num_images, num_algorithms, 2)
        - [:, :, 0]: similarities with base image (index 0)
        - [:, :, 1]: similarities with feature image (index -1)
        Values are in [0, 1] where 1 means identical.
    """

    compute_similarity_counter.add(1)
    compute_similarity_image_counter.add(len(image_files))

    # Compute similarity using CvService
    s_nam2 = service.compute_images_similarity(
        image_files, algorithm_names=algorithm_names, **algorithm_kwds
    )

    with logfire.span(f'serialize response with {fmt=}'):
        match fmt:
            case "arrow_tensor" | "arrow_recordbatch" | "parquet":
                import pyarrow as pa

                from lib.utils.arrow_utils import dump

                # Prepare tensor for dumping
                tensor: 'Tensor' = (
                    s_nam2 if fmt == "arrow_tensor" else s_nam2.reshape(s_nam2.shape[0], -1)
                )

                fmt_: str = "parquet" if fmt == "parquet" else "arrow"

                # Generate column names based on algorithms and comparison ends (base/feature)
                # For CV, we have a single metric (Score) to match embedding's 4D format
                names = list[str](
                    map(
                        ':'.join,
                        itertools.product(algorithm_names, ["Score"], ["base", "feature"]),
                    )
                )

                dim_names: list[str] = ["image", "algorithm", "metric", "end"]

                stream: pa.NativeFile = dump(
                    tensor,
                    fmt_,
                    names=names,
                    dim_names=dim_names,
                )

                media_type: str = (
                    "application/vnd.apache.parquet"
                    if fmt == "parquet"
                    else "application/vnd.apache.arrow.stream"
                )

                return Response(
                    content=stream.getvalue().to_pybytes(),
                    media_type=media_type,
                )

            case "safetensors":
                from safetensors.numpy import save

                return Response(
                    content=save({"similarity": s_nam2}),
                    media_type="application/octet-stream",
                )

            case _:
                raise ValueError(f'Unsupported {fmt=}')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        "main:app",
        host='0.0.0.0',
        port=int(os.environ["TRIAGE_CV_API_PORT"]),
        workers=int(os.environ["TRIAGE_CV_API_WORKERS"]),
    )
