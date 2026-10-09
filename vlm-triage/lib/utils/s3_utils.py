#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import datetime as dt, os, sys, typing as tp

from contextlib import asynccontextmanager
from miniopy_async import Minio

from .io_utils import PathLikeStr

if tp.TYPE_CHECKING:
    from collections.abc import AsyncIterator


NAME: str = os.getenv('OTEL_SERVICE_NAME', os.path.splitext(os.path.basename(sys.argv[0]))[0])
PARTITION_FORMAT: str = '%Y%m%d'

DEFAULT_END_POINT: str = 's3-nmgpu-inter.didistatic.com'
DEFAULT_ACCESS_KEY: str = os.getenv('TRIAGE_S3_ACCESS_KEY', 'AKDD00000000000ZR6IP2BA7BQEHEG')
DEFAULT_SECRET_KEY: str = os.getenv('TRIAGE_S3_SECRET_KEY', 'ASDDmhmKJgUccAmJVIiFsSRVtlLzAeWjADyZwcLk')
DEFAULT_BUCKET: str = os.getenv('TRIAGE_S3_BUCKET', 'te-ds-autolabeling-dos-1')
DEFAULT_DATA_PREFIX: str = os.environ['TRIAGE_DATA_PREFIX_IN_S3']

# Team-level shared credential (same pattern as cooper.py).
default_client = Minio(
    DEFAULT_END_POINT,
    access_key=DEFAULT_ACCESS_KEY,
    secret_key=DEFAULT_SECRET_KEY,
)


def prepend_object_partition(
    object_name: str,
    app_name: str = NAME,
    prefix: str = DEFAULT_DATA_PREFIX,
) -> str:
    r"""Prepend ``<prefix>/<app_name>/<YYYYMMDD>/`` to *object_name*."""
    prefix = prefix.rstrip('/') + '/' if prefix else ''
    partition: str = dt.date.today().strftime(PARTITION_FORMAT)
    return f'{prefix}{app_name}/{partition}/{object_name}'


@asynccontextmanager
async def get(
    object_name: str,
    bucket_name: str = DEFAULT_BUCKET,
    *,
    chunk_size: int = (1024**2 * 1),
    **get_kwds
) -> AsyncIterator[tp.AsyncIterator[bytes]]:
    r"""Download object as a chunked async byte stream.

    Usage::

        async with get('my-object') as stream:
            await copy_to(stream, 'output.bin')
    """
    resp = await default_client.get_object(bucket_name, object_name, **get_kwds)
    try: yield resp.content.iter_chunked(chunk_size)  # fmt: skip
    finally: resp.release()  # fmt: skip


async def sign(
    object_name: str,
    bucket_name: str = DEFAULT_BUCKET,
    *,
    content_type: str = 'application/octet-stream',
    response_headers: tp.Optional[dict[str, str]] = None,
    **sign_kwds
) -> str:
    r"""Generate a presigned GET URL for an existing object."""
    response_headers = response_headers or dict[str, str]()
    response_headers['response-content-type'] = content_type
    return await default_client.presigned_get_object(
        bucket_name, object_name, response_headers=response_headers, **sign_kwds
    )


async def put_and_sign(
    data: tp.BinaryIO,
    object_name: str,
    length: int = -1,
    bucket_name: str = DEFAULT_BUCKET,
    *,
    content_type: str = 'application/octet-stream',
    response_headers: tp.Optional[dict[str, str]] = None,
    **put_kwds
) -> str:
    r"""Upload a binary stream and return a presigned URL.

    When *app_name* is not ``None``, *object_name* is automatically
    partitioned via :func:`prepend_object_partition`.
    """
    await default_client.put_object(
        bucket_name, object_name, data, length, content_type=content_type, **put_kwds
    )
    return await sign(
        object_name,
        bucket_name=bucket_name,
        content_type=content_type,
        response_headers=response_headers,
    )


async def fput_and_sign(
    file_path: PathLikeStr,
    object_name: str,
    bucket_name: str = DEFAULT_BUCKET,
    *,
    content_type: str = 'application/octet-stream',
    response_headers: tp.Optional[dict[str, str]] = None,
    **fput_kwds
) -> str:
    r"""Upload a local file and return a presigned URL.

    When *app_name* is not ``None``, *object_name* is automatically
    partitioned via :func:`prepend_object_partition`.
    """
    await default_client.fput_object(
        bucket_name, object_name, os.fspath(file_path), content_type=content_type, **fput_kwds
    )
    return await sign(
        object_name,
        bucket_name=bucket_name,
        content_type=content_type,
        response_headers=response_headers,
    )


if __name__ == '__main__':
    import asyncio
    import typer

    from .io_utils import copy_to, is_path_stdio

    app = typer.Typer(no_args_is_help=True)
    runner = asyncio.Runner()

    @app.command()
    def ls(
        prefix: tp.Annotated[
            str,
            typer.Argument(help='对象名前缀'),
        ] = '',
        *,
        recursive: tp.Annotated[
            bool,
            typer.Option('--recursive', '-r', help='递归列出'),
        ] = False,
        bucket: tp.Annotated[
            str,
            typer.Option('--bucket', '-b', help='Bucket 名称'),
        ] = DEFAULT_BUCKET,
    ):
        r"""列出 S3 对象。"""

        async def impl():
            async for obj in default_client.list_objects(
                bucket,
                prefix=prefix,
                recursive=recursive,
            ):
                if obj.is_dir:
                    typer.echo(f'{"PRE":>31s}  {obj.object_name}')
                else:
                    ts = (
                        obj.last_modified.strftime('%Y-%m-%d %H:%M:%S')
                        if obj.last_modified
                        else ''
                    )
                    size = obj.size if obj.size is not None else 0
                    typer.echo(f'{ts}  {size:>10d}  {obj.object_name}')

        runner.run(impl())

    @app.command('get')
    def get_cmd(
        object_name: tp.Annotated[
            str,
            typer.Argument(help='S3 对象名'),
        ],
        file_path: tp.Annotated[
            tp.Optional[str],
            typer.Argument(
                help="本地路径；省略则用 object_name 下载到当前目录；'-' 输出到 stdout",
            ),
        ] = None,
        *,
        bucket: tp.Annotated[
            str,
            typer.Option('--bucket', '-b', help='Bucket 名称'),
        ] = DEFAULT_BUCKET,
    ):
        r"""下载 S3 对象到文件或 stdout。"""
        local_path = file_path if file_path is not None else os.path.basename(object_name)

        async def impl():
            async with get(object_name, bucket) as stream:
                await copy_to(stream, local_path)

        runner.run(impl())
        if is_path_stdio(local_path): return  # fmt: skip
        size = os.path.getsize(local_path)
        typer.echo(f'{local_path} ({size} bytes)', err=True)

    @app.command()
    def put(
        file_path: tp.Annotated[
            str,
            typer.Argument(help='本地文件路径'),
        ],
        object_name: tp.Annotated[
            str,
            typer.Argument(help='S3 对象名'),
        ],
        *,
        app_name: tp.Annotated[
            tp.Optional[str],
            typer.Option('--app-name', help='应用名，设定后自动拼接分区路径'),
        ] = None,
        prefix: tp.Annotated[
            str,
            typer.Option('--prefix', help='分区路径前缀'),
        ] = DEFAULT_DATA_PREFIX,
        content_type: tp.Annotated[
            str,
            typer.Option('--content-type', '-t', help='Content-Type'),
        ] = 'application/octet-stream',
        bucket: tp.Annotated[
            str,
            typer.Option('--bucket', '-b', help='Bucket 名称'),
        ] = DEFAULT_BUCKET,
    ):
        r"""上传本地文件到 S3。"""
        if object_name.endswith('/'): object_name = object_name + os.path.basename(file_path)  # fmt: skip
        object_name = (
            prepend_object_partition(object_name, app_name=app_name, prefix=prefix)
            if app_name
            else object_name
        )
        runner.run(
            default_client.fput_object(
                bucket,
                object_name,
                file_path,
                content_type=content_type,
            )
        )
        typer.echo(object_name, err=True)

    @app.command('sign')
    def sign_cmd(
        object_name: tp.Annotated[
            str,
            typer.Argument(help='S3 对象名'),
        ],
        *,
        content_type: tp.Annotated[
            str,
            typer.Option('--content-type', '-t', help='Content-Type'),
        ] = 'application/octet-stream',
        bucket: tp.Annotated[
            str,
            typer.Option('--bucket', '-b', help='Bucket 名称'),
        ] = DEFAULT_BUCKET,
    ):
        r"""生成预签名 GET URL。"""
        url = runner.run(sign(object_name, bucket, content_type=content_type))
        typer.echo(url)

    @app.command('put-sign')
    def put_sign_cmd(
        file_path: tp.Annotated[
            str,
            typer.Argument(help='本地文件路径'),
        ],
        object_name: tp.Annotated[
            str,
            typer.Argument(help='S3 对象名'),
        ],
        *,
        app_name: tp.Annotated[
            tp.Optional[str],
            typer.Option('--app-name', help='应用名，设定后自动拼接分区路径'),
        ] = None,
        prefix: tp.Annotated[
            str,
            typer.Option('--prefix', help='分区路径前缀'),
        ] = DEFAULT_DATA_PREFIX,
        content_type: tp.Annotated[
            str,
            typer.Option('--content-type', '-t', help='Content-Type'),
        ] = 'application/octet-stream',
        bucket: tp.Annotated[
            str,
            typer.Option('--bucket', '-b', help='Bucket 名称'),
        ] = DEFAULT_BUCKET,
    ):
        r"""上传文件并生成预签名 URL。"""
        if object_name.endswith('/'): object_name = object_name + os.path.basename(file_path)  # fmt: skip
        object_name = (
            prepend_object_partition(object_name, app_name=app_name, prefix=prefix)
            if app_name
            else object_name
        )
        url = runner.run(
            fput_and_sign(
                file_path,
                object_name,
                bucket_name=bucket,
                app_name=app_name,
                prefix=prefix,
                content_type=content_type,
            )
        )
        typer.echo(url)

    app()
