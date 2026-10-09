#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import dataclasses as dc
import datetime as dt
import enum
import json
import math
import os
import re
from pathlib import Path
import typing as tp

import typer


PROJECT_ROOT_DIR: Path = Path(os.environ["PROJECT_ROOT"]).resolve()
EXPERIMENTS_ROOT_DIR: Path = PROJECT_ROOT_DIR / 'experiments'
DEFAULT_SUBDIRS: tuple[str, ...] = ('artifacts', 'logs', 'results')
DEFAULT_RESULTS_FILE: str = 'results/metrics.json'
DEFAULT_CONCLUSION_FILE: str = 'results/conclusion.json'
DEFAULT_RUNTIME_ENV: str = 'default'
EXPERIMENT_NAME_PATTERN: re.Pattern[str] = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')

app = typer.Typer(no_args_is_help=True)


class Verdict(str, enum.Enum):
    r"""Experiment-level verdict."""

    FEASIBLE = '可行，建议继续 PoC'
    PARTIAL = '部分可行，需要保留部分现有调度逻辑'
    NOT_FEASIBLE = '不可行，继续沿用当前方案'


class MetricStatus(str, enum.Enum):
    r"""Per-metric evaluation status."""

    FEASIBLE = 'feasible'
    PARTIAL = 'partial'
    NOT_FEASIBLE = 'not_feasible'
    ERROR = 'error'


@dc.dataclass(frozen=True)
class ExperimentRuntimeSpec:
    r"""Runtime metadata for one experiment."""

    env_name: str = DEFAULT_RUNTIME_ENV
    features: list[str] = dc.field(default_factory=list)


@dc.dataclass(frozen=True)
class ExperimentManifest:
    r"""Experiment manifest schema."""

    name: str
    description: str = ''
    status: str = 'draft'
    runtime: ExperimentRuntimeSpec = dc.field(default_factory=ExperimentRuntimeSpec)
    entrypoint: str = ''
    metrics: list[str] = dc.field(default_factory=list)
    created_at: str = ''


@dc.dataclass(frozen=True)
class MetricRule:
    r"""Rule used to evaluate one metric."""

    objective: tp.Literal['maximize', 'minimize']
    feasible_ratio: float
    partial_ratio: float
    zero_is_error: bool = False


@dc.dataclass(frozen=True)
class MetricsPayload:
    r"""Metrics comparison payload schema."""

    baseline: dict[str, float]
    candidates: dict[str, dict[str, float]]
    rules: dict[str, MetricRule] = dc.field(default_factory=dict)


@dc.dataclass(frozen=True, slots=True)
class MetricEvaluation:
    r"""Per-metric evaluation entry."""

    baseline: float
    candidate: float
    ratio: float | None
    ratio_raw: str
    objective: tp.Literal['maximize', 'minimize']
    status: MetricStatus
    rule: MetricRule
    error_reason: str = ''


@dc.dataclass(frozen=True, slots=True)
class CandidateSummary:
    r"""Summary counts for one candidate."""

    metric_count: int
    feasible: int
    partial: int
    partial_or_better: int
    not_feasible: int
    error: int


@dc.dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    r"""Evaluation result for one candidate."""

    candidate_name: str
    verdict: Verdict
    score: int
    summary: CandidateSummary
    comparison: dict[str, MetricEvaluation]
    candidate: dict[str, float]


def get_experiments_root(root: Path | None = None) -> Path:
    r"""Return the experiments root directory."""
    return root if root is not None else EXPERIMENTS_ROOT_DIR


def normalize_experiment_name(name: str) -> str:
    r"""Validate and normalize an experiment name."""
    normalized = name.strip()
    if not normalized:
        raise ValueError('experiment name is empty')
    if normalized in {'.', '..'}:
        raise ValueError(f'invalid experiment name: {normalized!r}')
    if '/' in normalized or '\\' in normalized:
        raise ValueError(f'experiment name must not contain path separators: {normalized!r}')
    if not EXPERIMENT_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            'experiment name must start with an alphanumeric character and '
            'contain only alphanumerics, ".", "_", "-".',
        )
    return normalized


def get_experiment_dir(name: str, *, root: Path | None = None) -> Path:
    r"""Return the directory for a specific experiment."""
    return get_experiments_root(root) / normalize_experiment_name(name)


def _manifest_to_dict(manifest: ExperimentManifest) -> dict[str, tp.Any]:
    payload = dc.asdict(manifest)
    payload['runtime'] = dc.asdict(manifest.runtime)
    return payload


def _manifest_from_dict(payload: dict[str, tp.Any]) -> ExperimentManifest:
    runtime_raw = payload.get('runtime')
    if not isinstance(runtime_raw, dict):
        raise ValueError('manifest requires object field: runtime')

    runtime = ExperimentRuntimeSpec(
        env_name=str(runtime_raw.get('env_name', DEFAULT_RUNTIME_ENV)),
        features=[str(x) for x in runtime_raw.get('features', list[str]())],
    )

    created_at = payload.get('created_at')
    if not isinstance(created_at, str) or not created_at:
        created_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec='seconds')

    return ExperimentManifest(
        name=normalize_experiment_name(str(payload.get('name', ''))),
        description=str(payload.get('description', '')),
        status=str(payload.get('status', 'draft')),
        runtime=runtime,
        entrypoint=str(payload.get('entrypoint', '')),
        metrics=[str(item) for item in payload.get('metrics', list[str]())],
        created_at=created_at,
    )


def format_manifest(
    name: str,
    *,
    description: str = '',
    status: str = 'draft',
    runtime: ExperimentRuntimeSpec | None = None,
    entrypoint: str = '',
    metrics: tp.Sequence[str] = tuple[str, ...](),
    created_at: str | None = None,
) -> str:
    r"""Render the experiment manifest as pretty JSON."""
    if runtime is None:
        runtime = ExperimentRuntimeSpec()
    created_at = (
        created_at
        if created_at is not None
        else dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec='seconds')
    )
    manifest = ExperimentManifest(
        name=normalize_experiment_name(name),
        description=description,
        status=status,
        runtime=runtime,
        entrypoint=entrypoint,
        metrics=[str(item) for item in metrics],
        created_at=created_at,
    )
    return json.dumps(_manifest_to_dict(manifest), ensure_ascii=False, indent=2) + '\n'


def format_readme(name: str, *, description: str = '') -> str:
    r"""Render the experiment README."""
    description_line = description.strip() or '待补充。'
    return (
        f'# Experiment: {normalize_experiment_name(name)}\n\n'
        f'**目的**：{description_line}\n\n'
        '## 目录约定\n\n'
        '- `config.json`：实验配置\n'
        '- `artifacts/`：中间文件\n'
        '- `logs/`：运行日志\n'
        '- `results/`：最终结果\n\n'
        '## 使用方式\n\n'
        '1. 先更新 `config.json`（runtime、entrypoint、metrics）。\n'
        '2. 再根据实验需要补充脚本和结果。\n'
    )


def scaffold_experiment(
    name: str,
    *,
    description: str = '',
    root: Path | None = None,
) -> Path:
    r"""Create a new experiment directory structure."""
    exp_root = get_experiments_root(root)
    exp_dir = get_experiment_dir(name, root=exp_root)
    if exp_dir.exists():
        raise FileExistsError(f'experiment already exists: {exp_dir}')

    exp_dir.mkdir(parents=True, exist_ok=False)
    for subdir in DEFAULT_SUBDIRS:
        (exp_dir / subdir).mkdir(parents=True, exist_ok=False)
        (exp_dir / subdir / '.gitkeep').write_text('', encoding='utf-8')

    (exp_dir / 'README.md').write_text(
        format_readme(name, description=description),
        encoding='utf-8',
    )
    (exp_dir / 'config.json').write_text(
        format_manifest(
            name,
            description=description,
            metrics=('latency', 'throughput', 'gpu_memory'),
        ),
        encoding='utf-8',
    )
    return exp_dir


def list_experiments(*, root: Path | None = None) -> list[Path]:
    r"""List experiment directories under the root."""
    exp_root = get_experiments_root(root)
    if not exp_root.exists():
        return list[Path]()
    return sorted(
        path for path in exp_root.iterdir() if path.is_dir() and not path.name.startswith('.')
    )


def load_manifest(exp_dir: Path) -> ExperimentManifest:
    r"""Load an experiment manifest."""
    payload = json.loads((exp_dir / 'config.json').read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('manifest must be a JSON object')
    return _manifest_from_dict(payload)


def _parse_metric_rule(metric_name: str, payload: dict[str, tp.Any]) -> MetricRule:
    objective = payload.get('objective')
    if objective not in {'maximize', 'minimize'}:
        raise ValueError(
            f'metric rule {metric_name!r} has invalid objective: {objective!r}; '
            'expected "maximize" or "minimize"',
        )

    feasible_ratio = payload.get('feasible_ratio')
    partial_ratio = payload.get('partial_ratio')
    zero_is_error = payload.get('zero_is_error', False)
    if not isinstance(feasible_ratio, (int, float)) or not isinstance(partial_ratio, (int, float)):
        raise ValueError(
            f'metric rule {metric_name!r} requires numeric feasible_ratio/partial_ratio',
        )
    if not isinstance(zero_is_error, bool):
        raise ValueError(f'metric rule {metric_name!r} field zero_is_error must be bool')

    feasible_ratio_f = float(feasible_ratio)
    partial_ratio_f = float(partial_ratio)

    if objective == 'maximize' and feasible_ratio_f < partial_ratio_f:
        raise ValueError(
            f'metric rule {metric_name!r} invalid: maximize requires '
            'feasible_ratio >= partial_ratio',
        )
    if objective == 'minimize' and feasible_ratio_f > partial_ratio_f:
        raise ValueError(
            f'metric rule {metric_name!r} invalid: minimize requires '
            'feasible_ratio <= partial_ratio',
        )

    return MetricRule(
        objective=tp.cast(tp.Literal['maximize', 'minimize'], objective),
        feasible_ratio=feasible_ratio_f,
        partial_ratio=partial_ratio_f,
        zero_is_error=zero_is_error,
    )


def _infer_metric_rule(metric_name: str) -> MetricRule:
    token = metric_name.lower()
    if 'memory' in token or token.endswith('_mem'):
        return MetricRule(
            objective='minimize',
            feasible_ratio=1.0,
            partial_ratio=1.2,
            zero_is_error=True,
        )

    maximize_keywords = ('throughput', 'qps', 'accuracy', 'recall', 'precision', 'success')
    if any(word in token for word in maximize_keywords):
        return MetricRule(objective='maximize', feasible_ratio=1.0, partial_ratio=0.9)

    return MetricRule(objective='minimize', feasible_ratio=1.0, partial_ratio=1.2)


def _parse_metric_values(*, source: dict[str, tp.Any], role: str) -> dict[str, float]:
    result = dict[str, float]()
    for metric_name, raw_value in source.items():
        if not isinstance(raw_value, (int, float)):
            raise ValueError(f'{role} metric {metric_name!r} must be numeric')
        metric_value = float(raw_value)
        if metric_value < 0:
            raise ValueError(f'{role} metric {metric_name!r} must be non-negative')
        result[str(metric_name)] = metric_value
    return result


def load_metrics(path: Path) -> MetricsPayload:
    r"""Load and validate experiment metrics payload."""
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('metrics payload must be a JSON object')

    baseline_raw = payload.get('baseline')
    if not isinstance(baseline_raw, dict):
        raise ValueError('metrics payload requires object field: baseline')
    baseline = _parse_metric_values(source=baseline_raw, role='baseline')

    candidates_raw = payload.get('candidates')
    if not isinstance(candidates_raw, dict):
        raise ValueError('metrics payload requires object field: candidates')

    candidates = dict[str, dict[str, float]]()
    for name, raw_metrics in candidates_raw.items():
        if not isinstance(raw_metrics, dict):
            raise ValueError(f'candidate {name!r} must be a JSON object')
        candidates[str(name)] = _parse_metric_values(source=raw_metrics, role=f'candidate:{name}')

    if not candidates:
        raise ValueError('metrics payload requires at least one candidate')

    for candidate_name, values in candidates.items():
        overlap = set(baseline) & set(values)
        if not overlap:
            raise ValueError(
                f'candidate {candidate_name!r} has no shared metric with baseline',
            )

    rules_raw = payload.get('rules', dict[str, tp.Any]())
    if not isinstance(rules_raw, dict):
        raise ValueError('metrics payload field rules must be a JSON object when provided')

    rules = dict[str, MetricRule]()
    for metric_name, raw_rule in rules_raw.items():
        if not isinstance(raw_rule, dict):
            raise ValueError(f'metric rule {metric_name!r} must be a JSON object')
        rules[str(metric_name)] = _parse_metric_rule(str(metric_name), raw_rule)

    return MetricsPayload(baseline=baseline, candidates=candidates, rules=rules)


def _compute_ratio(*, baseline: float, candidate: float) -> float:
    if baseline == 0.0:
        return 1.0 if candidate == 0.0 else float('inf')
    return candidate / baseline


def _grade_metric(*, ratio: float, rule: MetricRule) -> MetricStatus:
    if rule.objective == 'maximize':
        if ratio >= rule.feasible_ratio:
            return MetricStatus.FEASIBLE
        if ratio >= rule.partial_ratio:
            return MetricStatus.PARTIAL
        return MetricStatus.NOT_FEASIBLE

    if ratio <= rule.feasible_ratio:
        return MetricStatus.FEASIBLE
    if ratio <= rule.partial_ratio:
        return MetricStatus.PARTIAL
    return MetricStatus.NOT_FEASIBLE


def _metric_eval_to_dict(metric_eval: MetricEvaluation) -> dict[str, tp.Any]:
    payload = dataclasses.asdict(metric_eval)
    payload['status'] = metric_eval.status.value
    payload['rule'] = dataclasses.asdict(metric_eval.rule)
    return payload


def _candidate_eval_to_dict(candidate_eval: CandidateEvaluation) -> dict[str, tp.Any]:
    return {
        'candidate_name': candidate_eval.candidate_name,
        'verdict': candidate_eval.verdict.value,
        'score': candidate_eval.score,
        'summary': dataclasses.asdict(candidate_eval.summary),
        'comparison': {
            metric_name: _metric_eval_to_dict(metric_eval)
            for metric_name, metric_eval in candidate_eval.comparison.items()
        },
        'candidate': candidate_eval.candidate,
    }


def _evaluate_candidate(
    *,
    candidate_name: str,
    baseline: dict[str, float],
    candidate: dict[str, float],
    rules: dict[str, MetricRule],
) -> CandidateEvaluation:
    per_metric = dict[str, MetricEvaluation]()

    for metric_name in sorted(set(baseline) & set(candidate)):
        baseline_v = baseline[metric_name]
        candidate_v = candidate[metric_name]
        rule = rules.get(metric_name, _infer_metric_rule(metric_name))

        if rule.zero_is_error and baseline_v > 0 and candidate_v == 0:
            per_metric[metric_name] = MetricEvaluation(
                baseline=baseline_v,
                candidate=candidate_v,
                ratio=None,
                ratio_raw='',
                objective=rule.objective,
                status=MetricStatus.ERROR,
                rule=rule,
                error_reason='candidate value is zero but metric rule marks zero as invalid',
            )
            continue

        ratio = _compute_ratio(baseline=baseline_v, candidate=candidate_v)
        status = _grade_metric(ratio=ratio, rule=rule)
        ratio_value: float | None = round(ratio, 6) if math.isfinite(ratio) else None
        per_metric[metric_name] = MetricEvaluation(
            baseline=baseline_v,
            candidate=candidate_v,
            ratio=ratio_value,
            ratio_raw=str(ratio) if ratio_value is None else '',
            objective=rule.objective,
            status=status,
            rule=rule,
        )

    statuses = [item.status for item in per_metric.values()]
    feasible_cnt = sum(1 for status in statuses if status == MetricStatus.FEASIBLE)
    partial_cnt = sum(1 for status in statuses if status == MetricStatus.PARTIAL)
    error_cnt = sum(1 for status in statuses if status == MetricStatus.ERROR)
    partial_or_better_cnt = feasible_cnt + partial_cnt

    if error_cnt > 0:
        verdict = Verdict.NOT_FEASIBLE
    elif feasible_cnt == len(statuses):
        verdict = Verdict.FEASIBLE
    elif partial_or_better_cnt == len(statuses):
        verdict = Verdict.PARTIAL
    else:
        verdict = Verdict.NOT_FEASIBLE

    score = feasible_cnt * 2 + partial_cnt
    summary = CandidateSummary(
        metric_count=len(statuses),
        feasible=feasible_cnt,
        partial=partial_cnt,
        partial_or_better=partial_or_better_cnt,
        not_feasible=len(statuses) - partial_or_better_cnt - error_cnt,
        error=error_cnt,
    )

    return CandidateEvaluation(
        candidate_name=candidate_name,
        verdict=verdict,
        score=score,
        summary=summary,
        comparison=per_metric,
        candidate=candidate,
    )


def build_conclusion(metrics: MetricsPayload) -> dict[str, tp.Any]:
    r"""Build a generic conclusion payload from baseline and one/many candidates."""
    evaluated = dict[str, CandidateEvaluation]()
    for name, candidate in sorted(metrics.candidates.items()):
        evaluated[name] = _evaluate_candidate(
            candidate_name=name,
            baseline=metrics.baseline,
            candidate=candidate,
            rules=metrics.rules,
        )

    ranking = sorted(
        (
            {
                'candidate': name,
                'verdict': result.verdict.value,
                'score': result.score,
            }
            for name, result in evaluated.items()
        ),
        key=lambda item: (-int(item['score']), str(item['candidate'])),
    )

    feasible = [name for name, res in evaluated.items() if res.verdict == Verdict.FEASIBLE]
    partial = [name for name, res in evaluated.items() if res.verdict == Verdict.PARTIAL]
    not_feasible = [name for name, res in evaluated.items() if res.verdict == Verdict.NOT_FEASIBLE]

    recommended_candidate = ranking[0]['candidate'] if ranking else ''

    if len(evaluated) == 1:
        single_name, single = next(iter(evaluated.items()))
        single_payload = _candidate_eval_to_dict(single)
        return {
            'verdict': single.verdict.value,
            'summary': single_payload['summary'],
            'comparison': single_payload['comparison'],
            'baseline': metrics.baseline,
            'candidate': single.candidate,
            'candidate_name': single_name,
            'candidates': {name: _candidate_eval_to_dict(res) for name, res in evaluated.items()},
            'ranking': ranking,
            'recommended_candidate': recommended_candidate,
        }

    return {
        'summary': {
            'candidate_count': len(evaluated),
            'feasible_candidates': feasible,
            'partial_candidates': partial,
            'not_feasible_candidates': not_feasible,
        },
        'baseline': metrics.baseline,
        'candidates': {name: _candidate_eval_to_dict(res) for name, res in evaluated.items()},
        'ranking': ranking,
        'recommended_candidate': recommended_candidate,
    }


def format_summary(exp_dir: Path) -> str:
    r"""Render a one-line summary for an experiment directory."""
    manifest = load_manifest(exp_dir)
    runtime = manifest.runtime
    features = ','.join(runtime.features)
    runtime_repr = runtime.env_name if not features else f'{runtime.env_name} [{features}]'
    return '\t'.join(
        [
            manifest.name,
            manifest.status,
            runtime_repr,
            manifest.description,
        ],
    )


@app.command()
def init(
    name: str = typer.Argument(..., help='实验名称'),
    *,
    description: str = typer.Option('', '--description', '-d', help='实验描述'),
) -> None:
    r"""Create a new experiment directory."""
    exp_dir = scaffold_experiment(name, description=description)
    typer.echo(str(exp_dir))


@app.command('list')
def list_cmd() -> None:
    r"""List existing experiments."""
    for exp_dir in list_experiments():
        typer.echo(format_summary(exp_dir))


@app.command()
def show(
    name: str = typer.Argument(..., help='实验名称'),
) -> None:
    r"""Show the experiment manifest."""
    exp_dir = get_experiment_dir(name)
    manifest = load_manifest(exp_dir)
    typer.echo(json.dumps(_manifest_to_dict(manifest), ensure_ascii=False, indent=2))


@app.command()
def conclude(
    name: str = typer.Argument(..., help='实验名称'),
    *,
    input_file: str = typer.Option(
        DEFAULT_RESULTS_FILE,
        '--input',
        '-i',
        help='输入 metrics JSON（相对实验目录）',
    ),
    output_file: str = typer.Option(
        DEFAULT_CONCLUSION_FILE,
        '--output',
        '-o',
        help='输出 conclusion JSON（相对实验目录）',
    ),
) -> None:
    r"""Generate conclusion from metrics payload."""
    exp_dir = get_experiment_dir(name)
    metrics_path = exp_dir / input_file
    conclusion_path = exp_dir / output_file

    metrics = load_metrics(metrics_path)
    conclusion = build_conclusion(metrics)

    conclusion_path.parent.mkdir(parents=True, exist_ok=True)
    conclusion_path.write_text(
        json.dumps(conclusion, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    typer.echo(str(conclusion_path))


def main() -> None:
    r"""CLI entry point."""
    app()


if __name__ == '__main__':
    main()
