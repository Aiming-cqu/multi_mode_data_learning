#!/usr/bin/env -S pixi run -e vllm -- python

from __future__ import absolute_import, annotations

import argparse, datetime as dt, json, os, pathlib, shlex, subprocess, sys, time, typing as tp


DEFAULT_MODEL_IDS = {
    'clip': 'AI-ModelScope/clip-vit-large-patch14',
    'aimv2': 'apple/aimv2-huge-patch14-448',
    'dino': 'facebook/dinov2-base',
}

DEFAULT_MODEL_TASKS = {
    'clip': 'embed',
    'aimv2': 'embed',
    'dino': 'embed',
}


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def _project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def _result_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent / 'results'


def _resolve_from_modelscope_cache(
    model_id: str, *, modelscope_cache: str | None
) -> tuple[str, bool]:
    r"""Resolve model id to local cache path when possible."""
    if os.path.isdir(model_id):
        return model_id, True
    if os.path.isabs(model_id):
        return model_id, os.path.isdir(model_id)
    if not modelscope_cache:
        return model_id, False
    local_path = os.path.join(modelscope_cache, 'models', model_id)
    if os.path.isdir(local_path):
        return local_path, True
    return model_id, False


def _query_gpu_memory_used_mib() -> int | None:
    r"""Return total used memory across all visible GPUs."""
    cmd = ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits']
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    values: list[int] = list[int]()
    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            values.append(int(raw))
        except ValueError:
            continue
    if not values:
        return None
    return sum(values)


def _extract_blocker_summary(lines: list[str]) -> str:
    r"""Extract a concise blocker line with priority ordering."""
    for token in (
        'NotImplementedError',
        'ValidationError',
        'Value error',
        'not supported',
        'KeyError',
        'RuntimeError',
    ):
        for line in reversed(lines):
            if token in line:
                return line
    return lines[-1] if lines else ''


def _run_single_model(
    *,
    python_bin: str,
    model_name: str,
    model_id: str,
    task: str,
    prompt: str,
    timeout_seconds: float,
    gpu_memory_utilization: float,
    modelscope_cache: str | None,
) -> dict[str, tp.Any]:
    r"""Run one loader-poc subprocess and collect metrics."""
    resolved_model_id, used_local_cache = _resolve_from_modelscope_cache(
        model_id,
        modelscope_cache=modelscope_cache,
    )
    command = [
        python_bin,
        'experiments/gpu-concurrency-vllm/run_loader_poc.py',
        '--model-id',
        resolved_model_id,
        '--task',
        task,
        '--prompt',
        prompt,
        '--gpu-memory-utilization',
        str(gpu_memory_utilization),
    ]
    env = os.environ.copy()
    project_root = str(_project_root())
    old_pythonpath = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = project_root if not old_pythonpath else f'{project_root}:{old_pythonpath}'

    memory_before_mib = _query_gpu_memory_used_mib()
    started_at = _now_iso()
    begin = time.perf_counter()
    status = 'ok'
    error: dict[str, tp.Any] | None = None
    result_text = ''
    output_tail: list[str] = list[str]()
    blocker_summary = ''
    try:
        proc = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        combined = '\n'.join([proc.stdout, proc.stderr]).strip()
        output_tail = combined.splitlines()[-30:]
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        blocker_summary = _extract_blocker_summary(lines)
        stdout_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        result_text = stdout_lines[-1] if stdout_lines else ''
        if proc.returncode != 0:
            status = 'failed'
            error = {
                'type': 'subprocess_nonzero',
                'returncode': proc.returncode,
                'message': blocker_summary or '\n'.join(output_tail[-8:]),
            }
    except subprocess.TimeoutExpired as exc:
        status = 'timeout'
        output = (exc.stdout or '') + '\n' + (exc.stderr or '')
        output_tail = [line for line in output.splitlines() if line.strip()][-30:]
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        blocker_summary = _extract_blocker_summary(lines)
        error = {
            'type': 'timeout',
            'returncode': None,
            'message': f'timeout after {timeout_seconds}s',
        }
    latency_seconds = time.perf_counter() - begin
    memory_after_mib = _query_gpu_memory_used_mib()

    throughput_qps = 1.0 / latency_seconds if status == 'ok' and latency_seconds > 0 else 0.0
    result = {
        'model_name': model_name,
        'model_id_requested': model_id,
        'model_id_resolved': resolved_model_id,
        'used_local_cache': used_local_cache,
        'task': task,
        'status': status,
        'started_at': started_at,
        'latency_seconds': latency_seconds,
        'throughput_qps': throughput_qps,
        'memory_before_mib': memory_before_mib,
        'memory_after_mib': memory_after_mib,
        'memory_delta_mib': (
            None
            if memory_before_mib is None or memory_after_mib is None
            else memory_after_mib - memory_before_mib
        ),
        'result_text': result_text,
        'blocker_summary': blocker_summary,
        'command': ' '.join(shlex.quote(item) for item in command),
        'output_tail': output_tail,
    }
    if error is not None:
        result['error'] = error
    return result


def parse_args() -> argparse.Namespace:
    r"""Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description='Benchmark cached CLIP/AIMv2/DINO with vLLM loader PoC.'
    )
    parser.add_argument(
        '--models',
        nargs='*',
        choices=tuple(DEFAULT_MODEL_IDS.keys()),
        default=['clip', 'aimv2', 'dino'],
        help='需要测试的模型集合',
    )
    parser.add_argument(
        '--prompt',
        default='benchmark',
        help='embed/generate 输入文本',
    )
    parser.add_argument(
        '--python-bin',
        default=sys.executable,
        help='用于执行 run_loader_poc.py 的 python，可指向已有 vllm 环境',
    )
    parser.add_argument(
        '--timeout-seconds',
        type=float,
        default=240.0,
        help='单模型超时时间（秒）',
    )
    parser.add_argument(
        '--gpu-memory-utilization',
        type=float,
        default=0.15,
        help='透传到 run_loader_poc 的 vLLM 显存占用比例',
    )
    parser.add_argument(
        '--result-file',
        default='',
        help='结果文件路径，默认写入 results/loader_metrics_<timestamp>.json',
    )
    return parser.parse_args()


def main() -> None:
    r"""CLI entrypoint."""
    args = parse_args()
    modelscope_cache = os.environ.get('MODELSCOPE_CACHE')
    records: list[dict[str, tp.Any]] = list[dict[str, tp.Any]]()
    for model_name in args.models:
        records.append(
            _run_single_model(
                python_bin=args.python_bin,
                model_name=model_name,
                model_id=DEFAULT_MODEL_IDS[model_name],
                task=DEFAULT_MODEL_TASKS[model_name],
                prompt=args.prompt,
                timeout_seconds=args.timeout_seconds,
                gpu_memory_utilization=args.gpu_memory_utilization,
                modelscope_cache=modelscope_cache,
            ),
        )

    payload = {
        'experiment': 'gpu-concurrency-vllm',
        'generated_at': _now_iso(),
        'python_bin': args.python_bin,
        'modelscope_cache': modelscope_cache,
        'records': records,
        'summary': {
            'ok': sum(1 for item in records if item['status'] == 'ok'),
            'failed': sum(1 for item in records if item['status'] == 'failed'),
            'timeout': sum(1 for item in records if item['status'] == 'timeout'),
        },
    }
    result_dir = _result_dir()
    result_dir.mkdir(parents=True, exist_ok=True)
    if args.result_file:
        output_path = pathlib.Path(args.result_file)
    else:
        ts = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        output_path = result_dir / f'loader_metrics_{ts}.json'
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    latest_path = result_dir / 'loader_metrics_latest.json'
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'WROTE: {output_path}')
    print(f'LATEST: {latest_path}')
    for item in records:
        print(
            f"{item['model_name']}: status={item['status']} "
            f"latency={item['latency_seconds']:.3f}s throughput_qps={item['throughput_qps']:.3f} "
            f"mem_delta_mib={item['memory_delta_mib']}",
        )


if __name__ == '__main__':
    main()
