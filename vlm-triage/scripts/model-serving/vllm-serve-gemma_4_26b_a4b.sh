#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# vllm 0.19.0 + transformers 5.5.4

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

# Model loading took 48.47 GiB memory and 308.775904 seconds
# Encoder cache will be initialized with a budget of 16384 tokens, and profiled with 6 video items of the maximum feature size.
# GPU KV cache size: 78,640 tokens
# Maximum concurrency for 262,144 tokens per request: 2.16x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 262144 --kv-cache-memory-bytes 18G"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser gemma4"
ARGS="${ARGS} --reasoning-parser gemma4"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/google/gemma-4-26B-A4B-it" \
	--served-model-name gemma-4-26B-A4B-it gemma-4-26B-A4B gemma-4 gemma AgentModel CoderModel CompletionModel ReasonModel ThinkSwitch VisionModel ${GPU} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
