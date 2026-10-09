#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import threading, typing as tp

from contextlib import contextmanager


class RWLock:
    r"""
    基于 threading.Condition 实现的简单读写锁。

    该锁允许多个读取者同时访问资源，但写入者需要独占访问。
    当存在写入者时，读取者会被阻塞；当存在读取者时，写入者会被阻塞。
    """

    def __init__(self, *, pre_read: bool = False):
        self.readers: int = 0
        self.pre_read: bool = pre_read
        self.writer: bool = False
        self._condition = threading.Condition()

    def acquire_read(self):
        r"""
        获取读锁。

        如果有写入者正在持有锁，则阻塞等待直到写入者释放锁。
        多个读取者可以同时持有读锁。
        """
        with self._condition:
            while self.writer:
                self._condition.wait()
            self.readers += 1

    def release_read(self):
        r"""
        释放读锁。

        减少读取者计数，如果是最后一个读取者，则通知所有等待的写入者。
        """
        with self._condition:
            self.readers -= 1
            if self.readers == 0:
                self.pre_read = False
                self._condition.notify_all()

    def acquire_write(self):
        r"""
        获取写锁。

        如果有任何读取者或写入者正在持有锁，则阻塞等待直到所有锁被释放。
        写锁是独占的，同一时间只能有一个写入者。
        """
        with self._condition:
            while self.readers > 0 or self.writer or self.pre_read:
                self._condition.wait()
            self.writer = True

    def release_write(self):
        r"""
        释放写锁。

        标记写入者为非活跃状态，并通知所有等待的读取者和写入者。
        """
        with self._condition:
            self.writer = False
            self._condition.notify_all()

    @contextmanager
    def read(self) -> tp.Generator[None, None, None]:
        r"""
        返回一个上下文管理器用于获取读锁。

        Returns
        -------
        tp.Generator[None, None, None]
            上下文管理器，进入时自动获取读锁，退出时自动释放。
        """
        self.acquire_read()
        try: yield  # fmt: skip
        finally: self.release_read()  # fmt: skip

    @contextmanager
    def write(self) -> tp.Generator[None, None, None]:
        r"""
        返回一个上下文管理器用于获取写锁。

        Returns
        -------
        tp.Generator[None, None, None]
            上下文管理器，进入时自动获取写锁，退出时自动释放。
        """
        self.acquire_write()
        try: yield  # fmt: skip
        finally: self.release_write()  # fmt: skip
