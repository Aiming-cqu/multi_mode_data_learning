# Experiments

实验统一放在 `experiments/{exp}/...` 下，每个实验目录至少包含：

- `README.md`：实验目标、范围、结果摘要
- `config.json`：实验配置（runtime/entrypoint/metrics）
- `artifacts/`：中间文件
- `logs/`：运行日志
- `results/`：最终结果

## 环境约定

- `lib/utils/experiments.py` 以 `PROJECT_ROOT` 环境变量为主（由 Pixi activation 注入），缺失时才回退到代码路径推断。
- 建议始终通过 Pixi 执行实验命令，以保证 `PROJECT_ROOT` 与依赖环境一致。

## 通用命令入口

统一使用一个 Pixi 入口：

```bash
pixi run exp -- --help
pixi run exp -- list
pixi run exp -- init gpu-concurrency-vllm
pixi run exp -- show gpu-concurrency-vllm
pixi run exp -- conclude gpu-concurrency-vllm
```

> 说明：具体实验运行脚本（例如 vLLM PoC）继续保留在独立任务中，不塞进通用 CLI。

## 一次实验支持几个 candidate？

- **支持多个 candidate。**
- `results/metrics.json` 使用：`baseline + candidates`。

## 结论生成（通用规则）

`conclude` 从 `results/metrics.json` 读取：

- `baseline`: 基线指标字典
- `candidates`: 多候选指标字典
- `rules`（可选）: 每个指标的判定规则

示例：

```json
{
  "baseline": {"latency": 1.0, "throughput": 3.0},
  "candidates": {
    "vllm": {"latency": 1.2, "throughput": 2.8},
    "hf": {"latency": 1.0, "throughput": 3.1}
  }
}
```

当 `rules` 缺失时，工具会按指标名自动推断目标（如 throughput 倾向 maximize，latency/memory 倾向 minimize）。

## 结果文件的版本管理约定

- `artifacts/`、`logs/`、`results/` 默认存放运行产物，不建议直接提交。
- 如需保留“决策级结果”，建议只提交少量稳定文件（例如 `metrics.json`/`conclusion.json`）。
