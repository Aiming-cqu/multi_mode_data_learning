#!/usr/bin/env -S pixi run -e vllm -- python

from __future__ import absolute_import, annotations

import argparse, dataclasses, typing as tp

from lib.services.vllm_loader import VllmEngineLike, VllmModelLoader


@dataclasses.dataclass(slots=True)
class _FakeEngine:
    model_id: str
    closed: bool = False

    def generate(
        self,
        prompts: list[str],
        *args: tp.Any,
        **kwargs: tp.Any,
    ) -> list[str]:
        del args, kwargs
        return [f'fake:{self.model_id}:{prompt}' for prompt in prompts]

    def shutdown(self) -> None:
        self.closed = True


def _extract_text(output: tp.Any) -> str:
    r"""Extract best-effort text from different output shapes."""
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output and isinstance(output[0], str):
        return output[0]
    if isinstance(output, list) and output:
        first = output[0]
        outputs = getattr(first, 'outputs', None)
        if isinstance(outputs, list) and outputs:
            text = getattr(outputs[0], 'text', None)
            if isinstance(text, str):
                return text
    return repr(output)


def run(
    model_id: str,
    *,
    prompt: str = 'hello',
    max_loaded_models: int = 1,
    dry_run: bool = False,
    gpu_memory_utilization: float = 0.05,
    task: str = 'auto',
) -> str:
    r"""Run a single loader PoC request."""
    if not dry_run and not model_id:
        raise ValueError('--model-id is required when --dry-run=false')

    if dry_run:
        loader = VllmModelLoader(
            max_loaded_models=max_loaded_models,
            engine_factory=lambda m: tp.cast(VllmEngineLike, _FakeEngine(model_id=m)),
        )
        model_id_ = model_id or 'fake-model'
        with loader.get(model_id_) as engine:
            output = engine.generate([prompt])
        return _extract_text(output)

    from vllm import SamplingParams

    sampling_params = SamplingParams(max_tokens=32)
    engine_options = {'gpu_memory_utilization': gpu_memory_utilization}
    if task != 'auto':
        engine_options['task'] = task
    loader = VllmModelLoader(
        max_loaded_models=max_loaded_models,
        engine_options=engine_options,
    )
    with loader.get(model_id) as engine:
        if task == 'embed':
            embed = getattr(engine, 'embed', None)
            if callable(embed):
                output = embed([prompt])
                return f'embed_ok:{len(output)}'
            encode = getattr(engine, 'encode', None)
            if callable(encode):
                output = encode([prompt])
                return f'encode_ok:{len(output)}'
            raise AttributeError('engine has no embed/encode method for embed task')
        output = engine.generate([prompt], sampling_params=sampling_params)
        return _extract_text(output)


def parse_args() -> argparse.Namespace:
    r"""Parse CLI args."""
    parser = argparse.ArgumentParser(description='Run vLLM loader PoC.')
    parser.add_argument('--model-id', default='', help='vLLM 模型 ID（非 dry-run 时必填）')
    parser.add_argument('--prompt', default='hello', help='测试 prompt')
    parser.add_argument('--max-loaded-models', type=int, default=1, help='最大驻留模型数')
    parser.add_argument(
        '--gpu-memory-utilization',
        type=float,
        default=0.05,
        help='vLLM GPU memory utilization ratio',
    )
    parser.add_argument(
        '--task',
        choices=('auto', 'generate', 'embed'),
        default='auto',
        help='vLLM task mode',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='使用 fake engine 跑通 loader 逻辑',
    )
    return parser.parse_args()


def main() -> None:
    r"""CLI entrypoint."""
    args = parse_args()
    text = run(
        args.model_id,
        prompt=args.prompt,
        max_loaded_models=args.max_loaded_models,
        dry_run=args.dry_run,
        gpu_memory_utilization=args.gpu_memory_utilization,
        task=args.task,
    )
    print(text)


if __name__ == '__main__':
    main()
