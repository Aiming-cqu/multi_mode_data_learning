#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import dataclasses as dc, logging, typing as tp, uuid

from contextvars import ContextVar, Token


_TC = tp.TypeVar('_TC')

SessionIdType: tp.TypeAlias = str

logger: logging.Logger = logging.getLogger(name=__name__)


@tp.final
@dc.dataclass(frozen=True, slots=True)
class Session(tp.Generic[_TC]):
    r"""
    会话管理类，用于封装和管理上下文数据。

    该类是一个冻结的 dataclass，表示一个不可变的会话对象。
    每个会话具有唯一的 ID 和一个强类型的上下文对象。
    上下文对象必须是 dataclass 类型。

    Args:
        id: 会话唯一标识符，默认为自动生成的 UUID
        context: 上下文数据对象，必须是 dataclass 类型

    Attributes:
        id (SessionIdType): 会话唯一标识符
        context (_TC): 强类型的上下文数据对象
    """

    id: SessionIdType = dc.field(default_factory=(lambda: uuid.uuid4().hex[:12]), kw_only=True)
    context: _TC

    def __post_init__(self):
        if not dc.is_dataclass(self.context):
            raise TypeError(
                f'context: dataclass required, got {type(self.context)}, {self.id=}'
            )

    @staticmethod
    def current() -> Session:
        r"""
        获取当前活动会话。

        通过上下文变量获取当前线程/协程中的活动会话实例。

        Returns:
            当前活动的 Session 实例

        Raises:
            RuntimeError: 如果没有活动的会话上下文
        """
        try:
            return session_var.get()
        except (LookupError,) as exc:
            raise RuntimeError(
                'No active session. Use SessionContextManager() please.'
            ) from exc

    def close(self):
        r"""
        关闭会话，同步清理上下文资源。

        遍历上下文对象的所有字段，尝试调用每个字段的 close() 方法。
        忽略没有 close 方法或调用失败的字段。
        """
        for field in dc.fields(self.context):  # type: ignore
            try: getattr(self.context, field.name).close()  # fmt: skip
            except (AttributeError, TypeError): pass  # fmt: skip
            else: logger.info('context.%s.close() invoked', field.name)  # fmt: skip

    async def aclose(self):
        r"""
        关闭会话，异步清理上下文资源。

        首先遍历上下文对象的所有字段，尝试异步调用每个字段的 aclose() 方法。
        然后调用同步的 close() 方法进行同步资源清理。
        忽略没有相应方法或调用失败的字段。
        """
        for field in dc.fields(self.context):  # type: ignore
            try: await getattr(self.context, field.name).aclose()  # fmt: skip
            except (AttributeError, TypeError): pass  # fmt: skip
            else: logger.info('context.%s.aclose() invoked', field.name)  # fmt: skip
        self.close()


session_var = ContextVar[Session]('session_var')


class SessionContextManager(
    tp.ContextManager[Session[_TC]],
    tp.AsyncContextManager[Session[_TC]],
):
    r"""
    会话上下文管理器，用于设置和管理当前会话。

    支持同步和异步上下文管理协议，可确保会话在代码块执行完毕后被正确清理。
    通过上下文变量实现会话的线程/协程隔离。

    Args:
        **kwds: 传递给 Session 构造函数的参数，必须包含 context 参数

    Examples:
        >>> @dc.dataclass
        ... class Context:
        ...     payload: int
        >>> with SessionContextManager[Context](Context(payload=1)) as session:
        ...     assert session == Session.current()
        ...     assert session.context.payload == 1
    """

    __slots__ = ("_session", "_token")

    def __init__(self, context: _TC, **kwds):
        self._session = Session[_TC](context=context, **kwds)

    def __repr__(self) -> str:
        r"""
        返回对象的字符串表示。

        Returns:
            包含类名和会话 ID 的字符串表示
        """
        return f'<{self.__class__.__name__} session={self._session.id!r}>'

    def __enter__(self) -> Session[_TC]:
        r"""
        进入同步上下文，设置当前会话。

        Returns:
            当前会话实例
        """
        self._token: Token[Session] = session_var.set(self._session)
        logger.debug('enter session %r', self._session.id)
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        r"""
        退出同步上下文，重置会话并清理资源。

        Args:
            exc_type: 异常类型（如果有）
            exc_val: 异常值（如果有）
            exc_tb: 异常回溯（如果有）
        """
        session_var.reset(self._token)
        logger.debug('exit session %r', self._session.id)
        self._session.close()

    async def __aenter__(self) -> Session[_TC]:
        r"""
        进入异步上下文，设置当前会话。

        Returns:
            当前会话实例
        """
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        r"""
        退出异步上下文，重置会话并异步清理资源。

        Args:
            exc_type: 异常类型（如果有）
            exc_val: 异常值（如果有）
            exc_tb: 异常回溯（如果有）
        """
        session_var.reset(self._token)
        logger.debug('exit session %r', self._session.id)
        await self._session.aclose()
