#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

import threading, time

from lib.utils.rwlock import RWLock


@pytest.mark.functional
def test_read_lock_acquire_release():
    r"""读锁可获取和释放。"""
    rw = RWLock()
    rw.acquire_read()
    rw.release_read()


@pytest.mark.functional
def test_write_lock_acquire_release():
    r"""写锁可获取和释放。"""
    rw = RWLock()
    rw.acquire_write()
    rw.release_write()


@pytest.mark.functional
def test_read_context_manager():
    r"""read 上下文管理器。"""
    rw = RWLock()
    with rw.read():
        pass


@pytest.mark.functional
def test_write_context_manager():
    r"""write 上下文管理器。"""
    rw = RWLock()
    with rw.write():
        pass


@pytest.mark.stress
def test_concurrent_readers():
    r"""多个读锁可并发获取。"""
    rw = RWLock()
    results: list[int] = []

    def reader(i: int):
        with rw.read():
            time.sleep(0.05)
            results.append(i)

    threads = [threading.Thread(target=reader, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 4


@pytest.mark.stress
def test_write_blocks_readers():
    r"""写锁阻塞读锁。"""
    rw = RWLock()
    acquired: list[str] = []

    def writer():
        with rw.write():
            time.sleep(0.3)
            acquired.append("writer")

    def reader():
        with rw.read():
            acquired.append("reader")

    tw = threading.Thread(target=writer)
    tr = threading.Thread(target=reader)
    tw.start()
    time.sleep(0.1)
    tr.start()
    tw.join()
    tr.join()
    assert acquired == ["writer", "reader"]
