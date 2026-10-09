#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm -- sh
# vllm>=0.11.0
# FlashInfer is not available. Falling back to the PyTorch-native implementation of top-p & top-k sampling. For the best performance, please install FlashInfer.
# Failed to import DeepGemm kernels.
# CutlassBlockScaledGroupedGemm not supported on the current platform.

set -eu

test -z "${MODELSCOPE_CACHE}" && echo '❗️ MODELSCOPE_CACHE required to be set' && exit 1
test -z "${VLLM_SERVE_VLM_ARGS}" && echo '❗️ VLLM_SERVE_VLM_ARGS required to be set' && exit 1

GPU=${1:-0} # numeric
PORT=803${GPU%%,*}

# image tokens reference
# 28 * 28 *   1200 =    940800
# 1352    *    810 =   1095120
# 28 * 28 *   2304 =   1806336
# 1920    *   1080 =   2073600
# 28 * 28 *   4096 =   3211264
# 28 * 28 *  16384 =  12845056
# 28 * 28 *  32768 =  25690112
# 28 * 28 * 131072 = 102760448

# Model loading took 30.4862 GiB and 237.113267 seconds
# Encoder cache will be initialized with a budget of 153600 tokens, and profiled with 1 video items of the maximum feature size.
# GPU KV cache size: 567,968 tokens
# Maximum concurrency for 262,144 tokens per request: 2.17x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 262144 --kv-cache-memory-bytes 52G"
# ARGS="${ARGS} --rope-scaling '{\"rope_type\":\"yarn\",\"factor\":3.0,\"original_max_position_embeddings\":262144,\"mrope_section\":[24,20,20],\"mrope_interleaved\":true}'"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser hermes"
ARGS="${ARGS} --reasoning-parser qwen3"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/Qwen/Qwen3-VL-30B-A3B-Thinking-FP8" \
	--served-model-name Qwen3-VL-30B-A3B-Thinking-FP8 Qwen3-VL-30B-A3B-Thinking Qwen3-VL-30B-A3B Qwen3-VL AgentModel CompletionModel ReasonModel ThinkSwitch VisionModel ${GPU} "$@" \
	--port ${PORT} # multi # numeric
