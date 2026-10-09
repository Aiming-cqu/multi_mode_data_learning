#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import io, os, shutil, sys, tempfile, typing as tp

from contextlib import contextmanager
from pathlib import Path


PathLikeStr = tp.Union[os.PathLike[str], str]


def is_path_stdio(path: PathLikeStr) -> bool:
    r"""
    Return whether *file_path* should map to stdio.

    Examples:
        >>> is_path_stdio('-')
        True
        >>> is_path_stdio('/tmp/report.docx')
        False
    """
    return os.fspath(path) == '-'


@tp.overload
def open_maybe_stdio(
    path: PathLikeStr, mode: tp.Literal['r', 'w', 'rt', 'wt'], **kwds
) -> tp.ContextManager[tp.TextIO]: ...


@tp.overload
def open_maybe_stdio(
    path: PathLikeStr, mode: tp.Literal['rb', 'wb'], **kwds
) -> tp.ContextManager[tp.BinaryIO]: ...


@contextmanager
def open_maybe_stdio(
    path: PathLikeStr = '-',
    mode: tp.Literal['r', 'w', 'rt', 'wt', 'rb', 'wb'] = 'r',
    **kwds
) -> tp.Union[tp.Generator[tp.BinaryIO, None, None], tp.Generator[tp.TextIO, None, None]]:
    r"""
    Open *path* as a regular file, or fall back to stdio when *path*
    is ``'-'``.

    For write modes the parent directories are created on demand.
    Extra *kwds* (``encoding``, ``newline``, …) are forwarded to
    :py:meth:`pathlib.Path.open`.

    Examples:
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     p = Path(tmp_dir) / 'in.bin'
        ...     _ = p.write_bytes(b'abc')
        ...     with open_maybe_stdio(p, 'rb') as f:
        ...         f.read()
        b'abc'

        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     p = Path(tmp_dir) / 'out.txt'
        ...     with open_maybe_stdio(p, 'w', encoding='utf-8') as f:
        ...         _ = f.write('hello\n')
        ...     p.read_text(encoding='utf-8')
        'hello\n'

        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     p = Path(tmp_dir) / 'out.bin'
        ...     with open_maybe_stdio(p, 'wb') as f:
        ...         n = f.write(b'xyz')
        ...     (n, p.read_bytes())
        (3, b'xyz')

        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     p = Path(tmp_dir) / 'in.txt'
        ...     _ = p.write_text('world\n', encoding='utf-8')
        ...     with open_maybe_stdio(p, encoding='utf-8') as f:
        ...         f.read()
        'world\n'
    """
    is_binary = 'b' in mode
    is_write = 'w' in mode

    if is_path_stdio(path):
        if is_write:
            stdio: tp.Any = sys.stdout.buffer if is_binary else sys.stdout
            yield stdio
            stdio.flush()
        else:
            yield sys.stdin.buffer if is_binary else sys.stdin
        return

    path_ = Path(path)
    if is_write: path_.parent.mkdir(parents=True, exist_ok=True)  # fmt: skip
    with path_.open(mode, **kwds) as f:
        yield f


async def copy_to_file(
    chunks: tp.AsyncIterator[bytes],
    file_path: PathLikeStr,
) -> int:
    r"""
    Write an async byte stream to a local file.

    Examples:
        >>> import tempfile
        >>> async def chunks():
        ...     yield b'co'
        ...     yield b'oper'
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     file_path = Path(tmp_dir) / 'out.bin'
        ...     n = await_(copy_to_file(chunks(), file_path))
        ...     (n, file_path.read_bytes())
        (6, b'cooper')
    """
    file_path_ = Path(file_path)
    file_path_.parent.mkdir(parents=True, exist_ok=True)
    ret = 0
    with file_path_.open('wb') as f:
        async for chunk in chunks:
            ret += f.write(chunk)
    return ret


async def copy_to_stdout(chunks: tp.AsyncIterator[bytes]) -> int:
    r"""Write an async byte stream to stdout."""
    stdout_buffer = sys.stdout.buffer
    ret = 0
    async for chunk in chunks:
        ret += stdout_buffer.write(chunk)
    stdout_buffer.flush()
    return ret


async def copy_to(
    chunks: tp.AsyncIterator[bytes],
    path: PathLikeStr,
) -> int:
    r"""
    Write an async byte stream to a local file or stdout.

    Examples:
        >>> import tempfile
        >>> async def chunks():
        ...     yield b'vlm'
        ...     yield b'-triage'
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     file_path = Path(tmp_dir) / 'out.bin'
        ...     n = await_(copy_to_file(chunks(), file_path))
        ...     (n, file_path.read_bytes())
        (10, b'vlm-triage')
    """
    if is_path_stdio(path): return await copy_to_stdout(chunks)  # fmt: skip
    return await copy_to_file(chunks, path)


@tp.overload
def ensure_seekable_input(
    readable: tp.BinaryIO,
    *,
    max_size: int,
) -> tp.ContextManager[tp.BinaryIO]: ...


@tp.overload
def ensure_seekable_input(
    readable: tp.TextIO,
    *,
    max_size: int,
) -> tp.ContextManager[tp.TextIO]: ...


@contextmanager
def ensure_seekable_input(
    readable: tp.Union[tp.BinaryIO, tp.TextIO],
    *,
    max_size: int = (1024**2 * 10),  # 10 MiB
) -> tp.Union[tp.Generator[tp.BinaryIO, None, None], tp.Generator[tp.TextIO, None, None]]:
    r"""
    Ensure an input stream is seekable.

    If the stream is already seekable it is yielded as-is; otherwise the
    content is spooled to a temporary file (binary or text, auto-detected
    via ``read(0)``).

    Examples:
        >>> import io
        >>> with ensure_seekable_input(io.BytesIO(b'abc')) as f:
        ...     (f.seekable(), f.read())
        (True, b'abc')

        >>> class NonSeekable:
        ...     def __init__(self, data: bytes):
        ...         self._buffer = io.BytesIO(data)
        ...
        ...     def read(self, size: int = -1) -> bytes:
        ...         return self._buffer.read(size)
        ...
        ...     def seekable(self) -> bool:
        ...         return False
        >>> with ensure_seekable_input(NonSeekable(b'xyz')) as f:
        ...     (f.seekable(), f.read())
        (True, b'xyz')

        >>> class NonSeekableText:
        ...     def __init__(self, data: str):
        ...         self._buffer = io.StringIO(data)
        ...
        ...     def read(self, size: int = -1) -> str:
        ...         return self._buffer.read(size)
        ...
        ...     def seekable(self) -> bool:
        ...         return False
        >>> with ensure_seekable_input(NonSeekableText('hello')) as f:
        ...     (f.seekable(), f.read())
        (True, 'hello')
    """
    if readable.seekable():
        yield readable
        return

    is_binary = isinstance(readable.read(0), bytes)
    mode = 'w+b' if is_binary else 'w+'
    with tempfile.SpooledTemporaryFile(max_size=max_size, mode=mode) as f:
        shutil.copyfileobj(readable, f)
        f.seek(0)
        yield f


# ---------------------------------------------------------------------------
# Sync: stream ↔ chunked iterator
# ---------------------------------------------------------------------------


def iter_chunks(
    readable: tp.BinaryIO,
    chunk_size: int = 8192,
) -> tp.Iterator[bytes]:
    r"""Read a binary stream in fixed-size chunks.

    Examples:
        >>> import io
        >>> list(iter_chunks(io.BytesIO(b'hello world'), chunk_size=5))
        [b'hello', b' worl', b'd']
        >>> list(iter_chunks(io.BytesIO(b'')))
        []
    """
    return iter(lambda: readable.read(chunk_size), b'')


class ChunkedReader(io.RawIOBase):
    r"""Adapt an ``Iterator[bytes]`` to a readable binary stream.

    The returned object is a valid ``BinaryIO`` (inherits
    ``io.RawIOBase``), so it can be passed anywhere a file-like
    object is expected — including ``shutil.copyfileobj`` and
    ``ensure_seekable_input``.

    Examples:
        >>> reader = ChunkedReader(iter([b'he', b'llo']))
        >>> reader.read()
        b'hello'
        >>> reader = ChunkedReader(iter([b'ab', b'cde', b'f']))
        >>> reader.read(4)
        b'abcd'
        >>> reader.read(4)
        b'ef'
        >>> reader.read(4)
        b''
    """

    def __init__(self, chunks: tp.Iterator[bytes]) -> None:
        super().__init__()
        self._chunks = chunks
        self._buf = bytearray()

    def readable(self) -> bool:
        return True

    def readinto(self, b: bytearray) -> int:  # type: ignore[override]
        while len(self._buf) < len(b):
            try:
                self._buf.extend(next(self._chunks))
            except StopIteration:
                break
        n = min(len(b), len(self._buf))
        b[:n] = self._buf[:n]
        del self._buf[:n]
        return n


# ---------------------------------------------------------------------------
# Async: stream ↔ chunked iterator
# ---------------------------------------------------------------------------


async def aiter_chunks(
    readable: tp.Any,
    chunk_size: int = 8192,
) -> tp.AsyncIterator[bytes]:
    r"""Read an async readable in fixed-size chunks.

    *reader* can be any object with an async ``read(n)`` method
    (``asyncio.StreamReader``, ``aiohttp.StreamReader``, etc.).

    Examples:
        >>> import io
        >>> class FakeReader:
        ...     def __init__(self, data: bytes):
        ...         self._buf = io.BytesIO(data)
        ...
        ...     async def read(self, n: int = -1) -> bytes:
        ...         return self._buf.read(n)
        >>> async def collect(reader, size=8192):
        ...     return [c async for c in aiter_chunks(reader, size)]
        >>> await_(collect(FakeReader(b'abcde'), 2))
        [b'ab', b'cd', b'e']
        >>> await_(collect(FakeReader(b'')))
        []
    """
    while chunk := await readable.read(chunk_size):
        yield chunk


class AsyncChunkedReader:
    r"""Adapt an ``AsyncIterator[bytes]`` to an async readable.

    Provides an async ``read(n)`` method compatible with interfaces
    that expect an async file-like object.

    Examples:
        >>> async def chunks():
        ...     yield b'he'
        ...     yield b'llo'
        >>> await_(AsyncChunkedReader(chunks()).read())
        b'hello'
        >>> async def chunks2():
        ...     yield b'ab'
        ...     yield b'cde'
        ...     yield b'f'
        >>> r = AsyncChunkedReader(chunks2())
        >>> await_(r.read(4))
        b'abcd'
        >>> await_(r.read(4))
        b'ef'
        >>> await_(r.read(4))
        b''
    """

    def __init__(self, chunks: tp.AsyncIterator[bytes]) -> None:
        self._chunks = chunks
        self._buf = bytearray()
        self._eof = False

    async def read(self, n: int = -1) -> bytes:
        if n < 0:
            while not self._eof:
                try:
                    self._buf.extend(await self._chunks.__anext__())
                except StopAsyncIteration:
                    self._eof = True
            ret = bytes(self._buf)
            self._buf.clear()
            return ret

        while len(self._buf) < n and not self._eof:
            try:
                self._buf.extend(await self._chunks.__anext__())
            except StopAsyncIteration:
                self._eof = True

        ret = bytes(self._buf[:n])
        del self._buf[:n]
        return ret
