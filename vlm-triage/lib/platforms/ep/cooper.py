#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import os, re, typing as tp
import httpx

from contextlib import asynccontextmanager
from pathlib import Path
from tenacity import retry, stop_after_attempt
from zipfile import ZipFile

from ...utils.io_utils import (
    PathLikeStr,
    copy_to,
    ensure_seekable_input,
)

from .cooper_types import FileInfo

if tp.TYPE_CHECKING:
    from httpx._types import FileTypes
    from tenacity.stop import StopBaseT


PUBLIC_BASE_URL: str = 'https://cooper.didichuxing.com/team-file'

# Team-level API key (shared credential, safe to commit).
# Individual username must be set via COOPER_USERNAME env var (see local.sh).
DEFAULT_BASE_URL: str = 'http://api-kylin.intra.xiaojukeji.com/EP_CLOUD_DISK_oe_openapi_cooper_server_prod'  # fmt: skip
DEFAULT_API_KEY: str = '7d38c6e1f54144bf950fd210feebe682'

STOP_POLICY: 'StopBaseT' = stop_after_attempt(3)

_DOCS2_RE = re.compile(r'/docs2/\w+/(\d+)')
_TEAM_FILE_RE = re.compile(r'/team-file/(\d+)/(\d+)')
_STYLE_TAG_RE = re.compile(r'<w:style\b(?![^>]*\bw:type=)([^>]*)>')


def parse_team_file_url(url: str) -> tuple[int, int]:
    r"""Parse a Cooper team-file URL and extract group_id + resource_id.

    Args:
        url: A Cooper team-file URL like
            ``https://cooper.didichuxing.com/team-file/{group_id}/{resource_id}``.

    Returns:
        ``(group_id, resource_id)`` tuple.

    Raises:
        ValueError: If the URL does not match the team-file pattern.

    Examples:
        >>> parse_team_file_url('https://cooper.didichuxing.com/team-file/123/456')
        (123, 456)
    """
    if m := _TEAM_FILE_RE.search(url):
        return (int(m.group(1)), int(m.group(2)))
    raise ValueError(f'Not a team-file URL: {url}')


def parse_docs2_url(url: str) -> int:
    r"""Parse a Cooper docs2 URL and extract the resource_id.

    Args:
        url: A Cooper docs2 URL like
            ``https://cooper.didichuxing.com/docs2/document/{resource_id}``.

    Returns:
        The document ``resource_id``.

    Raises:
        ValueError: If the URL does not match the docs2 pattern.

    Examples:
        >>> parse_docs2_url('https://cooper.didichuxing.com/docs2/document/789')
        789
    """
    if m := _DOCS2_RE.search(url):
        return int(m.group(1))
    raise ValueError(f'Not a docs2 URL: {url}')


def get_team_file_url(group_id: int, resource_id: int) -> str:
    r"""
    Get a URL for browsing a Cooper directory in the web UI.

    Args:
        group_id: Cooper team group ID.
        resource_id: Cooper folder ID.

    Returns:
        URL string for the folder in Cooper's web interface.

    Parameters:
        -
    """

    return f'{PUBLIC_BASE_URL}/{group_id}/{resource_id}'


def normalize_styles_xml(
    styles_xml: str,
    default_style_type: str = 'paragraph',
) -> tuple[str, int]:
    r"""
    Add missing ``w:type`` attributes to DOCX style tags.

    Args:
        styles_xml: XML content from ``word/styles.xml``.
        default_style_type: Fallback ``w:type`` value for custom styles that
            omit it.

    Returns:
        Tuple of ``(normalized_xml, patched_count)``.

    Examples:
        >>> normalize_styles_xml('<w:style w:styleId="s1"></w:style>')
        ('<w:style w:styleId="s1" w:type="paragraph"></w:style>', 1)
        >>> normalize_styles_xml('<w:style w:type="table" w:styleId="s2"></w:style>')
        ('<w:style w:type="table" w:styleId="s2"></w:style>', 0)

    Parameters:
        -
    """
    return _STYLE_TAG_RE.subn(
        rf'<w:style\1 w:type="{default_style_type}">',
        styles_xml,
    )


def normalize_docx_file(
    input_file: tp.BinaryIO,
    output_file: tp.BinaryIO,
    default_style_type: str = 'paragraph',
) -> int:
    r"""
    Normalize exported DOCX content so downstream converters can parse styles.

    Args:
        input_file: Binary DOCX input file object.
        output_file: Binary DOCX output file object.
        default_style_type: Fallback ``w:type`` for styles that omit it.

    Returns:
        Number of patched style tags.

    Parameters:
        -
    """
    patched_count: int = 0
    with ensure_seekable_input(input_file) as seekable_input_file:
        seekable_input_file.seek(0)
        with (
            ZipFile(seekable_input_file) as input_zip,
            ZipFile(output_file, mode='w') as output_zip,
        ):
            output_zip.comment = input_zip.comment
            for file_info in input_zip.infolist():
                file_bytes = input_zip.read(file_info)
                if file_info.filename == 'word/styles.xml':
                    styles_xml, patched_count = normalize_styles_xml(
                        file_bytes.decode('utf-8'),
                        default_style_type=default_style_type,
                    )
                    file_bytes = styles_xml.encode('utf-8')
                output_zip.writestr(file_info, file_bytes)
    return patched_count


class CooperClient:
    r"""
    Async HTTP client for the Cooper open file-management API.

    Wraps the Cooper intranet REST API with typed methods for uploading files,
    listing directory contents, and generating download links.  Authentication
    uses a shared team-level API key plus a per-user ``username`` taken from
    the ``COOPER_USERNAME`` environment variable.

    All network methods are decorated with :func:`~tenacity.retry` and will
    retry up to :data:`STOP_POLICY` times on transient failures.

    Attributes:
        _client: Underlying :class:`httpx.AsyncClient` instance.

    Example::

        client = CooperClient()
        info = await client.upload_file(GROUP_ID, PARENT_ID, open("report.pdf", "rb"))
        items = await client.list_dir(GROUP_ID, FOLDER_ID)
        url = await client.get_download_url(GROUP_ID, [items[0].id])
        data = await client.export_cooperate(DOC_RESOURCE_ID, '/tmp/doc.docx')

    Parameters:
        -
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = DEFAULT_API_KEY,
        username: tp.Optional[str] = None,
    ):
        r"""
        Initialise the client with Cooper credentials.

        Args:
            base_url: Cooper API base URL.  Defaults to the internal
                production endpoint :data:`DEFAULT_BASE_URL`.
            api_key: Team-level Cooper API key.  Defaults to
                :data:`DEFAULT_API_KEY` (safe to keep in source).
            username: Cooper username for the ``username`` header.  Defaults
                to ``os.environ["COOPER_USERNAME"]``; must be set in the shell
                environment (e.g. via ``local.sh``).

        Parameters:
            -
        """
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Apikey": api_key, "username": username or os.environ["COOPER_USERNAME"]},
        )

    @retry(stop=STOP_POLICY, reraise=True)
    async def list_dir(self, group_id: int, resource_id: int) -> list[FileInfo]:
        r"""
        List files in a Cooper folder.

        Args:
            group_id: Cooper team group ID.
            resource_id: Cooper folder ID to list.

        Returns:
            List of :class:`~cooper_types.FileInfo` objects in the folder.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            RuntimeError: If the Cooper API returns ``success: false``.

        Examples:
            >>> client = CooperClient()
            >>> await_(client.list_dir(2199094698523, 2205779003774))
            [...FileInfo(id=2207369729546, display_name='.test', ...)...]

        """

        resp = await self._client.get(
            '/openapi/v1/files',
            params={"group_id": group_id, "resource_id": resource_id},
        )
        res = resp.raise_for_status().json()
        if not res.get("success"):
            raise RuntimeError(f'list_dir failed: {res}')
        return [FileInfo.model_validate(v) for v in res["data"]]

    @retry(stop=STOP_POLICY, reraise=True)
    async def upload_file(self, group_id: int, parent_id: int, file: 'FileTypes') -> FileInfo:
        r"""
        Upload a single file to a Cooper folder.

        *file* is passed as an ``httpx`` file value with field name ``"file"``
        added automatically.  Accepted forms:

        - ``IO[bytes]`` — raw file object; the filename in the multipart
          boundary is left empty.
        - ``(filename, IO[bytes])`` — file object with an explicit filename.
        - ``(filename, bytes)`` — in-memory bytes with a filename.

        Args:
            group_id: Cooper team group ID (visible in folder URL).
            parent_id: Cooper folder ID to upload into.
            file: An ``httpx`` :data:`~httpx._types.FileTypes` value.

        Returns:
            :class:`~cooper_types.FileInfo` for the newly uploaded file.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            RuntimeError: If the Cooper API returns ``success: false`` or more
                than one entry in ``data``.

        Examples:
            Raw file object::

                with open("report.pdf", "rb") as f:
                    info = await client.upload_file(GROUP_ID, PARENT_ID, f)

            Explicit filename::

                with open("report.pdf", "rb") as f:
                    info = await client.upload_file(GROUP_ID, PARENT_ID, ("custom-name.pdf", f))

            In-memory bytes::

                data = Path("report.pdf").read_bytes()
                info = await client.upload_file(GROUP_ID, PARENT_ID, ("report.pdf", data))

        Parameters:
            -
        """

        resp = await self._client.post(
            '/openapi/v1/files',
            params={"group_id": group_id},
            data={"parentid": parent_id},
            files=[("file", file)],  # NOTE: only one file allowed per request, but httpx requires a list of tuples
        )
        res = resp.raise_for_status().json()
        if not res.get("success"):
            raise RuntimeError(f'upload_file failed: {res}')
        if len(res["data"]) != 1:
            raise RuntimeError(
                f'upload_file: expected 1 item in response, got {len(res["data"])}: {res}'
            )
        return FileInfo.model_validate(res["data"][0])

    @retry(stop=STOP_POLICY, reraise=True)
    async def get_download_url(
        self,
        group_id: int,
        resource_ids: tp.Sequence[int],
    ) -> str:
        r"""
        Get a download URL for one or more Cooper files.

        If multiple file IDs are given, Cooper packs them into a ZIP archive.

        Args:
            group_id: Cooper team group ID.
            resource_id: Sequence of Cooper file IDs to download (from
                :meth:`list_dir`).

        Returns:
            Public download URL (``str``).  Points to a ZIP archive when
            multiple IDs are requested.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            RuntimeError: If the Cooper API returns ``success: false``.

        Examples:
            >>> client = CooperClient()
            >>> await_(client.get_download_url(2199094698523, [2207369729546]))
            'http://api-kylin.intra.xiaojukeji.com/EP_CLOUD_DISK_oe_openapi_cooper_server_prod/...name=download.zip...'

        """

        resp = await self._client.post(
            '/openapi/v1/files/downloads',
            params={"group_id": group_id},
            json={"ids": list(resource_ids)},
        )
        res = resp.raise_for_status().json()
        if not res.get("success"):
            raise RuntimeError(f'get_download_url failed: {res}')
        return f'{DEFAULT_BASE_URL}/{res["data"]["uri"]}'

    @retry(stop=STOP_POLICY, reraise=True)
    async def download(
        self,
        group_id: int,
        resource_ids: tp.Sequence[int],
        file_path: PathLikeStr,
    ):
        async with self._client.stream(
            'GET',
            await self.get_download_url(group_id, resource_ids),
            follow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            return await copy_to(resp.aiter_bytes(chunk_size=(1024**2 * 1)), file_path)

    @asynccontextmanager
    async def export_stream(
        self,
        resource_id: int,
    ) -> tp.AsyncGenerator[httpx.Response, None]:
        r"""
        Export a Cooper online document (协作文档) as an async byte stream.

        Returns an async context manager yielding an :class:`httpx.Response`
        whose body has **not** been read yet.  Use ``resp.aiter_bytes()`` or
        ``resp.aiter_lines()`` to consume the stream.

        Args:
            resource_id: Cooper file resource ID of the online document.

        Yields:
            :class:`httpx.Response` with status already verified.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.

        Examples:
            Consume as bytes::

                async with client.export_cooperate_stream(123) as resp:
                    async for chunk in resp.aiter_bytes():
                        process(chunk)

        Parameters:
            -
        """
        async with self._client.stream(
            'GET',
            f'/openapi/v1/cooperate/export/{resource_id}',
            follow_redirects=True,
        ) as resp:
            yield resp.raise_for_status()

    @retry(stop=STOP_POLICY, reraise=True)
    async def export(
        self,
        resource_id: int,
        file_path: PathLikeStr,
    ):
        r"""
        Export a Cooper online document (协作文档) to a local file or stdout.

        High-level convenience built on :meth:`export_stream`.
        Streams the response body directly into *file_path*. When *file_path*
        is ``'-'``, the bytes are written to stdout so the CLI can be piped
        into downstream tools like ``markitdown``. The resulting file or stream
        is in Office format (``.docx``, ``.xlsx``, …) depending on the
        document type.

        Args:
            resource_id: Cooper file resource ID of the online document.
            file_path: Local file path to write the exported document to. Pass
                ``'-'`` to stream to stdout instead. Parent directories are
                created automatically for real file paths.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.

        Examples:
            Download a Word document::

                await client.export(123456, '/tmp/report.docx')

            Pipe the Office bytes to another process::

                await client.export(123456, '-')

        Parameters:
            -
        """
        async with self.export_stream(resource_id) as resp:
            return await copy_to(resp.aiter_bytes(chunk_size=(1024**2 * 1)), file_path)


_default_client = CooperClient()


async def list_dir(*args, **kwds) -> list[FileInfo]:
    r"""
    Convenience wrapper for :meth:`CooperClient.list_dir` using a shared client.

    See :meth:`CooperClient.list_dir` for full method docs.

    Parameters:
        *args: Positional arguments passed to :meth:`CooperClient.list_dir`.
        **kwds: Keyword arguments passed to :meth:`CooperClient.list_dir`.
    """
    return await _default_client.list_dir(*args, **kwds)


async def upload_file(*args, **kwds) -> FileInfo:
    r"""
    Convenience wrapper for :meth:`CooperClient.upload_file` using a shared client.

    See :meth:`CooperClient.upload_file` for full method docs.

    Parameters:
        *args: Positional arguments passed to :meth:`CooperClient.upload_file`.
        **kwds: Keyword arguments passed to :meth:`CooperClient.upload_file`.
    """
    return await _default_client.upload_file(*args, **kwds)


async def get_download_url(*args, **kwds) -> str:
    r"""
    Convenience wrapper for :meth:`CooperClient.get_download_url` using a shared client.

    See :meth:`CooperClient.get_download_url` for full method docs.

    Parameters:
        *args: Positional arguments passed to :meth:`CooperClient.get_download_url`.
        **kwds: Keyword arguments passed to :meth:`CooperClient.get_download_url`.
    """
    return await _default_client.get_download_url(*args, **kwds)


async def download(*args, **kwds):
    r"""
    Convenience wrapper for :meth:`CooperClient.get_download_url` using a shared client.

    See :meth:`CooperClient.get_download_url` for full method docs.

    Parameters:
        *args: Positional arguments passed to :meth:`CooperClient.get_download_url`.
        **kwds: Keyword arguments passed to :meth:`CooperClient.get_download_url`.
    """
    return await _default_client.download(*args, **kwds)


def export_stream(*args, **kwds) -> tp.AsyncContextManager[httpx.Response]:
    r"""
    Convenience wrapper for :meth:`CooperClient.export_cooperate_stream` using a shared client.

    See :meth:`CooperClient.export_cooperate_stream` for full method docs.

    Parameters:
        *args: Positional arguments passed to :meth:`CooperClient.export_cooperate_stream`.
        **kwds: Keyword arguments passed to :meth:`CooperClient.export_cooperate_stream`.
    """
    return _default_client.export_stream(*args, **kwds)


async def export(*args, **kwds):
    r"""
    Convenience wrapper for :meth:`CooperClient.export_cooperate` using a shared client.

    See :meth:`CooperClient.export_cooperate` for full method docs.

    Parameters:
        *args: Positional arguments passed to :meth:`CooperClient.export_cooperate`.
        **kwds: Keyword arguments passed to :meth:`CooperClient.export_cooperate`.
    """
    return await _default_client.export(*args, **kwds)


if __name__ == '__main__':
    import os

    NAME: str = os.environ.setdefault("OTEL_SERVICE_NAME", "cooper-cli")
    ENV: str = os.getenv("OTEL_ENVIRONMENT_NAME", "prod")

    from conflog import configure_logging

    configure_logging()

    import asyncio
    import typer

    from ...utils.io_utils import (
        is_path_stdio,
        open_maybe_stdio,
    )

    app = typer.Typer(
        name='cooper-cli',
        help='Cooper 文件管理 CLI — 上传、列表、下载、导出协作文档。',
        no_args_is_help=True,
    )
    runner = asyncio.Runner()

    def _resolve_team_file_dir(
        url: tp.Optional[str],
        group_id: tp.Optional[int],
        resource_id: tp.Optional[int],
    ) -> tuple[int, int]:
        r"""Resolve (group_id, resource_id) from --url or positional args."""
        if url is not None:
            return parse_team_file_url(url)
        if group_id is None or resource_id is None:
            raise typer.BadParameter(
                'group_id and resource_id are required when --url is not given',
            )
        return (group_id, resource_id)

    def _resolve_upload_name(
        file_path: str,
        upload_name: tp.Optional[str],
    ) -> tuple[PathLikeStr, str]:
        r"""
        Resolve the upload source and multipart filename for CLI uploads.

        Args:
            file_path: Local file path or ``'-'`` for stdin.
            upload_name: Explicit multipart filename.

        Returns:
            ``(file_path, resolved_upload_name)``.

        Raises:
            ValueError: If stdin is used without an explicit upload name.
            FileNotFoundError: If the local path does not exist.
            IsADirectoryError: If the local path is not a regular file.
            PermissionError: If the local path is not readable.
        """
        if is_path_stdio(file_path):
            if upload_name is None:
                raise ValueError('upload_name is required when file_path is -')
            return (file_path, upload_name)

        file_path_ = Path(file_path)
        return (file_path_, upload_name or file_path_.name)

    @app.command()
    def ls(
        group_id: tp.Annotated[
            tp.Optional[int],
            typer.Argument(help='Cooper 团队 group_id'),
        ] = None,
        resource_id: tp.Annotated[
            tp.Optional[int],
            typer.Argument(help='目录 resource_id'),
        ] = None,
        *,
        url: tp.Annotated[
            tp.Optional[str],
            typer.Option(help='Cooper team-file URL'),
        ] = None,
    ):
        r"""列出 Cooper 目录下的文件。"""
        gid, rid = _resolve_team_file_dir(url, group_id, resource_id)
        items = runner.run(list_dir(gid, rid))
        for i in items:
            t = 'd' if i.has_child else 'f'
            t = f'{t}{i.type}'
            typer.echo(
                f'{i.id}\t{i.create_time}\t{t}\t{i.create_by_cn}\t{i.display_name}',
            )

    @app.command()
    def put(
        file_path: tp.Annotated[
            str,
            typer.Argument(help="本地文件路径；传 '-' 从 stdin 读取"),
        ] = '-',
        group_id: tp.Annotated[
            tp.Optional[int],
            typer.Argument(help='Cooper 团队 group_id'),
        ] = None,
        parent_id: tp.Annotated[
            tp.Optional[int],
            typer.Argument(help='上传目录 resource_id'),
        ] = None,
        *,
        url: tp.Annotated[
            tp.Optional[str],
            typer.Option(help='Cooper team-file URL'),
        ] = None,
        upload_name: tp.Annotated[
            tp.Optional[str],
            typer.Option('--name', '-n', help='上传时使用的文件名；stdin 模式必填'),
        ] = None,
    ):
        r"""上传文件到 Cooper 目录。"""
        gid, pid = _resolve_team_file_dir(url, group_id, parent_id)
        try:
            file_path_, upload_name_ = _resolve_upload_name(file_path, upload_name)
        except (ValueError,) as exc:
            raise typer.BadParameter(str(exc)) from exc
        with open_maybe_stdio(file_path_, 'rb') as f:
            info = runner.run(upload_file(gid, pid, (upload_name_, f)))
        typer.echo(f'{info.id}\t{info.display_name}')

    @app.command()
    def get(
        file_path: tp.Annotated[
            str,
            typer.Argument(help="保存到本地的文件路径；传 '-' 输出到 stdout"),
        ] = '-',
        group_id: tp.Annotated[
            tp.Optional[int],
            typer.Argument(help='Cooper 团队 group_id'),
        ] = None,
        resource_id: tp.Annotated[
            tp.Optional[list[int]],
            typer.Argument(help='一个或多个 resource_id'),
        ] = None,
        *,
        url: tp.Annotated[
            tp.Optional[str],
            typer.Option(help='Cooper team-file URL'),
        ] = None,
    ):
        r"""下载 Cooper 文件到本地或 stdout（多文件时返回 ZIP）。"""
        if url is not None:
            gid, rid = parse_team_file_url(url)
            rids = [rid]
        else:
            if group_id is None or resource_id is None:
                raise typer.BadParameter(
                    'group_id and resource_id required when --url not given',
                )
            gid = group_id
            rids = resource_id
        runner.run(download(gid, rids, file_path))
        if is_path_stdio(file_path): return  # fmt: skip
        size = Path(file_path).stat().st_size
        typer.echo(f'{file_path} ({size} bytes)')

    @app.command(name="export")
    def export_cmd(
        file_path: tp.Annotated[
            str,
            typer.Argument(help="保存到本地的文件路径；传 '-' 输出到 stdout"),
        ] = '-',
        resource_id: tp.Annotated[
            tp.Optional[int],
            typer.Argument(help='协作文档 resource_id'),
        ] = None,
        *,
        url: tp.Annotated[
            tp.Optional[str],
            typer.Option(help='Cooper 协作文档 URL'),
        ] = None,
    ):
        r"""导出 Cooper 协作文档到本地文件或 stdout（docx/xlsx 等）。"""
        if url is not None:
            rid = parse_docs2_url(url)
        elif resource_id is not None:
            rid = resource_id
        else:
            raise typer.BadParameter('resource_id or --url is required')
        runner.run(export(rid, file_path))
        if is_path_stdio(file_path): return  # fmt: skip
        size = Path(file_path).stat().st_size
        typer.echo(f'{file_path} ({size} bytes)')

    @app.command()
    def normalize_docx(
        input_path: tp.Annotated[
            str,
            typer.Argument(help="输入 DOCX 路径；默认 stdin；传 '-' 显式指定 stdin"),
        ] = '-',
        output_path: tp.Annotated[
            str,
            typer.Argument(help="输出 DOCX 路径；默认 stdout；传 '-' 显式指定 stdout"),
        ] = '-',
        *,
        default_style_type: tp.Annotated[
            str,
            typer.Option(help='补齐缺失 w:type 时使用的默认值'),
        ] = 'paragraph',
    ):
        r"""补齐 DOCX 自定义样式中缺失的 `w:type`。"""
        if (
            input_path == output_path
            and not is_path_stdio(input_path)
            and not is_path_stdio(output_path)
        ):
            raise typer.BadParameter('input_path and output_path must differ')
        with (
            open_maybe_stdio(input_path, 'rb') as input_file,
            open_maybe_stdio(output_path, 'wb') as output_file,
        ):
            patched_count = normalize_docx_file(
                input_file,
                output_file,
                default_style_type=default_style_type,
            )
        if is_path_stdio(output_path): return  # fmt: skip
        typer.echo(f'{output_path} (patched {patched_count} styles)', err=True)

    app()
