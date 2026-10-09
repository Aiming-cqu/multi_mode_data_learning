#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# pip install nvidia-cudnn-cu12==9.16.0.29
# pip install vllm>=0.12.0
# pip install transformers>=5.0.0rc0

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

# Model loading took 52.15 GiB memory and 354.297031 seconds
# Encoder cache will be initialized with a budget of 30000 tokens, and profiled with 1 video items of the maximum feature size.
# GPU KV cache size: 136,768 tokens
# Maximum concurrency for 128,000 tokens per request: 1.07x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 128000 --kv-cache-memory-bytes 24G"
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

echo ${ARGS} | CUDA_VISIBLE_DEVICES="${GPU}" xargs vllm serve "${MODELSCOPE_CACHE}/models/ZhipuAI/GLM-4___6V-FP8" \
	--served-model-name GLM-4.6V-FP8 GLM-4.6V GLM AgentModel CoderModel CompletionModel ReasonModel ThinkSwitch VisionModel ${GPU_NAMES} "$@" \
	--port ${PORT} # multi # numeric
