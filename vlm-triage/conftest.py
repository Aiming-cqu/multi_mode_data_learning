from __future__ import absolute_import, annotations

import os

os.environ.setdefault("OTEL_ENVIRONMENT_NAME", "test")

from conflog import configure_logging, configure_auto_tracing

configure_logging(force=True)
configure_auto_tracing()

import pytest

import asyncio, gc, logging, re, resource as rm, time, tracemalloc, typing as tp
import psutil

from pathlib import Path


_T = tp.TypeVar('_T')

logging.getLogger(name="asyncio").setLevel(logging.DEBUG)

try:
    runner = asyncio.Runner(debug=True)
except (AttributeError, ):
    pass
else:
    def await_(coro: tp.Coroutine[tp.Any, tp.Any, _T]) -> _T:
        try: loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()  # fmt: skip
        except (RuntimeError,): return runner.run(coro)  # fmt: skip
        else: return loop.run_until_complete(coro)  # fmt: skip


@pytest.fixture(autouse=True)
def add_doctest_namespace(doctest_namespace: tp.MutableMapping[str, tp.Any]):
    doctest_namespace['await_'] = await_


# ---------------------------------------------------------------------------
# Resource Monitor — 用于标记 @pytest.mark.resource 的密集测试
# ---------------------------------------------------------------------------

# 确保 tracemalloc 已启动（全局一次）
if not tracemalloc.is_tracing():
    tracemalloc.start()


def _format_bytes(n: int | float) -> str:
    r"""将 byte 数转为人类可读格式。"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(n) < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


_PIXI_RUN_RE = re.compile(r'pixi run(?: -e (?P<env>[\w-]+))? -- (?P<command>[\w-]+)')


def _read_file_header(path: Path, *, max_lines: int = 6) -> str:
    with path.open(encoding='utf-8', errors='ignore') as f:
        return ''.join(next(f, '') for _ in range(max_lines))


def _parse_pixi_run(path: Path) -> tuple[str | None, str | None]:
    match = _PIXI_RUN_RE.search(_read_file_header(path))
    if match is None:
        return (None, None)
    return (match.group('env'), match.group('command'))


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:
    r"""Skip files that declare another Pixi environment or non-test app entrypoints."""
    if collection_path.suffix != '.py' or not collection_path.is_file():
        return False

    declared_env, declared_command = _parse_pixi_run(collection_path)
    current_env = os.getenv('PIXI_ENVIRONMENT_NAME', '')
    if declared_env and current_env and declared_env != current_env:
        return True

    if 'apps' in collection_path.parts and declared_command not in {'test', None}:
        return True

    return False


@pytest.fixture
def resource_monitor(request: pytest.FixtureRequest):
    r"""资源监控 fixture。

    自动捕获测试的耗时、CPU 时间、RSS 峰值、Python heap 峰值。
    如果测试标记了 ``@pytest.mark.resource`` 且 GPU 可用，额外捕获 GPU 显存峰值。

    Usage::

        @pytest.mark.resource
        def test_heavy(resource_monitor):
            # ... 测试逻辑自动被监控 ...

    输出在 ``-s`` 模式下可见::

        [RESOURCE] path::test_name
          wall_time:   12.345s
          cpu_time:    11.234s
          peak_rss:    8.2 GB  (delta: +4.1 GB)
          current_rss: 6.1 GB  (delta: +2.0 GB)
          py_peak:     3.2 GB  (Python heap)
          gpu_peak:    6.1 GB  (CUDA alloc)

    Parameters:
        -
    """
    # 判断是否需要追踪 GPU（仅当 torch 实际可用时）
    marker = request.node.get_closest_marker('resource')
    track_gpu: bool = False
    if marker is not None:
        try:
            import torch  # noqa: F401
        except ModuleNotFoundError:
            track_gpu = False
        else:
            track_gpu = True

    # --- 前置采样 ---
    gc.collect()
    proc = psutil.Process()
    rss_before = proc.memory_info().rss
    cpu_before = time.process_time()
    wall_before = time.perf_counter()
    ru_before = rm.getrusage(rm.RUSAGE_SELF)
    tracemalloc.clear_traces()
    _ = tracemalloc.get_traced_memory()  # reset peak tracker

    if track_gpu:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()

    # --- 执行测试 ---
    yield

    # --- 后置采样 ---
    gc.collect()
    wall_after = time.perf_counter()
    cpu_after = time.process_time()
    rss_after = proc.memory_info().rss
    ru_after = rm.getrusage(rm.RUSAGE_SELF)

    wall_time: float = wall_after - wall_before
    cpu_time: float = cpu_after - cpu_before
    rss_delta: int = rss_after - rss_before
    ru_peak: int = ru_after.ru_maxrss * 1024
    ru_delta: int = (ru_after.ru_maxrss - ru_before.ru_maxrss) * 1024
    tc_curr: int
    tc_peak: int
    tc_curr, tc_peak = tracemalloc.get_traced_memory()

    lines: list[str] = [
        f'\n[RESOURCE] {request.node.nodeid}',
        f'  wall_time:    {wall_time:.3f}s',
        f'  cpu_time:     {cpu_time:.3f}s',
        f'  peak_rss:     {_format_bytes(ru_peak)}  (delta: +{_format_bytes(max(0, ru_delta))})',
        f'  current_rss:  {_format_bytes(rss_after)}  (delta: {_format_bytes(rss_delta)})',
        f'  py_peak:      {_format_bytes(tc_peak)}  (Python heap)',
    ]

    if track_gpu:
        import torch

        if torch.cuda.is_available():
            torch.cuda.synchronize()
            gpu_peak: int = torch.cuda.max_memory_allocated()
            lines.append(f'  gpu_peak:     {_format_bytes(gpu_peak)}  (CUDA alloc)')

    print('\n'.join(lines))
