#!/bin/sh
""":"
# prod
exec pixi run -e vllm -- env OTEL_ENVIRONMENT_NAME=prod python "$0" "$@"
# dev
pixi shell -e vllm
env OTEL_ENVIRONMENT_NAME=dev fastapi dev --host 0.0.0.0 --port "${TRIAGE_EMBEDDING_API_PORT}" main.py
"""
#!/usr/bin/env -S pixi run -e vllm -- python

from __future__ import absolute_import, annotations

import os

NAME: str = os.environ.setdefault("OTEL_SERVICE_NAME", "embedding-api")
ENV: str = os.getenv("OTEL_ENVIRONMENT_NAME", "prod")

from conflog import configure_logging, configure_auto_tracing

configure_logging(force=True)
configure_auto_tracing()

import itertools, os, typing as tp
import logfire

from fastapi import (
    FastAPI,
    Request,
    Response,
    Depends,
    Query,
    UploadFile,
    File,
)
from pydantic import Field

from lib.services.embedding_service import EmbeddingService, EmbeddingExtractorLoader
from lib.utils.async_utils import async_run

if tp.TYPE_CHECKING:
    from opentelemetry.metrics import Counter
    from torch import Tensor


app = FastAPI(
    title='Embedding API',
    description='API for extracting image embeddings using pre-trained models.',
)
service = EmbeddingService(EmbeddingExtractorLoader())

logfire.instrument_fastapi(app, capture_headers=True)
logfire.instrument_pydantic(record="failure")


def get_processor_kwds(request: Request) -> tp.Mapping[str, tp.Any]:
    kwds = dict[str, tp.Any](request.query_params)
    kwds.pop("model_ids", None)
    kwds.pop("metric_names", None)
    kwds.pop("fmt", None)
    return kwds


embed_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.requests.embed',
    unit='1',
    description='Number of embed requests',
)
embed_image_counter: 'Counter' = logfire.metric_counter(
    name=f'{NAME}.counter.embed.num_images',
    unit='1',
    description='Number of images in embed requests',
)


@app.post('/embed')
async def embed_images(
    image_files: tp.Annotated[
        list[UploadFile],
        File(media_type="image/*", max_length=(1024**2 * 2)),
    ],
    *,
    processor_kwds: tp.Annotated[
        tp.Mapping[str, tp.Any],
        Depends(dependency=get_processor_kwds),
        Field(examples=[{"text": ''}]),
    ],
    model_ids: tp.Annotated[tp.Sequence[str], Query()] = (
        'AI-ModelScope/clip-vit-large-patch14',
        'apple/aimv2-huge-patch14-448',
        'facebook/dinov2-base',
        'facebook/dinov2-large',
        'google/siglip2-base-patch16-224',
        'Salesforce/blip2-opt-2.7b',
    ),
    fmt: tp.Annotated[
        tp.Literal["arrow_tensor", "arrow_recordbatch", "safetensors"],
        Query(),
    ] = "arrow_recordbatch",
) -> Response:
    r"""
    Extract embeddings from uploaded images using specified models.

    Args:
        image_files: List of uploaded image files (max 10MB each).
        processor_kwds: Additional keyword arguments for the image processor.
        model_ids: Sequence of model identifiers for embedding extraction.
        fmt: Response format (arrow_tensor, arrow_recordbatch, or safetensors).

    Returns:
        Response containing embeddings in the specified format.
        For arrow formats, returns a stream of Arrow IPC record batches.
        For safetensors, returns serialized tensor data.
    """
    embed_counter.add(1)
    embed_image_counter.add(len(image_files))

    embeddings_by_model: 'dict[str, Tensor]' = await async_run(
        service.embed_images, [await f.read() for f in image_files], model_ids, **processor_kwds
    )

    with logfire.span(f'serialize response with {fmt=}'):
        match fmt:
            case "arrow_tensor" | "arrow_recordbatch":
                import pyarrow as pa

                from lib.utils.arrow_utils import dump

                names: list[str] = [
                    f.filename or f'File-{i}' for i, f in enumerate(image_files, start=1)
                ]
                dim_names: list[str] = ["image", "embedding"]
                stream = pa.BufferOutputStream()
                for model_id in model_ids:
                    e_nc = embeddings_by_model[model_id].cpu().float().numpy()
                    dump(
                        e_nc.T if fmt == "arrow_recordbatch" else e_nc,
                        "arrow",
                        names=names,
                        dim_names=dim_names,
                        stream=stream,
                    )

                return Response(
                    content=stream.getvalue().to_pybytes(),
                    media_type="application/vnd.apache.arrow.stream",
                )

            case "safetensors":
                from safetensors.torch import save

                return Response(
                    content=save(embeddings_by_model),
                    media_type="application/octet-stream",
                )

            case _:
                raise ValueError(f'Unsupported {fmt=}')


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
    processor_kwds: tp.Annotated[
        tp.Mapping[str, tp.Any],
        Depends(dependency=get_processor_kwds),
        Field(examples=[{"text": ''}]),
    ],
    model_ids: tp.Annotated[tp.Sequence[str], Query()] = (
        'AI-ModelScope/clip-vit-large-patch14',
        'apple/aimv2-huge-patch14-448',
        'facebook/dinov2-base',
        'facebook/dinov2-large',
        'google/siglip2-base-patch16-224',
        'Salesforce/blip2-opt-2.7b',
    ),
    metric_names: tp.Annotated[tp.Sequence[str], Query()] = ("Cosine", "L2"),
    fmt: tp.Annotated[
        tp.Literal["arrow_tensor", "arrow_recordbatch", "parquet", "safetensors"],
        Query(),
    ] = "arrow_recordbatch",
) -> Response:
    r"""
    Compute similarity scores between images using embedding models.

    Args:
        image_files: List of uploaded image files (max 10MB each).
        processor_kwds: Additional keyword arguments for the image processor.
        model_ids: Sequence of model identifiers for embedding extraction.
        metric_names: Sequence of similarity metric names (e.g., "Cosine", "L2").
        fmt: Response format (arrow_tensor, arrow_recordbatch, parquet, or safetensors).

    Returns:
        Response containing similarity scores in the specified format.
        Shape: (num_images, num_models, num_metrics, 2)
        - [:, :, :, 0]: similarities with base image (index 0)
        - [:, :, :, 1]: similarities with feature image (index -1)
    """
    compute_similarity_counter.add(1)
    compute_similarity_image_counter.add(len(image_files))

    s_nms2 = service.compute_images_similarity(
        image_files, model_ids, metric_names=metric_names, **processor_kwds
    )

    with logfire.span(f'serialize response with {fmt=}'):
        match fmt:
            case "arrow_tensor" | "arrow_recordbatch" | "parquet":
                import pyarrow as pa

                from lib.utils.arrow_utils import dump

                tensor: 'Tensor' = (
                    s_nms2 if fmt == "arrow_tensor" else s_nms2.reshape(s_nms2.shape[0], -1)
                )
                fmt_: str = "parquet" if fmt == "parquet" else "arrow"
                names = list[str](
                    map(
                        ':'.join,
                        itertools.product(model_ids, metric_names, ["base", "feature"]),
                    )
                )
                dim_names: list[str] = ["image", "model", "metric", "end"]
                stream: pa.NativeFile = dump(
                    tensor.cpu().float().numpy(),
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
                from safetensors.torch import save

                return Response(
                    content=save({"similarity": s_nms2}),
                    media_type="application/octet-stream",
                )

            case _:
                raise ValueError(f'Unsupported {fmt=}')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app,
        host='0.0.0.0',
        port=int(os.environ["TRIAGE_EMBEDDING_API_PORT"]),
    )
