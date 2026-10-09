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

GPU="${1:-0,1}"
PORT=803${GPU%%,*}
GPU_COUNT=$(echo "${GPU}" | awk -F',' '{print NF}')
GPU_NAMES="$(echo "${GPU}" | tr ',' ' ')"

# Model loading took 61.0347 GiB memory and 101.557847 seconds
# Available KV cache memory: 23.78 GiB
# GPU KV cache size: 97,376 tokens
# Maximum concurrency for 32,768 tokens per request: 2.97x

ARGS="${VLLM_SERVE_LLM_ARGS}"
ARGS="${ARGS} --max-model-len 40960"
# ARGS="${ARGS} --rope-scaling '{\"rope_type\":\"yarn\",\"factor\":4.0,\"original_max_position_embeddings\":32768}'"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser hermes"
ARGS="${ARGS} --reasoning-parser deepseek_r1"

if [ ${GPU_COUNT} -gt 1 ]
then
	ARGS="${ARGS} --tensor-parallel-size ${GPU_COUNT}"
	ARGS="${ARGS} --enable-expert-parallel"
fi

echo ${ARGS} | CUDA_VISIBLE_DEVICES="${GPU}" xargs vllm serve "${MODELSCOPE_CACHE}/models/Qwen/Qwen3-235B-A22B-FP8" \
	--served-model-name Qwen3-235B-A22B-FP8 Qwen3-235B-A22B Qwen3 AgentModel CoderModel CompletionModel ReasonModel ThinkSwitch ${GPU_NAMES} "$@" \
	--port ${PORT} # multi # numeric
