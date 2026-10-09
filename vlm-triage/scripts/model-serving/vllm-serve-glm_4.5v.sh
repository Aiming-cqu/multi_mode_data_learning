#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm -- sh
# pip install transformers>=4.57.1
# pip install vllm>=0.10.2
# FlashInfer is not available. Falling back to the PyTorch-native implementation of top-p & top-k sampling. For the best performance, please install FlashInfer.

set -eu

test -z "${MODELSCOPE_CACHE}" && echo '❗️ MODELSCOPE_CACHE required to be set' && exit 1
test -z "${VLLM_SERVE_VLM_ARGS}" && echo '❗️ VLLM_SERVE_VLM_ARGS required to be set' && exit 1

GPU="${1:-0,1}"
PORT=803${GPU%%,*}
GPU_COUNT=$(echo "${GPU}" | awk -F',' '{print NF}')
GPU_NAMES="$(echo "${GPU}" | tr ',' ' ')"

# image tokens reference
# 28 * 28 *   1200 =    940800
# 1352    *    810 =   1095120
# 28 * 28 *   2304 =   1806336
# 1920    *   1080 =   2073600
# 28 * 28 *   4096 =   3211264
# 28 * 28 *  16384 =  12845056
# 28 * 28 *  32768 =  25690112
# 28 * 28 * 131072 = 102760448

# Model loading took 52.1449 GiB and 367.206369 seconds
# Encoder cache will be initialized with a budget of 30970 tokens, and profiled with 1 video items of the maximum feature size.
# Available KV cache memory: 8.18 GiB
# GPU KV cache size: 93,248 tokens
# Maximum concurrency for 65,536 tokens per request: 1.42x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 65536 --kv-cache-memory-bytes 12G"
ARGS="${ARGS} --media-io-kwargs '{\"video\":{\"num_frames\":-1}}'"
ARGS="${ARGS} --mm-processor-cache-type shm"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser glm45"
ARGS="${ARGS} --reasoning-parser glm45"

if [ ${GPU_COUNT} -gt 1 ]
then
	ARGS="${ARGS} --tensor-parallel-size ${GPU_COUNT}"
	ARGS="${ARGS} --mm-encoder-tp-mode data"
	ARGS="${ARGS} --enable-expert-parallel"
fi

echo ${ARGS} | CUDA_VISIBLE_DEVICES="${GPU}" xargs vllm serve "${MODELSCOPE_CACHE}/models/ZhipuAI/GLM-4___5V-FP8" \
	--served-model-name GLM-4.5V-FP8 GLM-4.5V GLM AgentModel CoderModel CompletionModel ReasonModel ThinkSwitch VisionModel ${GPU_NAMES} "$@" \
	--port ${PORT} # multi # numeric
