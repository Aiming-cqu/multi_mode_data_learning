---
name: adding-vllm-serve-scripts
description: 为新模型创建、审查和修正 vLLM serve 脚本，包括选择 vllm 或 vllm-latest 环境、复用同家族 parser、设置 served-model-name trait、处理 GPU 与端口规则、补充 trust-remote-code 和多模态参数。当用户提到“新增 vllm serve 脚本”、“模型接入 scripts/model-serving”、“补充模型服务启动脚本”、“审查 serve 脚本”或“为某个模型生成 vllm serve 脚本”时使用。
---

# Adding vLLM Serve Scripts Skill

Act 类技能：为 `scripts/model-serving/` 新增、修正或审查 vLLM serve 脚本。

## 何时使用

- 接入一个新的模型到 `scripts/model-serving/`
- 审查现有脚本的环境、parser、trait、多卡和多模态参数
- 判断某个模型应继续走 `vllm serve`，还是应该回退到 `models/inference_*.py`

## 先读什么

动手前先读这几类上下文：

```bash
view docs/rules/coding-guidelines.md
view scripts/activation/vllm.sh
view pyproject.toml
glob scripts/model-serving/*.sh
rg 'tool-call-parser|reasoning-parser|served-model-name|trust-remote-code' scripts/model-serving
```

不要从零发明参数。优先复用“同家族、同能力、同部署形态”的最近亲脚本。

## 证据优先级

写脚本时按下面的优先级做判断：

1. **本地日志**：`logs/model-serving-test.log` 和 `logs/test-vllm-serve-*.log`
2. **仓库现状**：`scripts/model-serving/` 里同家族脚本、`scripts/activation/vllm.sh` 的全局默认值
3. **上游事实**：ModelScope `BackendSupport.vllm`、官方 README、模型卡里的上下文长度 / trust-remote-code / 多模态输入约束
4. **Skill 文案**：只作为规则摘要，不能覆盖前 3 项

如果日志、现有脚本、上游信息三者冲突，以**本地最新事实**为准，并把结论写回脚本注释或文档。

## 决策顺序

1. 先看相关本地日志，确认当前是路径/缓存、参数、PTX/toolchain、OOM 还是后端兼容性问题
2. 再看同家族现有脚本和 `scripts/activation/vllm.sh`，优先复用已验证模式
3. 再用 ModelScope / 上游 README 补齐上下文长度、`trust_remote_code`、多模态约束等事实
4. 根据显存与用户场景决定单卡还是双卡
5. 如果没有稳定的 vLLM 路径，就改走 `models/inference_*.py`

## 仓库里的稳定骨架

```sh
#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e <env> -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e <env> -- sh

set -eu

test -z "${MODELSCOPE_CACHE}" && echo '❗️ MODELSCOPE_CACHE required to be set' && exit 1
test -z "${VLLM_SERVE_<TYPE>_ARGS}" && echo '❗️ VLLM_SERVE_<TYPE>_ARGS required to be set' && exit 1

GPU=${1:-0} # numeric
PORT=803${GPU%%,*}

ARGS="${VLLM_SERVE_<TYPE>_ARGS}"
ARGS="${ARGS} <model-specific-flags>"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/<org>/<model>" \
	--served-model-name <full-name> <short-name> <traits...> ${GPU} "$@" \
	--port ${PORT} # multi # numeric
```

其中：

- 文本模型使用 `VLLM_SERVE_LLM_ARGS`
- 多模态模型使用 `VLLM_SERVE_VLM_ARGS`
- 多模态全局默认值以 `scripts/activation/vllm.sh` 为准，不要在单个脚本里重复发明

## 环境选择

| 环境 | 适用场景 | 当前基线 |
|------|----------|----------|
| `vllm` | 常规模型、已有稳定 parser、无需最新 transformers / vLLM 特性 | `vllm >=0.11`，`transformers 4.57.x` |
| `vllm-latest` | 新模型、自定义新版依赖、当前 `vllm` 环境缺符号或缺处理器能力 | `vllm >=0.19`，`transformers 5.6.x` |

规则：

1. 能用 `vllm` 跑通，就优先 `vllm`
2. 只有确实依赖新版 vLLM / transformers / mm-processor 时才切到 `vllm-latest`
3. 上游 README 的原生依赖要保留成注释，但不要误写成当前 Pixi 环境事实

推荐注释写法：

```sh
# pixi env: vllm-latest (vllm 0.19.x + transformers 5.5.x)
# upstream native inference reference (non-pixi):
#   conda create -n bagel python=3.10 -y
#   conda activate bagel
#   pip install -r requirements.txt
#     transformers==4.49.0
#   pip install flash_attn==2.5.8 --no-build-isolation
```

如果来源明确提到了 YaRN / rope scaling / rope theta / original max position embeddings，把对应参数写成注释模板保留在脚本里，便于后续试验：

```sh
# ARGS="${ARGS} --rope-scaling '{\"rope_type\":\"yarn\",\"factor\":4.0,\"original_max_position_embeddings\":32768}'"
```

## parser 选择

不要按品牌名猜 parser，优先复用同家族现有脚本。

| 模型家族 | tool-call parser | reasoning parser | 参考脚本 |
|----------|------------------|------------------|----------|
| Qwen3 | `hermes` | `deepseek_r1` | `vllm-serve-qwen3_32b.sh` |
| Qwen3.5 / Qwen3.6 | `qwen3_coder` | `qwen3` | `vllm-serve-qwen3.5_27b.sh` |
| Qwen3-VL | `hermes` | `qwen3` | `vllm-serve-qwen3_vl_30b_a3b.sh` |
| Gemma 4 | `gemma4` | `gemma4` | `vllm-serve-gemma_4_e4b.sh` |
| GLM 4.5V / 4.6V | `glm45` | `glm45` | `vllm-serve-glm_4.6v.sh` |

补充规则：

- reasoning parser 只有在输出约定稳定、且已知 vLLM 能识别时才加
- Thinking mode 依赖 system prompt 的模型，不要误加 `ThinkSwitch` 或生造 reasoning parser
- 如果上游视频示例本质上是“先拆帧成多张 `<image>` 再推理”，不要默认它稳定支持 OpenAI `video` 输入

## served-model-name 与 trait

`--served-model-name` 不只是别名，也承载上层路由语义。

至少检查这些 trait：

- `AgentModel`
- `CoderModel`
- `CompletionModel`
- `ReasonModel`
- `ThinkSwitch`
- `VisionModel`

经验规则：

- 只要脚本使用 `VLLM_SERVE_VLM_ARGS`，默认就要重新确认是否应带 `VisionModel`
- 漏掉 `VisionModel` 会导致上层按能力路由时漏选
- `ThinkSwitch` 只用于“同一 serve 支持思维开关”的模型，不适合 system prompt 驱动或固定思维模式

## GPU 与端口策略

### 单卡

```sh
GPU=${1:-0} # numeric
PORT=803${GPU%%,*}
```

### 多卡

```sh
GPU="${1:-0,1}"
PORT=803${GPU%%,*}
GPU_COUNT=$(echo "${GPU}" | awk -F',' '{print NF}')
GPU_NAMES="$(echo "${GPU}" | tr ',' ' ')"

if [ ${GPU_COUNT} -gt 1 ]
then
	ARGS="${ARGS} --tensor-parallel-size ${GPU_COUNT}"
fi
```

规则：

- 默认多卡时用逗号分隔 GPU 列表，不要写死 `0,1`
- GPU 个数统一用 `awk -F',' '{print NF}'` 计算，不要再用 `wc -l`
- H20 单卡明显 OOM 的模型，可以直接把默认 profile 设成双卡

## 多模态与 trust-remote-code

只有在模型真实需要时才添加这些参数：

- `--media-io-kwargs`
- `--mm-processor`
- `--mm-processor-cache-type`
- `--mm-encoder-tp-mode`
- `--trust-remote-code`

不要把别的脚本里的多模态参数整段复制过来。

## 日志驱动修正

不要只看脚本长相是否像模板，必须结合测试日志修正。

常见归因与动作：

| 日志现象 | 应对动作 |
|----------|----------|
| 找不到 `config.json` / 只落到 `._temp` 目录 | 先修本地模型路径或下载完整性，不要误判成参数问题 |
| `the provided PTX was compiled with an unsupported toolchain` | 记为当前环境 / 预编译内核兼容性问题；保留失败原因注释，不要靠清模型缓存解决 |
| 加载阶段直接 OOM | 优先调整默认 GPU profile、TP、KV cache 预算；如果当前机器明显不够，就降级为“参考入口” |
| 进入 generic multimodal backend 后缺处理器私有接口 | 记为当前 vLLM / transformers 兼容性缺口，不再把该脚本当稳定正例 |

如果日志已经证明脚本当前失败，就把脚本顶部注释改成**真实失败原因**，不要继续保留过期的“成功显存实测”。

## 什么时候回退到 `models/inference_*.py`

出现任一情况时，优先改走 reference inference：

- ModelScope `BackendSupport.vllm` 明确为 `null`
- 上游文档没有明确可靠的 vLLM 路径
- `trust_remote_code` 也无法让 vLLM 识别模型架构
- 当前 vLLM 实现与权重结构不兼容

这类 `inference_*.py` 默认只要求“可读、可参考”，除非用户明确要求，否则不承诺本地直接跑通。

## 最小校验清单

```bash
sh -n scripts/model-serving/vllm-serve-<model>.sh

# 仅当本地模型和 GPU 资源具备时再启动
sh scripts/model-serving/vllm-serve-<model>.sh 0
curl -sf http://localhost:8030/ping
```

除非用户明确要求，不要默认跑全量 `scripts/model-serving-test.sh`。

如果用户是在“修现有脚本”，优先做单模型验证：

```bash
sh scripts/model-serving-test.sh vllm-serve-<model>.sh
```

## DO / DON'T

**DO**

- 复用同家族现有脚本
- 把 Pixi 环境事实和上游原生依赖分开写
- 给多模态脚本补齐 `VisionModel`
- 模型卡不清晰时补查 ModelScope feedback / 用户交流经验
- 发现 vLLM 不可靠时，明确记录原因并回退到 `models/inference_*.py`

**DON'T**

- 不要根据品牌名猜 parser
- 不要复制别处的显存实测注释当成当前模型结论
- 不要把 `VLLM_SERVE_VLM_ARGS` 用到文本模型上
- 不要把 reference inference 当成必须可运行的生产入口
- 不要省略最后的用户确认

## See Also

- `docs/rules/coding-guidelines.md`
- `scripts/activation/vllm.sh`
- `scripts/model-serving/`
- `docs/kanban/tasks/SOTA 模型调研.md`
