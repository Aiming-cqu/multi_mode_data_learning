#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# pixi env: vllm-latest (vllm 0.19.x + transformers 5.5.x)
# upstream native inference reference (non-pixi):
#   conda create -n bagel python=3.10 -y
#   conda activate bagel
#   pip install -r requirements.txt
#     transformers==4.49.0
#   pip install flash_attn==2.5.8 --no-build-isolation

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

# Model loading took 14.97 GiB memory and 119.010980 seconds
# Encoder cache will be initialized with a budget of 16384 tokens, and profiled with 3 image items of the maximum feature size.
# GPU KV cache size: 74,896 tokens
# Maximum concurrency for 32,768 tokens per request: 2.29x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 32768 --kv-cache-memory-bytes 4G"
ARGS="${ARGS} --trust-remote-code"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/ByteDance-Seed/BAGEL-7B-MoT" \
	--served-model-name BAGEL-7B-MoT BAGEL-7B BAGEL VisionModel ${GPU} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
