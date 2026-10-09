#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# pixi env: vllm-latest (vllm 0.19.x + transformers 5.6.x)
# upstream native inference reference (non-pixi):
# git clone -b qwen3_omni https://github.com/wangxiongts/vllm.git
# pip install -r requirements/build.txt
# pip install -r requirements/cuda.txt
# export VLLM_PRECOMPILED_WHEEL_LOCATION=https://wheels.vllm.ai/a5dd03c1ebc5e4f56f3c9d3dc0436e9c582c978f/vllm-0.9.2-cp38-abi3-manylinux1_x86_64.whl
# VLLM_USE_PRECOMPILED=1 pip install -e . -v --no-build-isolation
# pip install git+https://github.com/huggingface/transformers
# pip install accelerate qwen-omni-utils -U
# pip install -U flash-attn --no-build-isolation
# ModelScope BackendSupport.vllm is null for this AWQ mirror.
# In this repo, keep the serve boundary to image inputs + text outputs;
# do not treat it as a stable raw audio/video serve example.

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

# Current local test loads weights successfully, then fails in the Marlin /
# compressed-tensors path with 'CUDA error: the provided PTX was compiled with an
# unsupported toolchain' from the precompiled vllm-latest wheel.

export VLLM_USE_V1=0

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 32768"
ARGS="${ARGS} --limit-mm-per-prompt '{\"image\":12,\"video\":0,\"audio\":0}'"
ARGS="${ARGS} --trust-remote-code"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/cpatonn-mirror/Qwen3-Omni-30B-A3B-Thinking-AWQ-4bit" \
	--served-model-name Qwen3-Omni-30B-A3B-Thinking-AWQ-4bit Qwen3-Omni-30B-A3B-Thinking Qwen3-Omni-30B-A3B Qwen3-Omni ReasonModel VisionModel ${GPU} "$@" \
	--port ${PORT} # multi # numeric
