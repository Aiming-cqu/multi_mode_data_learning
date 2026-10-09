#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# pip install nvidia-cudnn-cu12==9.16.0.29
# pip install vllm>=0.12.0
# pip install transformers>=5.0.0rc0

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

# Model loading took 19.24 GiB memory and 127.384803 seconds
# Encoder cache will be initialized with a budget of 58800 tokens, and profiled with 1 video items of the maximum feature size.
# GPU KV cache size: 314,560 tokens
# Maximum concurrency for 128,000 tokens per request: 2.46x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 128000 --kv-cache-memory-bytes 12G"
ARGS="${ARGS} --media-io-kwargs '{\"video\":{\"num_frames\":-1}}'"
ARGS="${ARGS} --mm-processor-cache-type shm"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser glm45"
ARGS="${ARGS} --reasoning-parser glm45"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/ZhipuAI/GLM-4___6V-Flash" \
	--served-model-name GLM-4.6V-Flash GLM-4.6V GLM AgentModel CompletionModel ReasonModel ThinkSwitch VisionModel ${GPU} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
