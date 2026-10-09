# SOTA 模型调研

| 属性 | 值 |
| ---- | --- |
| ID | sota-model-research |
| 类型 | task |
| 优先级 | medium |
| 状态 | active |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

调研可接入的 SOTA 模型，将结论沉淀为两类落地形式：能走 vLLM 的保留/新增 serve 脚本，不能走的转为 reference inference 参考实现。

## 背景

随着 Qwen3.6、Gemma 4、Kimi-VL、Keye-VL 等新模型发布，需要系统性评估哪些能稳定在 vLLM 上 serve，哪些需要走替代路径。

## 范围

**在范围内：**

- 模型兼容性验证（vLLM vs HF/Transformers）
- serve 脚本维护（`scripts/model-serving/*.sh`）
- 参考推理实现（`models/inference_*.py`）
- 环境问题记录和排查

**不在范围内：**

- 不涉及模型训练/微调
- 不替代 CR 定位评测框架（那是聚合算法优化任务的范畴）

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| vLLM 可服务模型数 | 已有 Qwen3.5/CLIP/DINOv2 等 | 新增 ≥ 3 个 serve 脚本 | 脚本可启动且冒烟测试通过 |
| 不兼容模型覆盖 | 无 | 每个不兼容模型有 inference_*.py 参考实现 | 代码审查 |
| 环境问题文档化 | 散落 | 每个已知问题记录到本文档 | 审计 |

## Related Skill

- `docs/skills/adding-vllm-serve-scripts/SKILL.md`：当调研结论要落到 serve 脚本或 reference inference 时，按这里的环境、parser、trait、多卡、fallback 和校验规则执行。

## 当前结论

| 模型 | 当前结论 | 推荐入口 | 关键说明 |
|------|----------|----------|----------|
| Qwen3.6-27B-FP8 | 保留 serve 脚本 | `scripts/model-serving/vllm-serve-qwen3.6_27b.sh` | MTP 已开启 (`qwen3_next_mtp`, 2 tokens)；延续 Qwen3.5 / Qwen3.6 parser 组合；需 vllm-latest |
| Qwen3.6-35B-A3B-FP8 | 保留 serve 脚本 | `scripts/model-serving/vllm-serve-qwen3.6_35b_a3b.sh` | MTP 已开启；MOE 路径，GDN prefill 用 triton backend，按现有 Qwen3.6 规则接入；需 vllm-latest |
| Qwen3.5-27B-FP8 | 保留 serve 脚本 | `scripts/model-serving/vllm-serve-qwen3.5_27b.sh` | MTP 已开启；需 vllm-latest |
| Gemma 4 26B / 31B | 保留 serve 脚本 | `scripts/model-serving/vllm-serve-gemma_4_26b_a4b.sh` / `scripts/model-serving/vllm-serve-gemma_4_31b.sh` | H20 场景默认双卡 TP 更稳 |
| Kimi-VL-A3B | 保留 serve 脚本 | `scripts/model-serving/vllm-serve-kimi_vl_a3b.sh` | 当前应使用 `vllm-latest`；无 server parser |
| Keye-VL-1.5-8B | 保留 serve 脚本 | `scripts/model-serving/vllm-serve-keye_vl_1.5_8b.sh` | 无 server parser；思维开关由 prompt 驱动 |
| Qwen3-Omni-30B-A3B-Thinking-AWQ-4bit | 保留受限 serve 脚本 | `scripts/model-serving/vllm-serve-qwen3_omni_30b.sh` | 当前应使用 `vllm-latest`；需 `--trust-remote-code` 与 `VLLM_USE_V1=0`；ModelScope 镜像 `BackendSupport.vllm = null`，当前仓库按 image-only / text-output 使用；本地 `precompiled` wheel 还可能在 Marlin 路径报 PTX toolchain mismatch |
| Llama-3.2-11B-Vision | 暂不作为稳定 serve 入口 | `scripts/model-serving/vllm-serve-llama_3.2_11b_vision.sh` | 路径规范化后可读到模型，但当前 generic transformers multimodal backend 仍因 `MllamaProcessor` 缺 `_get_num_multimodal_tokens` 而失败 |
| Qwen3-235B-A22B-FP8 | 仅保留 4-GPU 参考脚本 | `scripts/model-serving/vllm-serve-qwen3_235b_a22b.sh` | 当前双 H20 默认 profile 在加载阶段直接 OOM，不应再视为稳定 2xH20 serve 入口 |
| ERNIE-4.5-VL-28B-A3B-PT | 不新增 serve 脚本 | `models/inference_ernie_45_vl.py` | `BackendSupport.vllm = null`，当前以 reference inference 为准 |
| Valley-Eagle-7B | 不新增 serve 脚本 | `models/inference_valley_eagle_7b.py` | `BackendSupport.vllm = null`，且当前环境报 `model type valley` 未识别 |
| InternVL3.5-38B-Flash | 暂不作为稳定 serve 入口 | - | raw `video` 输入不稳，Flash 权重加载还会遇到 `mlp2` 结构不匹配 |

## 环境问题记录

### 2026-05-13 FlashInfer JIT 编译失败（GDA prefill kernel）

**现象**：vLLM 启动时 FlashInfer 0.6.6 JIT 编译 `gdn_prefill_sm90` 失败：

```
fatal error: flashinfer/flat/prefill/prefill_kernel_delta_rule_sm90.cuh: No such file or directory
```

**根因**：FlashInfer 的 JIT 缓存是在 Python 3.13 环境中编译的（luonairui 的原始环境），
nvcc 命令中的 include 路径硬编码了 `python3.13`：
- `-isystem .../include/python3.13`
- `-isystem .../lib/python3.13/site-packages/flashinfer/data/include`

但当前 vllm-latest 环境是 Python 3.12，实际 flashinfer 头文件在 `python3.12/site-packages/` 下，
头文件本身存在（`prefill_kernel_delta_rule_sm90.cuh`），只是路径不匹配导致 nvcc 找不到。

**修复方式**：
```bash
rm -rf /home/luban/.cache/flashinfer/0.6.6/90a
```
清除 JIT 缓存后，下次 vLLM 启动时 FlashInfer 会用正确的 Python 3.12 路径重新编译。

**状态**：已清除缓存并重启，Qwen3.6-27B-FP8 端口 8031 启动成功，FlashInfer GDN prefill kernel 编译通过。

## Iteration 20260517.1800

- 补充环境问题记录：FlashInfer JIT 编译失败排查与修复
- 根因明确：Python 3.13 环境编译的 JIT 缓存与当前 vllm-latest 环境 Python 3.12 头文件路径不匹配
- 修复方式：清除 `~/.cache/flashinfer/0.6.6/90a` 后重建

## 待继续调研

- 商用可接入模型
- 其他需要额外量化形态或上下文扩展参数的模型
