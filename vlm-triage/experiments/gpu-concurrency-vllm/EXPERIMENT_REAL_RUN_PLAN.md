# vLLM PoC 实验 - Real-Run 执行方案

## 目标

对比当前 `ModelLoaderBase + EmbeddingExtractorLoader` 方案（Baseline）vs `VllmModelLoader` 方案（Candidate）的性能指标，为是否推进 vLLM 化改造提供数据支撑。

## 实验设置

### Baseline（当前生产方案）
- **加载器**：`lib/loaders/embedding_extractor_loader.py` (ModelLoaderBase)
- **模型**：CLIP-ViT-Base-32（openai/clip-vit-base-patch32）
- **并发数**：8
- **GPU 显存限制**：6GB
- **任务**：图像编码 (100 张随机图像)
- **输出指标**：
  - `latency` (ms)：单张图像编码平均延迟
  - `throughput` (images/s)：吞吐量
  - `gpu_memory` (GB)：峰值显存占用

### Candidate（vLLM 方案）
- **加载器**：`lib/services/vllm_loader.py` (VllmModelLoader)
- **模型**：同 Baseline
- **并发数**：8
- **GPU 显存限制**：6GB
- **任务**：同 Baseline
- **输出指标**：同 Baseline

## Real-Run 核心问题与验证目标

### 问题1：vLLM 对 CLIP 的支持

**理论预测**（基于 vLLM v0.11.0 源码分析）：
- vLLM 不在支持列表中包含 CLIP（只支持 LLM 和部分多模态生成模型）
- `LLM(model="clip-vit-base-32")` 会抛出 `NotImplementedError: get_input_embeddings not auto-handled`

**Real-Run 验证**：
- ✅ 若加载成功：说明 vLLM 版本支持更多模型，需进一步测试推理性能
- ❌ 若加载失败：印证不兼容性，实验结束，维持当前方案

### 问题2：VllmModelLoader 的性能（若能加载）

需要测量以下指标：
- **Latency**：单张图像编码延迟 (ms)
- **Throughput**：吞吐量 (images/s)
- **GPU Memory**：峰值显存占用 (GB)
- **Success Rate**：并发请求成功率 (%)

### 问题3：与 Baseline 的对标

计算以下比例：
```
throughput_ratio = candidate_throughput / baseline_throughput
latency_ratio = candidate_latency / baseline_latency
gpu_memory_ratio = candidate_gpu_memory / baseline_gpu_memory
```

**判定规则**：
- ✅ **Feasible**：`throughput >= baseline * 90% AND latency <= baseline * 110% AND gpu_memory <= baseline * 115%`
- ⚠️ **Partial**：`throughput >= baseline * 80% AND latency <= baseline * 130% AND gpu_memory <= baseline * 130%`
- ❌ **Not Feasible**：其他情况

## 预期结果

基于当前架构分析，预期如下：

### 最可能情况（90% 概率）
- **vLLM 加载 CLIP 失败**
- 错误信息：`NotImplementedError: get_input_embeddings not auto-handled`
- **结论**：vLLM 不支持视觉编码器，实验不进行，维持当前方案
- **输出**：failure 日志 + 决策记录

### 低概率情况（10% 概率）
若意外加载成功：
- vLLM 版本可能支持更多模型
- 需要完成 Candidate 性能测量
- 对标 Baseline 指标并生成结论

**即使成功加载**，根据架构分析，预期：
- vLLM 在单个编码器上性能可能略优（批处理优化）
- 但增加了环境复杂度和维护成本
- 短期内不推荐替换

## Real-Run 执行步骤

### 前置条件
- 可联网环境（支持 PyPI、HuggingFace Hub 下载）
- GPU 设备（至少 6GB 显存）
- vLLM 环境已配置（`pixi shell -e vllm`）

### 执行命令

#### 1. Baseline Run
```bash
cd /path/to/vlm-triage.worktrees/copilot-gpu-offloading-vllm-scheduling

# 使用原生 ModelLoaderBase 运行
# （需要 experiments/gpu-concurrency-vllm/run_loader_poc.py 支持 --loader-type 标志）
pixi run exp-run-loader-poc -- --task clip --dry-run

# real-run（计算实际指标）
python experiments/gpu-concurrency-vllm/run_loader_poc.py \
  --task clip \
  --num-concurrent 8 \
  --gpu-memory-utilization 0.3
```

#### 2. Candidate Run
```bash
# 在 vllm 环境中运行
pixi run exp-run-loader-poc-vllm -- --task clip --num-concurrent 8
```

#### 3. 生成结论
```bash
# 自动对标两个 metrics.json 并输出 conclusion.json
pixi run exp-conclude
```

## 预期输出

### `results/metrics.json`
```json
{
  "baseline": {
    "latency": <float>,
    "throughput": <float>,
    "gpu_memory": <float>,
    "success_rate": <float>,
    "timestamp": "<ISO8601>"
  },
  "candidate": {
    "latency": <float>,
    "throughput": <float>,
    "gpu_memory": <float>,
    "success_rate": <float>,
    "timestamp": "<ISO8601>"
  }
}
```

### `results/conclusion.json`
```json
{
  "verdict": "feasible | partial | not_feasible | experiment_failed",
  "reason": "<string>",
  "comparison": {
    "throughput_ratio": <float>,
    "latency_ratio": <float>,
    "gpu_memory_ratio": <float>
  },
  "baseline": { ... },
  "candidate": { ... }
}
```

## 关键假设与风险

### 假设1：vLLM 不支持 CLIP
- **来源**：vLLM 源码分析 + 官方文档
- **风险**：低（vLLM 设计明确针对 LLM）
- **验证**：Real-Run 会立即确认

### 假设2：即使加载成功，性能不会显著优于当前方案
- **理由**：
  - vLLM 的优化针对生成任务的 KV cache，而非嵌入提取
  - 新增环境复杂度反而可能增加开销
- **风险**：中低（可能被性能意外击中）
- **应对**：Real-Run 数据会决定去留

### 假设3：环境复杂度显著增加
- **来源**：实验中多次遇到 PyPI 超时、依赖冲突
- **风险**：高（已观测到）
- **应对**：已记录防踩坑指南，后续保持隔离的 vllm 环境

## 记录与回溯

本实验方案设计的核心目标：
1. **验证架构不兼容性**（主线）
2. **获取性能对标数据**（备线，若加载成功）
3. **为决策提供充分证据**（最终目的）

即使 Real-Run 未能完成（因环境限制），本 PoC 代码本身已提供了：
- 完整的 vLLM 集成参考
- 实验框架与管理工具
- 防踩坑指南

这些都是后续项目的可复用资产。

---

**本文档最后更新**：2026-05-15 01:50 UTC
**实验状态**：Ready for Real-Run（等待可联网 GPU 环境）
