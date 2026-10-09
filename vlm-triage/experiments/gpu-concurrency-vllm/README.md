# Experiment: gpu-concurrency-vllm

**目的**：评估 vLLM Python API 在 GPU 并发模型推理场景中的调度能力，并作为后续 PoC 的主实验目录。

## 目录约定

- `config.json`：实验配置
- `artifacts/`：中间产物
- `logs/`：运行日志
- `results/`：最终结果

## 当前状态

- 重点关注 loader 入口保持稳定
- vLLM 环境固定为 `vllm-base + vllm-extras`
- 后续结果统一沉淀到 `results/`

## 结论产出

1. 填写 `results/metrics.json`（基线 vs 候选）。
2. 执行 `pixi run exp -- conclude gpu-concurrency-vllm`。
3. 检查 `results/conclusion.json`，并把结论同步回看板卡片。


## 运行前检查（避免超时/显存误判）

1. 首次请先执行：`pixi install -e vllm`（预热环境，避免把依赖下载当成脚本超时）。
2. 先执行 dry-run：`pixi run exp-run-loader-poc`。
3. real-run 先用小模型：`Qwen/Qwen2.5-0.5B-Instruct`。
4. `--gpu-memory-utilization` 建议从 `0.05` 起步，确认稳定后再放大。

## Loader PoC 运行

```bash
# 干跑：验证 vLLM loader 调度路径
pixi run exp-run-loader-poc

# 真跑：替换模型后触发真实 vLLM 请求
pixi run exp-run-loader-poc-vllm --model-id Qwen/Qwen2.5-0.5B-Instruct --prompt "hello"

# 或直接在 vllm 环境运行
pixi run -e vllm -- python experiments/gpu-concurrency-vllm/run_loader_poc.py \
  --model-id Qwen/Qwen2.5-0.5B-Instruct \
  --prompt "hello"
```

## 三模型基准（CLIP / AIMv2 / DINO）

```bash
# 推荐：避免 pixi 触发环境更新
pixi run --as-is -e vllm -- python experiments/gpu-concurrency-vllm/benchmark_loader_models.py

# 若本 worktree 的 vllm 环境缺包，可显式指定已有 vllm python
PY=/home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/bin/python
python experiments/gpu-concurrency-vllm/benchmark_loader_models.py --python-bin "$PY"
```

产物：
- `results/loader_metrics_<timestamp>.json`
- `results/loader_metrics_latest.json`

指标字段：
- `latency_seconds`：单模型一次 PoC 请求耗时
- `throughput_qps`：吞吐代理（`1 / latency_seconds`，失败时为 0）
- `memory_before_mib` / `memory_after_mib` / `memory_delta_mib`：`nvidia-smi` 轻量采样
