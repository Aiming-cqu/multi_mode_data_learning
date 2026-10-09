#!/usr/bin/env -S pixi run -- test

r"""
"""

from __future__ import absolute_import, annotations

import dataclasses as dc, json, threading, traceback, os, sys, typing as tp
import streamlit as st

from streamlit.runtime.scriptrunner import (
    ScriptRunContext,
    add_script_run_ctx,
    get_script_run_ctx,
)

if tp.TYPE_CHECKING:
    from opentelemetry.trace import SpanContext
    from opentelemetry.sdk.trace import Span, ReadableSpan


_T = tp.TypeVar('_T')

NAME: str = os.getenv("OTEL_SERVICE_NAME", os.path.splitext(os.path.basename(sys.argv[0]))[0])


@tp.overload
def st_paramed(
    key: str,
    comp: tp.Callable[..., str],
    *args,
    value: tp.Optional[str] = None,
    is_string_type: tp.Literal[True] = True,
    **kwds
) -> str: ...


@tp.overload
def st_paramed(
    key: str,
    comp: tp.Callable[..., _T],
    *args,
    value: tp.Optional[_T] = None,
    is_string_type: tp.Literal[False],
    **kwds
) -> _T: ...


def st_paramed(
    key: str,
    comp: tp.Callable[..., _T],
    *args,
    value: tp.Optional[_T] = None,
    is_string_type: bool = True,
    **kwds
) -> _T:
    if key in st.query_params:
        value_ = st.query_params[key]
        if not is_string_type: value_ = json.loads(value_)  # fmt: skip
        value = comp(*args, key=key, value=value_, **kwds)
    elif value is not None:
        value = comp(*args, key=key, value=value, **kwds)
    else:
        value = comp(*args, key=key, **kwds)
    if value is not None:
        st.query_params[key] = value if is_string_type else json.dumps(value)
    return value


def st_paramed_selectbox(
    key: str,
    label: str,
    options: tp.Sequence[str],
    index: tp.Optional[int] = 0,
    **kwds
) -> tp.Optional[str]:
    if key in st.query_params: index = options.index(st.query_params[key])  # fmt: skip
    value = st.selectbox(label, options, key=key, index=index, **kwds)
    if value is not None: st.query_params[key] = value  # fmt: skip
    return value


@st.dialog('Report')
def st_report(
    payload: tp.Any,
    *,
    type_options: tp.Sequence[str] = ("Error", "Badcase", "Goodcase"),
    rerun_scope: tp.Optional[tp.Literal["app", "fragment"]] = "app",
):
    report_type: str = st.selectbox('Report Type', type_options)
    report_comment: str = st.text_area(
        'Comment',
        height=200,
        placeholder='Additional infomation.',
    )
    if not st.button('Submit'): return  # fmt: skip

    report_dir: str = f'{os.environ["TRIAGE_DATA_DIR"]}/reports'
    os.makedirs(report_dir, exist_ok=True)
    with open(f'{report_dir}/{NAME}.jsonl', "a") as f:
        json.dump({"type": report_type, "comment": report_comment, "payload": payload}, f)
        f.write('\n')
        f.flush()

    if rerun_scope: st.rerun(scope=rerun_scope)  # fmt: skip


@dc.dataclass(frozen=True, slots=True)
class _Session:
    r"""Per-Streamlit-session state for :class:`SpanProcessor`.

    Attributes:
        -
    """

    ctx: ScriptRunContext
    container: tp.Any
    role: str
    spinners: dict[int, tp.Any] = dc.field(default_factory=dict)


class SpanProcessor:
    r"""Duck implementation of OpenTelemetry SpanProcessor as Streamlit log console.

    Supports multiple concurrent Streamlit sessions. Each session registers itself
    via :meth:`mount`. Spans are routed by ``trace_id``: the session whose
    Streamlit context is active when a root span starts automatically claims that
    trace, and all subsequent spans in that trace are rendered into the same
    session's log console.

    Route lifecycle:

    * Root span starts → ``trace_id`` → ``session_id`` route registered automatically
    * Root span ends → route removed
    * Session unmounted → routes pointing to that session removed

    Example::

        processor = SpanProcessor()
        logfire.configure(additional_span_processors=[processor])

        # In the Streamlit page (called on every render):
        processor.mount()

    Parameters:
        -
    """

    def __init__(self):
        self._sessions: dict[str, _Session] = {}
        self._routes: dict[int, str] = {}
        self._lock = threading.Lock()

    @property
    def is_mounted(self) -> bool:
        r"""True if at least one Streamlit session is currently registered."""
        return bool(self._sessions)

    def mount(
        self,
        label: str = 'Log Console',
        role: str = '📋',
        height: int = 300,
        *,
        script_run_ctx: tp.Optional[ScriptRunContext] = None,
        **kwds
    ):
        r"""
        Register the current Streamlit session and create its log container.

        Safe to call on every page render; re-registering the same session
        updates its :class:`ScriptRunContext` and recreates the container.

        Args:
            label: Label for the sidebar popover.
            role: Chat-message role icon used when rendering completed spans.
            height: Height of the scrollable log container in pixels.
            script_run_ctx: Override the session context. Defaults to the
                context of the calling thread (``get_script_run_ctx()``).
            **kwds: Extra keyword arguments forwarded to ``st.container``.

        Parameters:
            -
        """
        ctx = script_run_ctx or get_script_run_ctx()
        if ctx is None:
            return
        with self._lock:
            with st.sidebar, st.popover(label, icon='📋'):
                container = st.container(border=True, height=height, **kwds)
            self._sessions[ctx.session_id] = _Session(
                ctx=ctx,
                container=container,
                role=role,
            )
            print(f'SpanProcessor: mounted {ctx.session_id!r}', file=sys.stderr)

    def unmount(self, session_id: tp.Optional[str] = None):
        r"""
        Deregister a Streamlit session and remove its trace routes.

        Args:
            session_id: Session to remove. Defaults to the session of the
                calling thread. No-op if the session is not registered.

        Parameters:
            -
        """
        with self._lock:
            if session_id is None:
                ctx = get_script_run_ctx()
                session_id = ctx.session_id if ctx else None
            if session_id is None:
                return
            self._sessions.pop(session_id)
            stale = [
                tid for tid, sid in self._routes.items() if sid == session_id
            ]  # TODO: add reverse map
            for tid in stale:
                del self._routes[tid]
            print(f'SpanProcessor: unmounted {session_id!r}', file=sys.stderr)

    def shutdown(self):
        r"""Called by the OTel TracerProvider on process exit; clears all state."""
        with self._lock:
            self._sessions.clear()
            self._routes.clear()
            print('SpanProcessor: shutdown', file=sys.stderr)

    def _route(
        self,
        trace_id: int,
        is_root: bool,
    ) -> tp.Optional[_Session]:
        r"""
        Return the session for *trace_id*, auto-claiming on root spans.

        For root spans (``is_root=True``) with no existing route, attempts to
        claim the trace for the current Streamlit session if one is registered.
        Stale routes (session no longer mounted) are cleaned up lazily.

        Parameters:
            -
        """
        if trace_id in self._routes:
            session_id = self._routes[trace_id]
            session = self._sessions[session_id]
            return session

        if not is_root:
            return None

        ctx = get_script_run_ctx()
        if ctx is None or ctx.session_id not in self._sessions:
            return None

        self._routes[trace_id] = ctx.session_id
        return self._sessions[ctx.session_id]

    def _inject_ctx(self, session: _Session):
        r"""Inject *session*'s ScriptRunContext into the current thread if missing."""
        if get_script_run_ctx() is None:
            add_script_run_ctx(thread=threading.current_thread(), ctx=session.ctx)

    def on_start(
        self,
        span: 'Span',
        parent_context: tp.Optional['SpanContext'] = None,
    ):
        if not span.attributes or not span.context: return  # fmt: skip
        try:
            with self._lock:
                session = self._route(
                    trace_id=span.context.trace_id,
                    is_root=parent_context is None,
                )
                if session is None: return  # fmt: skip
                self._inject_ctx(session)
                match span.attributes.get("logfire.span_type"):
                    case "span":
                        msg = tp.cast(str, span.attributes["logfire.msg"])
                        with session.container:
                            spinner = st.spinner(msg, show_time=True)
                            spinner.__enter__()
                            session.spinners[span.context.span_id] = spinner
                    case _:
                        pass
        except (Exception,) as exc:
            sys.stderr.writelines(
                [
                    'SpanProcessor:on_start: ',
                    repr(exc),
                    '\nspan=',
                    span.to_json(),
                    '\n',
                    ''.join(traceback.format_stack()),
                    '\n',
                ],
            )

    def on_end(self, span: 'ReadableSpan'):
        if not span.attributes or not span.context: return  # fmt: skip
        try:
            with self._lock:
                trace_id = span.context.trace_id
                session = self._route(trace_id=trace_id, is_root=False)
                if session is None: return  # fmt: skip
                self._inject_ctx(session)
                match span.attributes.get("logfire.span_type"):
                    case "span":
                        spinner = session.spinners[span.context.span_id]
                        with session.container:
                            spinner.__exit__(None, None, None)
                        msg = tp.cast(str, span.attributes["logfire.msg"])
                        with session.container, st.chat_message(session.role):
                            st.info(msg, icon='✅')
                        if span.parent is None:
                            self._routes.pop(trace_id)
                    case "log":
                        if msg := tp.cast(str, span.attributes["logfire.msg"]):
                            log: tp.Callable[[str], tp.Any]
                            match span.attributes.get("logfire.level_name"):
                                case "warning": log = st.warning  # fmt: skip
                                case "error": log = st.error  # fmt: skip
                                case _: log = st.info  # fmt: skip
                            with session.container, st.chat_message(session.role): log(msg)  # fmt: skip
                    case _:
                        pass
        except (Exception,) as exc:
            sys.stderr.writelines(
                [
                    'SpanProcessor:on_end: ',
                    repr(exc),
                    '\nspan=',
                    span.to_json(),
                    '\n',
                    ''.join(traceback.format_stack()),
                    '\n',
                ],
            )
