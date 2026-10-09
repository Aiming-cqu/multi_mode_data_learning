from __future__ import absolute_import, annotations

import os, sys, typing as tp


LOG_DIR: str = os.environ["TRIAGE_LOG_DIR"]
NAME: str = os.getenv("OTEL_SERVICE_NAME", os.path.splitext(os.path.basename(sys.argv[0]))[0])
ENV: str = os.getenv("OTEL_ENVIRONMENT_NAME", "prod")
LOG_MAX_BYTES: int = int(os.getenv("TRIAGE_LOG_MAX_BYTES", 1024**2 * 10))

LOGGING_FORMAT_THREAD: str = (
    '%(levelname)-7s|%(asctime)s|%(threadName)s] '
    '%(filename)s:%(lineno)d[%(name)s:%(funcName)s] %(message)s'
)
LOGGING_FORMAT_TID: str = (
    '%(levelname)-7s|%(asctime)s|%(thread)d) '
    '%(filename)s:%(lineno)d[%(name)s:%(funcName)s] %(message)s'
)
LOGGING_FORMAT_PID: str = (
    '%(levelname)-7s|%(asctime)s|%(process)d> '
    '%(filename)s:%(lineno)d[%(name)s:%(funcName)s] %(message)s'
)

LOGFIRE_LOGGER_BLACKLIST: list[str] = [
    "lib.tools.resources",
]

log_output: tp.TextIO = sys.stderr

try:
    import tqdm
except (ImportError,):
    pass
else:

    class TqdmOutput(tp.TextIO):
        def write(self, s: str) -> int:
            tqdm.tqdm.write(s, file=sys.__stderr__, end='')
            return len(s)

        def flush(self):
            if sys.__stderr__: sys.__stderr__.flush()  # fmt: skip

    log_output = TqdmOutput()


def configure_logging(
    env: tp.Literal["prod", "dev", "test", "perf"] = ENV,
    force: bool = False,
    *,
    logging_format: str = LOGGING_FORMAT_THREAD,
    enable_logfire: tp.Optional[bool] = None,
) -> bool:
    import logging
    import logging.handlers

    configured: bool = len(logging.getLogger().handlers) > 0

    if configured and not force: return False  # fmt: skip

    fe_logging_level: int = logging.DEBUG if env in ("dev", "test") else logging.INFO
    be_logging_level: int = logging.INFO if env in ("perf",) else logging.DEBUG
    handler: logging.Handler

    os.makedirs(LOG_DIR, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        f'{LOG_DIR}/{NAME}-{env}.log',
        maxBytes=LOG_MAX_BYTES,
        backupCount=5,
    )
    handler.setLevel(be_logging_level)
    handlers: list[logging.Handler] = [handler]

    if enable_logfire is not False:
        try:
            import logfire
        except (ImportError,):
            if enable_logfire is True: raise  # fmt: skip
            enable_logfire = False
        else:
            configure_logfire(env=env, force=force)

            class Filter(logging.Filter):
                def filter(self, record: logging.LogRecord) -> bool:
                    if record.name in LOGFIRE_LOGGER_BLACKLIST: return False  # fmt: skip
                    return True

            handler = logfire.LogfireLoggingHandler()
            handler.setLevel(be_logging_level)
            handler.addFilter(Filter())
            handlers.append(handler)

    if enable_logfire is False:
        handler = logging.StreamHandler(stream=log_output)
        handler.setLevel(fe_logging_level)
        handlers.append(handler)

    logging.basicConfig(
        format=logging_format,
        level=be_logging_level,
        handlers=handlers,
        force=force,
    )
    logging.getLogger(name=__name__).info("%s-%s: logging inited.", NAME, env)

    logging.getLogger(name="aiohttp_retry").setLevel(logging.INFO)
    logging.getLogger(name="asyncio").setLevel(logging.INFO)
    logging.getLogger(name="httpcore.connection").setLevel(logging.INFO)
    logging.getLogger(name="httpcore.http11").setLevel(logging.INFO)
    logging.getLogger(name="opentelemetry").setLevel(logging.FATAL)
    logging.getLogger(name="PIL.PngImagePlugin").setLevel(logging.INFO)
    logging.getLogger(name="python_multipart.multipart").setLevel(logging.INFO)
    logging.getLogger(name="urllib3.connectionpool").setLevel(logging.INFO)
    logging.getLogger(name="watchfiles.main").setLevel(logging.WARNING)

    return True


def configure_logfire(
    env: tp.Literal["prod", "dev", "test", "perf"] = ENV,
    force: bool = False,
) -> bool:
    import logfire

    configured: bool = False
    try: configured = logfire._internal.config.GLOBAL_CONFIG._initialized  # type: ignore # fmt: skip
    except: pass  # noqa # fmt: skip

    if configured and not force: return False  # fmt: skip

    logfire.configure(
        send_to_logfire=False,
        service_name=NAME,
        environment=env,
        inspect_arguments=True,
        console=logfire.ConsoleOptions(
            colors="always",
            span_style="indented",
            include_timestamps=True,
            include_tags=True,
            verbose=(env in ("dev", "test")),
            min_log_level=("debug" if env in ("dev", "test") else "info"),
            show_project_link=False,
            output=log_output,
        ),
    )
    logfire.instrument_system_metrics(
        {
            'process.runtime.gc_count': None,
            'process.open_file_descriptor.count': None,
            'process.cpu.time': ['user', 'system'],
            'process.cpu.utilization': None,
            'process.cpu.core_utilization': None,
            'process.memory.usage': None,
            'process.thread.count': None,
            'cpython.gc.collections': None,
        }
    )
    logfire.info(f'{NAME}-{env}: logfire configured')

    return True


def configure_auto_tracing(
    modules: tp.Sequence[str] = ("apps", "lib", "models", "tests"),
    env: tp.Literal["prod", "dev", "test", "perf"] = ENV,
):
    if env not in ("dev", "test"): return False  # fmt: skip

    try: import logfire  # fmt: skip
    except (ImportError,): return False  # fmt: skip

    logfire.install_auto_tracing(
        modules,
        min_duration=float(os.getenv("LOGFIRE_AUTO_TRACING_MIN_DURATION", 0.01)),
        check_imported_modules="warn",
    )
    return True


if __name__ == '__main__':
    configure_logging(env="test")
