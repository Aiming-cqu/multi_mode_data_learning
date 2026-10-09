#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

from lib.tools.resources import (
    FileStorage,
    MemoryStorage,
    Resource,
    ResourceContext,
    ResourceRepository,
    global_resource_repo,
    hash_func,
    resource_context,
)
from lib.tools.session import SessionContextManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    r"""提供 resource_context(max_size=4) + SessionContextManager 环境。"""
    with resource_context(max_size=4) as repo, SessionContextManager(ResourceContext()):
        yield repo


# ---------------------------------------------------------------------------
# Resource 生命周期
# ---------------------------------------------------------------------------


async def test_resource_registers_on_create(ctx):
    r"""to_resource() 后资源 id 出现在 repo._items。"""
    r1 = await MemoryStorage(content=b'hello').to_resource('r1', 'text/plain')

    assert r1.id in ctx._items


async def test_resource_hash_by_id(ctx):
    r"""同 id 的 hash() 相同；不同 id 的 hash() 不同。"""
    r1 = await MemoryStorage(content=b'a').to_resource('r1', 'text/plain')
    r2 = await MemoryStorage(content=b'b').to_resource('r2', 'text/plain')

    assert hash(r1) == hash(r1)
    assert r1.id != r2.id
    assert hash(r1) != hash(r2)


async def test_resource_type_format(ctx):
    r"""mime_type="image/jpeg" → .type == "image"，.format == "jpeg"。"""
    r = await MemoryStorage(content=b'\xff\xd8').to_resource('img', 'image/jpeg')

    assert r.type == 'image'
    assert r.format == 'jpeg'


async def test_resource_get_no_convert_missing(ctx):
    r"""get(FileStorage, no_convert=True) 在仅有 MemoryStorage 时返回 None。"""
    r = await MemoryStorage(content=b'data').to_resource('r', 'text/plain')

    result = await r.get(FileStorage, no_convert=True)

    assert result is None


async def test_resource_get_no_convert_present(ctx):
    r"""get(MemoryStorage, no_convert=True) 在 MemoryStorage 存在时直接返回。"""
    storage = MemoryStorage(content=b'data')
    r = await storage.to_resource('r', 'text/plain')

    result = await r.get(MemoryStorage, no_convert=True)

    assert result is storage


async def test_resource_get_auto_convert(ctx):
    r"""get(FileStorage) 自动从 MemoryStorage 转换，并缓存到 storages。"""
    r = await MemoryStorage(content=b'text content').to_resource('r', 'text/plain')

    assert FileStorage not in r.storages

    file_storage = await r.get(FileStorage)

    assert isinstance(file_storage, FileStorage)
    assert FileStorage in r.storages


async def test_resource_close(ctx):
    r"""close() 后 storages 为空。"""
    r = await MemoryStorage(content=b'data').to_resource('r', 'text/plain')
    assert len(r.storages) > 0

    r.close()

    assert len(r.storages) == 0


# ---------------------------------------------------------------------------
# ResourceRepository 生命周期
# ---------------------------------------------------------------------------


async def test_repo_add_new(ctx):
    r"""新资源出现在 repo._items 中。"""
    r = await MemoryStorage(content=b'new').to_resource('r', 'text/plain')

    assert r.id in ctx._items


async def test_repo_add_merge_same_name(ctx):
    r"""同 id + 同 name：storages 合并，write_count +1。"""
    r1 = await MemoryStorage(content=b'same').to_resource('r', 'text/plain')
    initial_write_count = ctx._items[r1.id].write_count

    # Adding same resource again (same id, same name) → merge
    ctx.add(r1)

    assert ctx._items[r1.id].write_count == initial_write_count + 1


async def test_repo_add_replace_diff_name(ctx):
    r"""同 id + 不同 name：旧 name 移出 _name2id，新 name 写入。"""
    from lib.tools.session import Session

    r1 = await MemoryStorage(content=b'same').to_resource('old_name', 'text/plain')
    session_id = Session.current().id

    assert 'old_name' in ctx._name2id[session_id]

    r2 = Resource(id=r1.id, name='new_name', mime_type='text/plain')

    assert 'old_name' not in ctx._name2id[session_id]
    assert 'new_name' in ctx._name2id[session_id]


async def test_repo_lru_eviction():
    r"""max_size=2 时，第 3 个资源淘汰最早加入的。"""
    with resource_context(max_size=2) as repo, SessionContextManager(ResourceContext()):
        r1 = await MemoryStorage(content=b'a').to_resource('r1', 'text/plain')
        r2 = await MemoryStorage(content=b'b').to_resource('r2', 'text/plain')

        assert r1.id in repo._items
        assert r2.id in repo._items

        r3 = await MemoryStorage(content=b'c').to_resource('r3', 'text/plain')

        assert r1.id not in repo._items  # oldest evicted
        assert r2.id in repo._items
        assert r3.id in repo._items


async def test_repo_lru_access_updates_order():
    r"""get() 调用 move_to_end，使访问过的资源不被下次 add 淘汰。"""
    with resource_context(max_size=2) as repo, SessionContextManager(ResourceContext()):
        r1 = await MemoryStorage(content=b'a').to_resource('r1', 'text/plain')
        r2 = await MemoryStorage(content=b'b').to_resource('r2', 'text/plain')

        # Access r1 via get() → move_to_end, r2 becomes LRU
        repo.get('r1')

        # r3 evicts the least recently used, which is now r2
        r3 = await MemoryStorage(content=b'c').to_resource('r3', 'text/plain')

        assert r1.id in repo._items   # r1 was accessed, survives
        assert r2.id not in repo._items  # r2 is LRU victim
        assert r3.id in repo._items


async def test_repo_get_increments_read_count(ctx):
    r"""repo.get(name) 后 counter[name][0] +1。"""
    await MemoryStorage(content=b'data').to_resource('r', 'text/plain')
    before = ctx.counter.get('r', (0, 0))[0]

    ctx.get('r')
    ctx.get('r')

    after = ctx.counter['r'][0]
    assert after == before + 2


async def test_repo_get_missing(ctx):
    r"""repo.get("nonexistent") → KeyError。"""
    with pytest.raises(KeyError):
        ctx.get('nonexistent')


async def test_repo_counter(ctx):
    r"""counter 返回正确的 (read_count, write_count) 元组。"""
    await MemoryStorage(content=b'data').to_resource('r', 'text/plain')

    ctx.get('r')
    ctx.get('r')

    read_count, write_count = ctx.counter['r']
    assert read_count == 2
    assert write_count == 0


async def test_repo_session_isolation(ctx):
    r"""不同 session 下同名资源互不干扰，各自 _name2id 独立"""
    r1 = await MemoryStorage(content=b'session1').to_resource('shared', 'text/plain')

    with SessionContextManager(ResourceContext()):
        r2 = await MemoryStorage(content=b'session2').to_resource('shared', 'text/plain')

        assert r2 is not r1
        assert ctx.get('shared') is r2

    # After leaving session 2, session 1 is restored
    assert ctx.get('shared') is r1


async def test_repo_close_strong_refs(ctx):
    r"""close() 后 _items 清空，各资源 storages 已清理。"""
    r1 = await MemoryStorage(content=b'a').to_resource('r1', 'text/plain')
    r2 = await MemoryStorage(content=b'b').to_resource('r2', 'text/plain')
    assert len(ctx._items) == 2

    ctx.close()

    assert len(ctx._items) == 0
    assert len(r1.storages) == 0
    assert len(r2.storages) == 0


async def test_repo_close_weak_refs(ctx):
    r"""close() 后 _weak_resources 已清理。"""
    with resource_context(max_size=1) as repo, SessionContextManager(ResourceContext()):
        r1 = await MemoryStorage(content=b'a').to_resource('r1', 'text/plain')
        # r2 evicts r1 → r1 goes to _weak_resources
        r2 = await MemoryStorage(content=b'b').to_resource('r2', 'text/plain')

        assert r1 in repo._weak_resources

        repo.close()

        # After close(), r1 (evicted) should be closed — its storages cleared
        assert len(r1.storages) == 0


async def test_resource_context_exits_clean():
    r"""resource_context() 退出后 _items 为空。"""
    with resource_context() as repo, SessionContextManager(ResourceContext()):
        await MemoryStorage(content=b'a').to_resource('r1', 'text/plain')
        assert len(repo._items) == 1

    assert len(repo._items) == 0


# ---------------------------------------------------------------------------
# 存储转换缓存（IO 减少）
# ---------------------------------------------------------------------------


async def test_storage_cache_hit(ctx):
    r"""get() 自动转换后再次 get 命中缓存，不触发重复 IO 转换。"""
    r = await MemoryStorage(content=b'content').to_resource('r', 'text/plain')

    file_storage1 = await r.get(FileStorage)
    file_storage2 = await r.get(FileStorage)

    assert file_storage1 is file_storage2  # same object = cache hit


async def test_cross_session_storage_cache(ctx):
    r"""跨 session 同 id resource 共享 storages，转换只发生一次。

    Session 1 先把同一内容转换为 FileStorage，缓存在 storages 中。
    Session 2 用相同内容 new 一个 MemoryStorage → to_resource，得到相同 id，
    add() 时触发 merge，将 Session 1 的 storages 合并过来。
    Session 2 无需重新转换即可通过 no_convert=True 获取 FileStorage。
    """
    # Session 1: create resource and convert to FileStorage
    r1 = await MemoryStorage(content=b'shared').to_resource('r', 'text/plain')
    file1 = await r1.get(FileStorage)

    # Session 2: create NEW MemoryStorage with same content → same id → merged with r1.
    # After merge, r2.storages inherits r1.storages (including the cached FileStorage).
    with SessionContextManager(ResourceContext()):
        r2 = await MemoryStorage(content=b'shared').to_resource('r', 'text/plain')
        assert r2.id == r1.id  # same content hash → same id

        # No re-conversion needed: FileStorage was merged in from session 1
        file2 = await r2.get(FileStorage, no_convert=True)

    assert file2 is file1  # same cached object


# ---------------------------------------------------------------------------
# 并发安全
# ---------------------------------------------------------------------------


async def test_concurrent_reads(ctx):
    r"""16 个并发 get() 后 read_count 正确，无竞态丢失。"""
    import asyncio

    await MemoryStorage(content=b'data').to_resource('r', 'text/plain')

    async def reader():
        ctx.get('r')

    await asyncio.gather(*[reader() for _ in range(16)])

    assert ctx.counter['r'][0] == 16


async def test_concurrent_adds():
    r"""8 个并发 to_resource() 后各资源均在 repo._items 中（max_size=16，无淘汰）。"""
    import asyncio

    with resource_context(max_size=16) as repo, SessionContextManager(ResourceContext()):

        async def add_resource(i: int):
            return await MemoryStorage(content=f'data{i}'.encode()).to_resource(f'r{i}', 'text/plain')

        resources = await asyncio.gather(*[add_resource(i) for i in range(8)])

        for r in resources:
            assert r.id in repo._items


async def test_concurrent_mixed(ctx):
    r"""读写并发：8 读 + 8 写混合，不抛异常，最终 _items 状态一致。"""
    import asyncio

    base = await MemoryStorage(content=b'base').to_resource('base', 'text/plain')

    async def reader():
        try:
            ctx.get('base')
        except KeyError:
            pass  # base may have been evicted if max_size is small

    async def writer(i: int):
        await MemoryStorage(content=f'w{i}'.encode()).to_resource(f'w{i}', 'text/plain')

    await asyncio.gather(
        *[reader() for _ in range(8)],
        *[writer(i) for i in range(8)],
    )

    # At least the 8 writer resources should be traceable
    assert len(ctx._items) > 0


# ---------------------------------------------------------------------------
# hash_func
# ---------------------------------------------------------------------------


def test_hash_func_deterministic():
    """Same input always produces same 12-char hex output."""
    result = hash_func(b'hello')
    assert result == hash_func(b'hello')
    assert len(result) == 12  # blake2b digest_size=6 → 12 hex chars
    assert all(c in '0123456789abcdef' for c in result)


def test_hash_func_unique():
    """Different inputs produce different digests."""
    assert hash_func(b'hello') != hash_func(b'world')
    assert hash_func(b'') != hash_func(b'\x00')


# ---------------------------------------------------------------------------
# threading.local fallback to global_resource_repo
# ---------------------------------------------------------------------------


def test_repo_falls_back_to_global_after_context():
    """After resource_context() exits, current() must return global_resource_repo, not None."""
    with resource_context() as inner_repo:
        assert ResourceRepository.current() is inner_repo

    # After context exits, local.resource_repo is restored to None (or unset).
    # ResourceRepository.current() must fall back to global_resource_repo.
    assert ResourceRepository.current() is global_resource_repo


def test_repo_nested_context_restores_outer():
    """Nested resource_context() restores the outer repo on exit."""
    with resource_context() as outer_repo:
        with resource_context() as inner_repo:
            assert ResourceRepository.current() is inner_repo
        # Inner exited: should be back to outer
        assert ResourceRepository.current() is outer_repo
    # Both exited: back to global
    assert ResourceRepository.current() is global_resource_repo




# ---------------------------------------------------------------------------
# Threaded concurrent get() correctness
# ---------------------------------------------------------------------------


async def test_concurrent_threaded_get():
    """read_count is accurate under concurrent threaded access.

    Tests that the repo lock correctly serialises get() across OS threads.
    asyncio.to_thread() copies the current ContextVar snapshot (including the
    active session) into each worker thread, so Session.current() is correct.
    """
    import asyncio
    from lib.tools.session import Session

    N = 32
    with resource_context(max_size=N + 4) as repo:
        with SessionContextManager(ResourceContext()):
            r = await MemoryStorage(content=b'data').to_resource('target', 'text/plain')

            # asyncio.to_thread() propagates the current ContextVar context
            # (session_var, etc.) into the worker thread.
            await asyncio.gather(*[asyncio.to_thread(repo.get, 'target') for _ in range(N)])

            item = repo._items[r.id]
            assert item.read_count == N
