#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm -- sh
# transformers>=4.51.0
# vllm>=0.8.5
# FlashInfer is not available. Falling back to the PyTorch-native implementation of top-p & top-k sampling. For the best performance, please install FlashInfer.
# Failed to import DeepGemm kernels.
# CutlassBlockScaledGroupedGemm not supported on the current platform.

set -eu

test -z "${MODELSCOPE_CACHE}" && echo '❗️ MODELSCOPE_CACHE required to be set' && exit 1
test -z "${VLLM_SERVE_LLM_ARGS}" && echo '❗️ VLLM_SERVE_LLM_ARGS required to be set' && exit 1

GPU=${1:-0} # numeric
PORT=803${GPU%%,*}

# Model loading took 29.0445 GiB and 238.674234 seconds
# GPU KV cache size: 87,376 tokens
# Maximum concurrency for 40,960 tokens per request: 2.13x

ARGS="${VLLM_SERVE_LLM_ARGS}"
ARGS="${ARGS} --max-model-len 40960 --kv-cache-memory-bytes 8G"
# ARGS="${ARGS} --rope-scaling '{\"rope_type\":\"yarn\",\"factor\":4.0,\"original_max_position_embeddings\":32768}'"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser hermes"
ARGS="${ARGS} --reasoning-parser deepseek_r1"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/Qwen/Qwen3-30B-A3B-FP8" \
	--served-model-name Qwen3-30B-A3B-FP8 Qwen3-30B-A3B Qwen3 AgentModel CompletionModel ReasonModel ThinkSwitch ${GPU} "$@" \
	--port ${PORT} # multi # numeric
