#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm -- sh
# pixi env: vllm (transformers 4.57.x + vllm >=0.11)
# upstream native inference reference (non-pixi):
# python=3.10
# pip install --upgrade keye-vl-utils==1.5.2
# pip install keye-vl-utils==1.5.2 "vllm>=0.9.2"
# Keye-VL custom architecture depends on --trust-remote-code

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

# Model loading took 16.3081 GiB and 104.265188 seconds
# Encoder cache will be initialized with a budget of 20449 tokens, and profiled with 1 image items of the maximum feature size.
# GPU KV cache size: 262,144 tokens
# Maximum concurrency for 131,072 tokens per request: 2.00x

# Keye-VL-1.5-8B extends context length to 128K.
# Thinking mode is selected in prompt text via '/think'; non-thinking uses '/no_think'.
# The official vLLM examples use OpenAI chat completions directly, without a custom parser.

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 131072 --kv-cache-memory-bytes 36G"
ARGS="${ARGS} --trust-remote-code"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/Kwai-Keye/Keye-VL-1___5-8B" \
	--served-model-name Keye-VL-1.5-8B Keye-VL-1.5 Keye-VL Keye VisionModel ${GPU} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
