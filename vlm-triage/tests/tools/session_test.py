#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

import dataclasses as dc

from lib.tools.session import Session, SessionContextManager


@dc.dataclass
class _PayloadContext:
    payload: int


@dc.dataclass
class _SyncCloser:
    closed: int = 0

    def close(self):
        self.closed += 1


@dc.dataclass
class _AsyncCloser:
    closed: int = 0
    aclosed: int = 0

    def close(self):
        self.closed += 1

    async def aclose(self):
        self.aclosed += 1


@dc.dataclass
class _ClosableContext:
    sync_closer: _SyncCloser = dc.field(default_factory=_SyncCloser)
    async_closer: _AsyncCloser = dc.field(default_factory=_AsyncCloser)


@pytest.mark.functional
def test__functional__session_create():
    r"""
    测试 SessionContextManager 创建并暴露当前会话。

    验证:
        - 进入上下文后可读取当前 Session
        - 自定义会话 ID 和上下文内容保持正确

    Parameters:
        -
    """
    with SessionContextManager(_PayloadContext(payload=1), id='session-under-test') as session:
        assert Session.current() is session
        assert session.id == 'session-under-test'
        assert session.context.payload == 1


@pytest.mark.coverage
def test__coverage__session_without_context():
    r"""
    测试无活跃上下文时访问当前会话会报错。

    验证:
        - Session.current() 在无上下文时抛出 RuntimeError

    Parameters:
        -
    """
    with pytest.raises(RuntimeError, match='No active session'):
        Session.current()


@pytest.mark.coverage
def test__coverage__session_invalid_context():
    r"""
    测试 Session 仅接受 dataclass 上下文。

    验证:
        - 非 dataclass 上下文会抛出 TypeError

    Parameters:
        -
    """
    with pytest.raises(TypeError, match='dataclass required'):
        Session(context=object())


@pytest.mark.coverage
async def test__coverage__session_close():
    r"""
    测试 aclose 会先执行异步清理，再执行同步清理。

    验证:
        - aclose() 调用异步资源的 aclose()
        - aclose() 最终调用所有资源的 close()

    Parameters:
        -
    """
    context = _ClosableContext()
    session = Session(context=context)

    await session.aclose()

    assert context.sync_closer.closed == 1
    assert context.async_closer.aclosed == 1
    assert context.async_closer.closed == 1
