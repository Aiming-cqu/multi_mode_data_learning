#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import asyncio, logging, inspect, io, os, typing as tp, weakref

from functools import partial, wraps

if tp.TYPE_CHECKING:
    from concurrent.futures import Executor


_T = tp.TypeVar('_T')  # Any type
_R = tp.TypeVar('_R')  # Result type
_ACM = tp.TypeVar('_ACM', bound=tp.AsyncContextManager)  # Async context manager type
_P = tp.ParamSpec('_P')

logger: logging.Logger = logging.getLogger(name=__name__)
runner = asyncio.Runner()


async def async_run(
    func: tp.Callable[_P, _R],
    /,
    *args: _P.args,
    run_in_executor: tp.Optional[tp.Union[tp.Literal[False], 'Executor']] = None,
    **kwds: _P.kwargs,
) -> _R:
    r"""
    在异步上下文中运行同步函数。

    根据参数选择不同的执行方式：优先使用线程执行，其次使用 executor，
    或者直接阻塞调用。

    Note:
        explicitly mark as async for `coroutinefunction` !!!

    Args:
        func: 要执行的同步函数。
        *args: 传递给 func 的位置参数。
        to_thread: 是否使用 asyncio.to_thread 在线程中执行函数。默认为 True。
        run_in_executor: 当 to_thread 为 False 时，是否使用 executor 执行。默认为 True。
        executor: 可选的 executor 实例，用于 run_in_executor 模式。
        **kwds: 传递给 func 的关键字参数。

    Returns:
        函数执行的结果。

    Examples:
        >>> inspect.iscoroutinefunction(async_run)
        True
        >>> def add(x, y):
        ...     return x + y
        >>> await_(async_run(add, 10, 20))
        30
    """

    if run_in_executor is None:
        logger.debug('async_run with to_thread')
        return await asyncio.to_thread(func, *args, **kwds)
    if not run_in_executor:
        logger.debug('async_run blocking')
        return func(*args, **kwds)
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    logger.debug('async_run with executor for running loop %r', loop)
    return await loop.run_in_executor(run_in_executor, partial(func, **kwds), *args)


def sync_run(
    func: tp.Callable[_P, tp.Coroutine[None, None, _R]],
    /,
    *args: _P.args,
    **kwds: _P.kwargs,
) -> _R:
    r"""
    在同步上下文中运行异步协程。

    如果没有运行中的事件循环，使用 asyncio.run 执行；
    如果已有运行中的事件循环，使用 loop.run_until_complete 执行。

    Args:
        func: 返回协程的可调用对象。
        *args: 传递给 func 的位置参数。
        **kwds: 传递给 func 的关键字参数。

    Returns:
        协程执行的结果。

    Examples:
        >>> async def add(x, y):
        ...     return x + y
        >>> sync_run(add, 10, 20)
        30
        >>> import nest_asyncio
        >>> nest_asyncio.apply()
        >>> async def gcd(x, y):
        ...     if y == 0:
        ...         return x
        ...     return sync_run(gcd, y, x % y)
        >>> sync_run(gcd, 9, 6)
        3
    """
    try:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    except (RuntimeError,):
        logger.debug('sync_run with runner')
        return runner.run(func(*args, **kwds))
    else:
        logger.debug('sync_run with running loop %r', loop)
        return loop.run_until_complete(func(*args, **kwds))


async def to_awaitable(x: _T) -> _T:
    r"""
    将值包装为可等待对象。

    Args:
        x: 要包装的值。

    Returns:
        返回输入值本身（在异步函数中）。
    """
    return x


async def ensure_awaitable(x: tp.Union[_T, tp.Awaitable[_T]]) -> _T:
    r"""
    确保值是可等待的，如果是可等待对象则等待，否则直接返回。

    Args:
        x: 值或可等待对象。

    Returns:
        解包后的值。

    Examples:
        >>> await_(ensure_awaitable(10))
        10
        >>> async def coro():
        ...     return 10
        >>> await_(ensure_awaitable(coro()))
        10
    """

    if inspect.isawaitable(x): return await x  # fmt: skip
    return x


def to_async(
    func: tp.Callable[_P, _R], **async_kwds
) -> tp.Callable[_P, tp.Coroutine[tp.Any, tp.Any, _R]]:
    r"""
    将同步函数转换为异步函数。

    返回的异步函数内部使用 async_run 执行原始同步函数。

    Args:
        func: 要转换的同步函数。
        **async_kwds: 传递给 async_run 的关键字参数。

    Returns:
        返回异步函数包装器。

    Examples:
        >>> def add(x, y):
        ...     return x + y
        >>> inspect.iscoroutinefunction(to_async(add))
        True
        >>> await_(to_async(add)(10, 20))
        30
        >>> await_(to_async(add, run_in_executor=False)(10, 20))
        30
    """

    return wraps(func)(partial(async_run, func, **async_kwds))


def ensure_async(
    func: tp.Callable[_P, tp.Union[_R, tp.Coroutine[None, None, _R]]], **async_kwds
) -> tp.Callable[_P, tp.Coroutine[tp.Any, tp.Any, _R]]:
    r"""
    确保函数是异步的。

    如果输入已经是协程函数，直接返回；否则使用 to_async 转换为异步函数。

    Args:
        func: 同步函数或协程函数。
        **async_kwds: 传递给 to_async 的关键字参数（当需要转换时）。

    Returns:
        协程函数。

    Examples:
        >>> def sync_add(x, y):
        ...     return x + y
        >>> inspect.iscoroutinefunction(to_async(sync_add))
        True
        >>> await_(ensure_async(sync_add)(10, 20))
        30
        >>> async def async_add(x, y):
        ...     return x + y
        >>> await_(ensure_async(async_add, run_in_executor=False)(10, 20))
        30
    """

    if inspect.iscoroutinefunction(func): return func  # fmt: skip
    func = tp.cast(tp.Callable[_P, _R], func)
    return to_async(func, **async_kwds)


def mapa(
    func: tp.Callable[[_T], tp.Union[_R, tp.Coroutine[None, None, _R]]],
    it: tp.Iterable[tp.Awaitable[_T]],
    **async_kwds,
) -> tp.Iterator[tp.Coroutine[tp.Any, tp.Any, _R]]:
    r"""
    在可等待对象的可迭代集合上映射函数。

    对输入可迭代对象中的每个可等待对象进行等待，然后将结果传递给 func 处理。

    Args:
        func: 要映射的函数，可以是同步或异步函数。
        it: 可等待对象的可迭代集合。
        **async_kwds: 传递给 ensure_async 的关键字参数。

    Returns:
        协程迭代器，每个协程执行 func 并返回结果。
    """

    afunc: tp.Callable[[_T], tp.Awaitable[_R]] = ensure_async(func, **async_kwds)

    async def wrapper(x):
        return await afunc(await x)

    return map(wrapper, it)


async def test_mapa():
    def sync_sqr(x):
        return x * x

    async def async_sqr(x):
        return x * x

    coros = list(mapa(sync_sqr, list(map(to_awaitable, range(3)))))
    assert (await asyncio.gather(*coros)) == [0, 1, 4]
    coros = list(mapa(async_sqr, list(map(to_awaitable, range(3)))))
    assert (await asyncio.gather(*coros)) == [0, 1, 4]


async def amap(
    func: tp.Callable[[_T], tp.Awaitable[_R]],
    it: tp.AsyncIterable[tp.Union[_T, tp.Awaitable[_T]]],
) -> tp.AsyncIterator[_R]:
    r"""
    在异步可迭代对象上映射异步函数。

    异步遍历输入的可迭代对象，对每个元素（如果是可等待对象则等待）
    应用 func 函数，产生结果。

    Args:
        func: 异步映射函数。
        it: 异步可迭代对象，元素可以是值或可等待对象。

    Returns:
        异步结果迭代器。
    """

    async for i in it:
        yield await func(await ensure_awaitable(i))


async def test_amap():
    async def async_sqr(x):
        return x * x

    async def f():
        for i in range(3):
            yield i

    async def g():
        for i in range(3):
            yield to_awaitable(i)

    res = []
    async for i in amap(async_sqr, f()):
        res.append(i)
    assert res == [0, 1, 4], res
    res = []
    async for i in amap(async_sqr, g()):
        res.append(i)
    assert res == [0, 1, 4], res


async def amapa(
    func: tp.Callable[[_T], tp.Union[_R, tp.Coroutine[None, None, _R]]],
    it: tp.AsyncIterable[tp.Union[_T, tp.Awaitable[_T]]],
    **async_kwds,
) -> tp.AsyncIterator[tp.Coroutine[tp.Any, tp.Any, _R]]:
    r"""
    在异步可迭代对象上映射任意函数（同步或异步）。

    异步遍历输入的可迭代对象，对每个元素（如果是可等待对象则等待）
    应用 func 函数。func 可以是同步或异步函数，会被自动处理。

    Args:
        func: 要映射的函数，可以是同步或异步函数。
        it: 异步可迭代对象，元素可以是值或可等待对象。
        **async_kwds: 传递给 ensure_async 的关键字参数。

    Returns:
        协程异步迭代器，每个协程执行 func 并返回结果。
    """

    afunc: tp.Callable[[_T], tp.Awaitable[_R]] = ensure_async(func, **async_kwds)

    async for i in it:
        yield await afunc(await ensure_awaitable(i))


async def test_amapa():
    def sync_sqr(x):
        return x * x

    async def async_sqr(x):
        return x * x

    async def f():
        for i in range(3):
            yield i

    async def g():
        for i in range(3):
            yield to_awaitable(i)

    res = []
    async for i in amapa(async_sqr, f()):
        res.append(i)
    assert res == [0, 1, 4], res
    res = []
    async for i in amapa(sync_sqr, g(), run_in_executor=False):
        res.append(i)
    assert res == [0, 1, 4], res


FileType: tp.TypeAlias = tp.Union[int, str, bytes, os.PathLike[str], os.PathLike[bytes]]


@tp.overload
def read_file_sync(file: FileType, mode: tp.Literal['r', 'rt'] = 'r', **open_kwds) -> str: ...


@tp.overload
def read_file_sync(file: FileType, mode: tp.Literal['rb'], **open_kwds) -> bytes: ...


def read_file_sync(file: FileType, *args, **open_kwds) -> tp.Union[str, bytes]:
    r"""
    同步读取文件内容。

    Args:
        file: 文件路径或文件描述符。
        *args: 额外的参数，可以包含模式和读取参数。
        **open_kwds: 传递给 open 函数的关键字参数。

    Returns:
        文件内容；文本模式返回 str，二进制模式返回 bytes。
    """
    match args:
        case [str() as mode, *read_args]: pass  # fmt: skip
        case _ as read_args: mode: str = "r"  # fmt: skip
    with open(file, mode, **open_kwds) as f: return f.read(*read_args)  # fmt: skip


@tp.overload
async def read_file_async(
    file: FileType, mode: tp.Literal['r', 'rt'] = 'r', **open_kwds
) -> str: ...


@tp.overload
async def read_file_async(file: FileType, mode: tp.Literal['rb'], **open_kwds) -> bytes: ...


async def read_file_async(file: FileType, *args, **open_kwds) -> tp.Union[str, bytes]:
    r"""
    异步读取文件内容。

    在后台线程中执行 read_file_sync 函数。

    Args:
        file: 文件路径或文件描述符。
        *args: 额外的参数，可以包含模式和读取参数。
        **open_kwds: 传递给 open 函数的关键字参数。

    Returns:
        文件内容；文本模式返回 str，二进制模式返回 bytes。
    """
    return await async_run(read_file_sync, file, *args, **open_kwds)


@tp.overload
async def aread(file: tp.TextIO, *args) -> str: ...


@tp.overload
async def aread(file: tp.BinaryIO, *args) -> bytes: ...


async def aread(file: tp.Union[tp.TextIO, tp.BinaryIO], *args) -> tp.Union[str, bytes]:
    r"""
    异步读取已打开文件对象的内容。

    Args:
        file: 已打开的文件对象。
        *args: 传递给 file.read 的参数。

    Returns:
        读取的文件内容。
    """
    return await async_run(file.read, *args)


@tp.overload
async def apread(
    file: tp.TextIO,
    offset: int,
    *read_args,
    whence: int = 0,
    lock: tp.Optional[asyncio.Lock] = None,
) -> str: ...


@tp.overload
async def apread(
    file: tp.BinaryIO,
    offset: int,
    *read_args,
    whence: int = 0,
    lock: tp.Optional[asyncio.Lock] = None,
) -> bytes: ...


async def apread(
    file: tp.Union[tp.TextIO, tp.BinaryIO],
    offset: int,
    *read_args,
    whence: int = 0,
    lock: tp.Optional[asyncio.Lock] = None,
) -> tp.Union[str, bytes]:
    r"""
    异步定位并读取文件内容。

    先定位到指定偏移位置，然后读取内容。可选使用锁进行同步。

    Args:
        file: 已打开的文件对象。
        offset: 定位偏移量。
        *read_args: 传递给 file.read 的参数。
        whence: 定位模式（0=文件开头，1=当前位置，2=文件末尾）。默认为 0。
        lock: 可选的异步锁，用于同步访问。默认为 None。

    Returns:
        读取的文件内容。
    """

    def f():
        file.seek(offset, whence)
        return file.read(*read_args)

    if lock is None: return await async_run(f)  # fmt: skip
    async with lock: return await async_run(f)  # fmt: skip


@tp.overload
def write_file_sync(file: FileType, data: tp.Union[str, bytes], **open_kwds) -> int: ...


@tp.overload
def write_file_sync(
    file: FileType, mode: tp.Literal['w', 'a', 'x', 'wt', 'at', 'xt'], data: str, **open_kwds
) -> int: ...


@tp.overload
def write_file_sync(
    file: FileType, mode: tp.Literal['wb', 'ab', 'xb'], data: bytes, **open_kwds
) -> int: ...


def write_file_sync(
    file: FileType,
    arg1: tp.Union[str, bytes, tp.Literal['w', 'a', 'x', 'wt', 'at', 'xt', 'wb', 'ab', 'xb']],
    *args,
    **open_kwds,
) -> int:
    r"""
    同步写入文件内容。

    根据参数自动推断写入模式（文本或二进制）。

    Args:
        file: 文件路径或文件描述符。
        arg1: 写入的数据或模式（如果指定了模式）。
        *args: 额外的参数。
        **open_kwds: 传递给 open 函数的关键字参数。

    Returns:
        写入的字节数或字符数。
    """
    mode: str = "w"
    match args:
        case [*args, data]:
            mode = arg1
        case _:
            data: tp.Union[str, bytes] = arg1
            match data:
                case str(): pass  # fmt: skip
                case _: mode = "wb"  # fmt: skip
    with open(file, mode, *args, **open_kwds) as f: return f.write(data)  # fmt: skip


@tp.overload
async def write_file_async(file: FileType, data: tp.Union[str, bytes], **open_kwds) -> int: ...


@tp.overload
async def write_file_async(
    file: FileType, mode: tp.Literal['w', 'a', 'x', 'wt', 'at', 'xt'], data: str, **open_kwds
) -> int: ...


@tp.overload
async def write_file_async(
    file: FileType, mode: tp.Literal['wb', 'ab', 'xb'], data: bytes, **open_kwds
) -> int: ...


async def write_file_async(
    file: FileType,
    arg1: tp.Union[str, bytes, tp.Literal['w', 'a', 'x', 'wt', 'at', 'xt', 'wb', 'ab', 'xb']],
    *args,
    **open_kwds,
) -> int:
    r"""
    异步写入文件内容。

    在后台线程中执行 write_file_sync 函数。

    Args:
        file: 文件路径或文件描述符。
        arg1: 写入的数据或模式（如果指定了模式）。
        *args: 额外的参数。
        **open_kwds: 传递给 open 函数的关键字参数。

    Returns:
        写入的字节数或字符数。
    """
    return await async_run(write_file_sync, file, arg1, *args, **open_kwds)


@tp.overload
async def awrite(file: tp.TextIO, data: str) -> int: ...


@tp.overload
async def awrite(file: tp.BinaryIO, data: bytes) -> int: ...


async def awrite(file: tp.Union[tp.TextIO, tp.BinaryIO], data: tp.Union[str, bytes]) -> int:
    r"""
    异步写入已打开文件对象。

    Args:
        file: 已打开的文件对象。
        data: 要写入的数据。

    Returns:
        写入的字节数或字符数。
    """
    return await async_run(file.write, data)


@tp.overload
async def apwrite(
    file: tp.TextIO,
    offset: int,
    data: str,
    whence: int = 0,
    lock: tp.Optional[asyncio.Lock] = None,
) -> int: ...


@tp.overload
async def apwrite(
    file: tp.BinaryIO,
    offset: int,
    data: bytes,
    whence: int = 0,
    lock: tp.Optional[asyncio.Lock] = None,
) -> int: ...


async def apwrite(
    file: tp.Union[tp.TextIO, tp.BinaryIO],
    offset: int,
    data: tp.Union[str, bytes],
    whence: int = 0,
    lock: tp.Optional[asyncio.Lock] = None,
) -> int:
    r"""
    异步定位并写入文件内容。

    先定位到指定偏移位置，然后写入内容。可选使用锁进行同步。

    Args:
        file: 已打开的文件对象。
        offset: 定位偏移量。
        data: 要写入的数据。
        whence: 定位模式（0=文件开头，1=当前位置，2=文件末尾）。默认为 0。
        lock: 可选的异步锁，用于同步访问。默认为 None。

    Returns:
        写入的字节数或字符数。
    """

    def f():
        file.seek(offset, whence)
        return file.write(data)

    if lock is None: return await async_run(f)  # fmt: skip
    async with lock: return await async_run(f)  # fmt: skip


async def test_async_file_ops():
    from tempfile import NamedTemporaryFile

    content = 'hello world'

    with NamedTemporaryFile(mode="w+", delete=False) as tmpfile:
        path = tmpfile.name

        assert (await write_file_async(path, content)) == len(content)
        assert (await read_file_async(path)) == content

        with open(path, "rb+") as f:
            assert (await apwrite(f, 1, b'elon')) == 4

        with open(path, "rb") as f:
            assert (await apread(f, 1)) == b'elon world'


class LoopLocal(tp.Generic[_T]):
    r"""
    事件循环本地存储。

    为每个事件循环维护一个独立的对象实例，类似于线程本地存储但用于异步事件循环。
    使用弱引用字典自动清理已关闭事件循环的缓存。

    Attributes:
        _factory: 用于创建新实例的工厂函数。
        _default: 默认实例（在没有运行事件循环时使用）。
        _cache: 事件循环到实例的映射缓存。
    """

    __slots__ = ("_factory", "_default", "_cache")

    _factory: tp.Callable[[], _T]
    _default: _T
    _cache: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _T]

    def __new__(cls, func: tp.Callable[_P, _T], *args: _P.args, **kwds: _P.kwargs) -> tp.Self:
        r"""
        创建 LoopLocal 实例。

        Args:
            func: 工厂函数，用于创建每个事件循环的实例。
            *args: 传递给工厂函数的位置参数。
            **kwds: 传递给工厂函数的关键字参数。

        Returns:
            LoopLocal 实例。
        """
        obj = super().__new__(cls)
        obj._factory = partial(func, *args, **kwds)
        obj._default = obj._factory()
        obj._cache = weakref.WeakKeyDictionary()
        return obj

    def get(self) -> _T:
        r"""
        获取当前事件循环的实例。

        如果没有运行的事件循环，返回默认实例；
        如果当前事件循环没有缓存实例，则使用工厂函数创建并缓存。

        Returns
        -------
        _T
            当前事件循环（或默认）的实例。
        """
        try:
            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        except (RuntimeError,):
            return self._default
        try:
            return self._cache[loop]
        except (KeyError,):
            logger.debug('call %r on running loop %r', self._factory, loop)
            self._cache[loop] = value = self._factory()  # type: _T
            return value

    async def aclose(self):
        r"""
        异步关闭所有缓存的实例。

        遍历所有缓存的实例，如果实例有 aclose 方法则调用它。
        """
        for value in self._cache.values():
            try: await value.aclose()  # type: ignore # fmt: skip
            except (AttributeError, TypeError): pass  # fmt: skip


class LoopBoundContextManager(tp.Generic[_P, _ACM]):
    r"""``asyncio.Semaphore`` wrapper safe to use as ``ClassVar``.

    Standard ``asyncio.Semaphore`` lazily binds to the running event loop on
    first ``acquire``.  If the loop is later replaced (e.g. pytest-asyncio
    creates a fresh loop per test), subsequent usage raises
    ``RuntimeError: … bound to a different event loop``.

    This wrapper detects the loop change and transparently re-creates the
    underlying semaphore.

    Examples:
        >>> sem = LoopBoundContextManager(asyncio.Semaphore, value=2)
        >>> async def demo():
        ...     async with sem:
        ...         return 'ok'
        >>> runner.run(demo())
        'ok'
    """

    __slots__ = ('_factory', '_obj', '_loop')

    def __init__(
        self, factory: tp.Callable[_P, _ACM], *args: _P.args, **kwds: _P.kwargs
    ) -> None:
        self._factory = partial(factory, *args, **kwds)
        self._obj: tp.Optional[_ACM] = None
        self._loop: tp.Optional[asyncio.AbstractEventLoop] = None

    def _get(self) -> _ACM:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._obj = self._factory()
            self._loop = loop
        else:
            assert self._obj is not None
        return self._obj

    async def __aenter__(self) -> 'LoopBoundContextManager':
        return await self._get().__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._get().__aexit__(exc_type, exc_val, exc_tb)

    def __repr__(self) -> str:
        if self._obj is None: return f'{type(self).__name__}(factory={self._factory!r})'  # fmt: skip
        return f'{type(self).__name__}(obj={self._obj!r})'


if __name__ == '__main__':
    from conflog import configure_logging

    configure_logging(env="test")

    sync_run(test_amap)
    sync_run(test_amapa)
    sync_run(test_async_file_ops)
