#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import abc, dataclasses as dc, hashlib, logging, os, threading, typing as tp, uuid, weakref
import httpx

from collections import OrderedDict, defaultdict
from contextlib import contextmanager

from functools import cached_property
from pathlib import Path
from typing_extensions import override

from ...utils.async_utils import sync_run, read_file_async, write_file_async
from ...utils.io_utils import copy_to_file
from ..session import SessionIdType, Session, SessionContextManager


_T = tp.TypeVar('_T')

ResourceIdType: tp.TypeAlias = str

CACHE_DIR: Path = Path(os.environ['TRIAGE_CACHE_DIR'])

hash_func: tp.Callable[[bytes], str] = lambda x: hashlib.blake2b(x, digest_size=6).hexdigest()

logger: logging.Logger = logging.getLogger(name=__name__)
local: threading.local = threading.local()

_http_client = httpx.AsyncClient()


class StorageBase:
    r"""
    存储基类，定义资源存储的标准接口。

    所有具体的存储实现（内存、文件、HTTP等）都应继承此类。
    提供资源转换、ID生成和资源清理的基础功能。
    """

    @classmethod
    async def from_resource(
        cls,
        resource: Resource,
        exclude: tp.Collection[type[StorageBase]] = tuple(),
    ) -> tp.Self:
        r"""
        从资源创建存储实例。

        Args:
            resource: 源资源对象
            exclude: 排除的存储类型集合，避免循环转换

        Returns:
            存储实例

        Raises:
            NotImplementedError: 如果子类未实现此方法
        """
        raise NotImplementedError('Not implemented')

    def __del__(self):
        try: self.close()  # fmt: skip
        except: pass  # noqa # fmt: skip

    async def to_resource(self, name: str, mime_type: str, **kwds) -> Resource:
        r"""
        将存储转换为资源对象。

        Args:
            name: 资源名称
            mime_type: MIME类型，如 "image/jpeg"
            **kwds: 额外的资源属性

        Returns:
            资源对象
        """
        return Resource(
            id=(await self.make_id()),
            name=name,
            mime_type=mime_type,
            storages={type(self): self},
            **kwds
        )

    async def make_id(self) -> ResourceIdType:
        r"""
        生成资源唯一标识符。

        Returns:
            资源ID字符串

        Raises:
            NotImplementedError: 如果子类未实现此方法
        """
        raise NotImplementedError('Not implemented')

    def close(self):
        r"""
        关闭存储，清理资源。

        子类应重写此方法以实现特定的资源清理逻辑。
        """
        pass


StorageT = tp.TypeVar('StorageT', bound=StorageBase)


@dc.dataclass(frozen=True, slots=True)
class ReferenceStorage(StorageBase, tp.Generic[_T]):
    r"""
    引用存储类，用于包装任意对象的引用。

    通过对象ID生成资源标识，不存储实际内容。

    Args:
        ref: 任意类型的对象引用
    """

    ref: _T

    @override
    async def make_id(self) -> ResourceIdType:
        r"""
        基于对象内存地址生成ID。

        Returns:
            12位十六进制字符串形式的对象ID
        """
        return f'{id(self.ref):012x}'


@dc.dataclass(frozen=True, slots=True)
class MemoryStorage(StorageBase):
    r"""
    内存存储类，将资源内容保存在内存中。

    支持从文件存储或HTTP存储转换而来。

    Args:
        content: 资源的二进制内容
    """

    content: bytes

    @override
    @classmethod
    async def from_resource(
        cls,
        resource: Resource,
        exclude: tp.Collection[type[StorageBase]] = tuple(),
    ) -> tp.Self:
        r"""
        从资源创建内存存储实例。

        优先尝试从FileStorage或HTTPStorage读取内容。

        Args:
            resource: 源资源对象
            exclude: 排除的存储类型集合

        Returns:
            内存存储实例
        """
        if storage := await resource.get(storage_type=FileStorage, no_convert=True):
            return cls(content=(await read_file_async(storage.path, "rb")))
        if storage := await resource.get(storage_type=HTTPStorage, no_convert=True):
            resp: httpx.Response = await _http_client.get(storage.url, follow_redirects=True)
            return cls(content=resp.raise_for_status().content)
        exclude_ = set(exclude)
        exclude_.add(cls)
        if FileStorage not in exclude:
            if storage := await resource.get(storage_type=FileStorage, no_convert=exclude_):
                return cls(content=(await read_file_async(storage.path, "rb")))
        return await super().from_resource(resource, exclude=exclude)

    @override
    async def make_id(self) -> ResourceIdType:
        r"""
        基于内容哈希生成ID。

        Returns:
            内容的blake2b哈希值（12字符十六进制）
        """
        return hash_func(self.content)


@dc.dataclass(frozen=True, slots=True)
class FileStorage(StorageBase):
    r"""
    文件存储类，将资源内容保存在本地文件系统中。

    支持从内存存储转换而来，自动管理缓存目录。

    Args:
        path: 文件的绝对路径
    """

    path: Path
    managed: bool = False

    @override
    @classmethod
    async def from_resource(
        cls,
        resource: Resource,
        exclude: tp.Collection[type[StorageBase]] = tuple(),
    ) -> tp.Self:
        r"""
        从资源创建文件存储实例。

        如果资源有内存存储，则写入缓存目录。

        Args:
            resource: 源资源对象
            exclude: 排除的存储类型集合

        Returns:
            文件存储实例
        """
        exclude_ = set(exclude)
        exclude_.add(cls)
        if HTTPStorage not in exclude_:
            if storage := await resource.get(storage_type=HTTPStorage, no_convert=exclude_):
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                path = cls.make_path(resource.id, resource.format)
                async with _http_client.stream(
                    'GET',
                    storage.url,
                    follow_redirects=True,
                ) as resp:
                    resp.raise_for_status()
                    await copy_to_file(resp.aiter_bytes(chunk_size=(1024**2 * 1)), path)
                return cls(path=path, managed=True)
        if MemoryStorage not in exclude_:
            if storage := await resource.get(storage_type=MemoryStorage, no_convert=exclude_):
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                path: Path = cls.make_path(resource.id, resource.format)
                await write_file_async(path, "wb", storage.content)
                return cls(path=path, managed=True)
        return await super().from_resource(resource, exclude=exclude)

    @classmethod
    def make_filename(cls, resource_id: ResourceIdType, fmt: str) -> str:
        r"""
        生成文件名。

        Args:
            resource_id: 资源ID
            fmt: 文件格式扩展名

        Returns:
            格式为 "{resource_id}.{fmt}" 的文件名

        Examples:
            >>> FileStorage.make_filename('abc123', 'jpg')
            'abc123.jpg'
            >>> FileStorage.make_filename('xyz', 'mp4')
            'xyz.mp4'
        """
        return f'{resource_id}.{fmt}'

    @classmethod
    def make_path(cls, resource_id: ResourceIdType, fmt: str) -> Path:
        r"""
        生成文件的完整路径。

        Args:
            resource_id: 资源ID
            fmt: 文件格式扩展名

        Returns:
            缓存目录下的完整文件路径
        """
        return CACHE_DIR / cls.make_filename(resource_id, fmt)

    @cached_property
    def format(self) -> str:
        r"""
        从文件路径提取扩展名。

        Returns:
            文件扩展名（包含点号）
        """
        return self.path.suffix

    @cached_property
    def url(self) -> str:
        r"""
        生成文件的URL。

        Returns:
            file:// 协议开头的绝对路径URL
        """
        return self.path.resolve().as_uri()

    @override
    async def to_resource(self, name: str, mime_type: str = '', **kwds) -> Resource:
        r"""
        转换为资源对象，自动推断MIME类型。

        Args:
            name: 资源名称
            mime_type: MIME类型，如未提供则使用文件扩展名
            **kwds: 额外的资源属性

        Returns:
            资源对象
        """
        return await super().to_resource(name, mime_type=(mime_type or self.format), **kwds)

    @override
    async def make_id(self) -> ResourceIdType:
        r"""
        基于文件路径哈希生成ID。

        Returns:
            路径的blake2b哈希值（12字符十六进制）
        """
        if self.managed: return ResourceIdType(self.path.with_suffix(''))  # fmt: skip
        return hash_func(self.path.as_posix().encode())

    @override
    def close(self):
        r"""
        删除文件，清理资源。
        """
        if not self.managed: return  # fmt: skip
        logger.debug('remove file %r', self.path)
        self.path.unlink()


@dc.dataclass(frozen=True, slots=True)
class HTTPStorage(StorageBase):
    r"""
    HTTP存储类，表示通过URL访问的远程资源。

    Args:
        url: 资源的HTTP/HTTPS URL
    """

    url: str

    @cached_property
    def mime_type(self) -> str:
        r"""
        同步获取资源的MIME类型。

        Returns:
            从HTTP响应头提取的MIME类型
        """
        return sync_run(self.get_mime_type)

    @override
    async def to_resource(self, name: str, mime_type: str = '', **kwds) -> Resource:
        r"""
        转换为资源对象，自动获取MIME类型。

        Args:
            name: 资源名称
            mime_type: MIME类型，如未提供则通过HEAD请求获取
            **kwds: 额外的资源属性

        Returns:
            资源对象
        """
        return await super().to_resource(
            name, mime_type=(mime_type or (await self.get_mime_type())), **kwds
        )

    @override
    async def make_id(self) -> ResourceIdType:
        r"""
        基于URL哈希生成ID。

        Returns:
            URL的blake2b哈希值（12字符十六进制）
        """
        return hash_func(self.url.encode())

    async def get_mime_type(self) -> str:
        r"""
        通过HEAD请求获取资源的MIME类型。

        Returns:
            Content-Type头的主类型（不包含charset等参数）

        Raises:
            httpx.HTTPStatusError: 如果HTTP请求失败
        """
        resp: httpx.Response = await _http_client.head(self.url, follow_redirects=True)
        return resp.raise_for_status().headers['Content-Type'].partition(';')[0]


@dc.dataclass(frozen=True, slots=True, weakref_slot=True)
class Resource:
    r"""
    资源类，表示具有多种存储形式的统一资源抽象。

    资源可以存在于多种存储形式中（内存、文件、HTTP等），
    并自动注册到当前会话的资源仓库。

    Args:
        id: 资源唯一标识符，默认自动生成UUID
        name: 资源名称
        mime_type: MIME类型，如 "image/jpeg"
        metadata: 资源的元数据字典
        storages: 存储类型到存储实例的映射

    Attributes:
        id (ResourceIdType): 资源唯一标识符
        name (str): 资源名称
        mime_type (str): MIME类型
        metadata (tp.Mapping[str, tp.Any]): 元数据字典
        storages (dict[tp.Type[StorageBase], StorageBase]): 存储映射
    """

    id: ResourceIdType = dc.field(default_factory=(lambda: uuid.uuid4().hex[:12]), kw_only=True)
    name: str
    mime_type: str = dc.field(metadata={'doc': 'type/format, e.g., "image/jpeg"'})  # NOTE: py<3.14 compat
    metadata: tp.Mapping[str, tp.Any] = dc.field(default_factory=dict, kw_only=True)
    storages: dict[tp.Type[StorageBase], StorageBase] = dc.field(
        default_factory=dict,
        kw_only=True,
    )

    @classmethod
    def repo(cls) -> ResourceRepository:
        r"""
        获取当前资源仓库。

        Returns:
            当前活动的ResourceRepository实例

        Raises:
            RuntimeError: 如果没有活动的资源仓库上下文
        """
        return ResourceRepository.current()

    def __post_init__(self):
        ResourceRepository.current().add(self)

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__}'
            f' id={self.id!r}'
            f' name={self.name!r}'
            f' mime_type={self.mime_type!r}'
            f' metadata={list(self.metadata)!r}'
            f' storages={list(self.storages)!r}'
            '>'
        )

    @property
    def type(self) -> str:
        r"""
        获取资源的主类型。

        Returns:
            MIME类型的主类型部分（如 "image/jpeg" -> "image"）
        """
        return self.mime_type.split('/')[0]

    @property
    def format(self) -> str:
        r"""
        获取资源的格式。

        Returns:
            MIME类型的子类型部分（如 "image/jpeg" -> "jpeg"）
        """
        return self.mime_type.split('/')[-1]

    @tp.overload
    async def get(
        self,
        storage_type: tp.Literal[None] = None,
        no_convert: tp.Literal[False] = False,
    ) -> StorageBase:
        r"""
        获取任意可用的存储。

        Args:
            storage_type: 必须为None
            no_convert: 当 storage_type 为 None 时此参数无效，传入任意值均可。

        Returns:
            任意可用的存储实例
        """
        ...

    @tp.overload
    async def get(
        self,
        storage_type: tp.Type[StorageT],
        no_convert: tp.Literal[False] = False,
    ) -> StorageT:
        r"""
        获取指定类型的存储，如不存在则自动转换。

        Args:
            storage_type: 目标存储类型
            no_convert: 必须为False

        Returns:
            指定类型的存储实例
        """
        ...

    @tp.overload
    async def get(
        self,
        storage_type: tp.Type[StorageT],
        no_convert: tp.Literal[True],
    ) -> tp.Optional[StorageT]:
        r"""
        获取指定类型的存储，如不存在则返回None。

        Args:
            storage_type: 目标存储类型
            no_convert: 必须为True

        Returns:
            指定类型的存储实例，或None
        """
        ...

    @tp.overload
    async def get(
        self,
        storage_type: tp.Type[StorageT],
        no_convert: tp.Collection[tp.Type[StorageBase]],
    ) -> tp.Optional[StorageT]:
        r"""
        获取指定类型的存储，从允许的存储类型中转换。

        Args:
            storage_type: 目标存储类型
            no_convert: 排除的存储类型集合

        Returns:
            指定类型的存储实例，如无法转换则返回None
        """
        ...

    async def get(
        self,
        storage_type: tp.Optional[tp.Type[StorageT]] = None,
        no_convert: tp.Union[bool, tp.Collection[tp.Type[StorageBase]]] = False,
    ) -> tp.Optional[tp.Union[StorageBase, StorageT]]:
        r"""
        获取指定类型的存储。

        Note: 根据 `no_convert` 参数控制是否自动转换存储类型
            - False: 自动从其他存储类型转换
            - True: 不转换，不存在时返回None
            - Collection: 从不在集合中的存储类型转换

        Args:
            storage_type: 目标存储类型，None表示获取任意可用存储
            no_convert: 控制转换行为的标志

        Returns:
            存储实例，或None（当no_convert为True且存储不存在时）
        """

        if storage_type is None:
            return next(iter(self.storages.values()))

        if storage_type not in self.storages:
            storage: StorageT
            match no_convert:
                case True:
                    return None
                case False:
                    storage = await storage_type.from_resource(self)
                case _:
                    try: storage = await storage_type.from_resource(self, exclude=no_convert)  # fmt: skip
                    except (NotImplementedError,): return None  # fmt: skip
            self.storages[storage_type] = storage

        return self.storages[storage_type]

    def close(self):
        r"""
        关闭所有存储，清理资源。
        """
        for storage in self.storages.values(): storage.close()  # fmt: skip
        self.storages.clear()


@dc.dataclass(slots=True)
class ResourceItem:
    r"""
    资源仓库中的条目，包含资源和访问统计。

    Args:
        resource: 资源对象
        session_id: 所属会话ID
        read_count: 读取次数统计
        write_count: 写入次数统计

    Attributes:
        resource (Resource): 资源对象
        session_id (SessionIdType): 所属会话ID
        read_count (int): 读取次数
        write_count (int): 写入次数
    """

    resource: Resource
    session_id: SessionIdType
    read_count: int = 0
    write_count: int = 0


@tp.final
class ResourceRepository:
    r"""
    资源仓库，管理资源的缓存和访问计数。

    使用LRU策略管理资源缓存，支持按会话隔离资源。
    提供线程安全的读写锁保护。

    Attributes:
        max_size (int): 最大缓存资源数量
    """

    @staticmethod
    def current() -> ResourceRepository:
        r"""
        获取当前活动的资源仓库。

        Returns:
            当前资源仓库实例（优先返回 resource_context() 作用域内的实例，
            否则返回全局默认实例）
        """
        if (repo := getattr(local, 'resource_repo', None)) is not None: return repo  # fmt: skip
        return global_resource_repo  # fmt: skip

    def __init__(
        self,
        max_size: int = 4096,
    ):
        r"""
        初始化资源仓库。

        Args:
            max_size: 最大缓存资源数量，默认4096
        """
        self.max_size: int = max_size
        self._items = OrderedDict[ResourceIdType, ResourceItem]()
        self._weak_resources = weakref.WeakKeyDictionary[Resource, None]()
        self._name2id = defaultdict[SessionIdType, dict[str, ResourceIdType]](dict)
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f'<{self.__class__.__name__}'
                f' max_size={self.max_size!r}'
                f' resources={len(self._items)!r}'
                f' weak_resources={len(self._weak_resources)!r}'
                f' read_count={sum(i.read_count for i in self._items.values())}'
                f' write_count={sum(i.write_count for i in self._items.values())}'
                '>'
            )

    @property
    def counter(self) -> tp.Mapping[str, tuple[int, int]]:
        r"""
        获取当前会话的资源访问计数。

        Returns:
            资源名称到(read_count, write_count)元组的映射
        """
        session_id: SessionIdType = Session.current().id
        with self._lock:
            return {
                n: (self._items[i].read_count, self._items[i].write_count)
                for n, i in self._name2id[session_id].items()
            }

    def add(self, resource: Resource):
        r"""
        添加资源到仓库。

        如果资源已存在，根据会话ID和名称决定合并或替换。
        如果缓存已满，淘汰最久未使用的资源。

        Args:
            resource: 要添加的资源
        """
        session_id: SessionIdType = Session.current().id
        logger.debug('add resource %r in session %r', resource, session_id)
        with self._lock:
            if item := self._items.get(resource.id):
                if item.resource.name == resource.name:  #  and item.session_id == session_id
                    logger.info(
                        'Resource %r already exists as %r, merge it in session %r',
                        resource,
                        item,
                        session_id,
                    )
                    resource.storages.update(item.resource.storages)
                    item.resource.storages.update(resource.storages)
                    item.write_count += 1
                else:
                    logger.warning(
                        'Resource %r already exists as %r, replace it in session %r',
                        resource,
                        item,
                        session_id,
                    )
                    self._weak_resources[item.resource] = None
                    self._name2id[item.session_id].pop(item.resource.name)
                    if len(self._name2id[item.session_id]) == 0: self._name2id.pop(item.session_id)  # fmt: skip
                    self._name2id[session_id][resource.name] = resource.id
                    self._items[resource.id] = ResourceItem(resource, session_id)
                self._items.move_to_end(resource.id)
            else:
                if len(self._items) >= self.max_size:
                    resource_id, item = self._items.popitem(last=False)
                    logger.debug('evict resource %r', item)
                    self._weak_resources[item.resource] = None
                    self._name2id[item.session_id].pop(item.resource.name)
                    if len(self._name2id[item.session_id]) == 0: self._name2id.pop(item.session_id)  # fmt: skip
                self._name2id[session_id][resource.name] = resource.id
                self._items[resource.id] = ResourceItem(resource, session_id)

    def get(self, name: str) -> Resource:
        r"""
        按名称获取当前会话的资源。

        Args:
            name: 资源名称

        Returns:
            资源对象

        Raises:
            KeyError: 如果资源不存在
        """
        session_id: SessionIdType = Session.current().id
        with self._lock:
            resource_id: ResourceIdType = self._name2id[session_id][name]
            self._items.move_to_end(resource_id)
            self._items[resource_id].read_count += 1
            return self._items[resource_id].resource

    def close(self):
        r"""
        关闭仓库，清理所有资源。
        """
        with self._lock:
            logger.info('clear %d weak resources', len(self._weak_resources))
            for resource in self._weak_resources: resource.close()  # fmt: skip
            self._weak_resources.clear()
            logger.info('clear %d resources', len(self._items))
            for item in self._items.values(): item.resource.close()  # fmt: skip
            self._items.clear()
            self._name2id.clear()


global_resource_repo = ResourceRepository()


@contextmanager
def resource_context(**kwds) -> tp.Generator[ResourceRepository, None, None]:
    r"""
    资源仓库上下文管理器。

    创建并激活资源仓库，在退出时自动清理资源。

    Args:
        **kwds: 传递给ResourceRepository构造函数的参数

    Yields:
        资源仓库实例

    Examples:
        >>> with resource_context(max_size=100) as repo:
        ...     # 在此上下文中可以使用Resource类
        ...     pass
    """
    old_repo: tp.Optional[ResourceRepository] = getattr(local, 'resource_repo', None)
    new_repo = ResourceRepository(**kwds)
    local.resource_repo = new_repo
    try:
        yield new_repo
    finally:
        local.resource_repo = old_repo
        new_repo.close()


@dc.dataclass(frozen=True)
class ResourceContext:
    r"""
    资源上下文占位类，用于SessionContext。

    这是一个空实现，仅作为类型标记使用，因为当前版本 Resource 生命周期不跟随 Session。
    """

    pass


async def test_resources():
    r"""
    资源系统的集成测试。

    验证资源仓库的LRU淘汰、存储转换和ID去重功能。
    """
    with resource_context(max_size=2) as repo, SessionContextManager(ResourceContext()):
        r1 = await MemoryStorage(content=b'a').to_resource('r1', 'text/plain')
        r2 = await MemoryStorage(content=b'b').to_resource('r2', 'text/plain')
        assert r1.id in repo._items

        r3 = await MemoryStorage(content=b'c').to_resource('r3', 'text/plain')
        r4 = await MemoryStorage(content=b'b').to_resource('r4', 'text/plain')
        assert r2.id == r4.id
        assert r1.id not in repo._items
        assert r2.id in repo._items
        assert r3.id in repo._items

        repo.add(r1)
        repo.add(r2)
        assert r1.id in repo._items

        repo.add(r3)
        repo.add(r4)
        assert r1.id not in repo._items
        assert r2.id in repo._items
        assert r3.id in repo._items


@tp.runtime_checkable
class ResourceTransformerProto(tp.Protocol):
    r"""
    资源转换协议，定义资源与特定格式间的转换接口。

    实现此协议的类可以将资源加载为特定格式，或将特定格式导出为资源。

    Attributes:
        FormatType (tp.ClassVar[type]): 支持的格式类型
        format (tp.Any): 当前格式实例
    """

    FormatType: tp.ClassVar[type]

    format: tp.Any  # type: FormatType

    @classmethod
    @abc.abstractmethod
    def load(cls, resource: Resource) -> tp.Self:
        r"""
        从资源加载为特定格式。

        Args:
            resource: 源资源

        Returns:
            格式化的实例
        """
        ...

    @abc.abstractmethod
    def dump(self) -> Resource:
        r"""
        导出为资源。

        Returns:
            资源对象
        """
        ...

    def as_format(self, format: tp.Any) -> tp.Self:
        r"""
        转换为其他格式。

        Args:
            format: 目标格式

        Returns:
            转换后的实例
        """
        ...


if __name__ == '__main__':
    from conflog import configure_logging, configure_auto_tracing

    configure_logging(env="test")
    configure_auto_tracing(env="test")

    import asyncio

    with SessionContextManager(ResourceContext()), asyncio.Runner(debug=True) as runner:
        runner.run(test_resources())

        image_url = 'https://s3-gz01.didistatic.com/pillars-uc/didi/user/jobCard/144115188103150121/1HU9xP9IPHWllHY17aQn8zz7vhpPn1pW.jpg'
        resource = runner.run(HTTPStorage(url=image_url).to_resource('avatar'))
        coro = resource.get(storage_type=FileStorage)
        print(runner.run(coro).path)
        coro = Resource.repo().get(resource.name).get(storage_type=FileStorage)
        print(runner.run(coro).path)
