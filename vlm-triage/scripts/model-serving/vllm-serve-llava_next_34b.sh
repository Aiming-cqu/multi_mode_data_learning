#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm -- sh
# transformers>=4.42.0,<4.58
# mistral_common<1.9
# FlashInfer is not available. Falling back to the PyTorch-native implementation of top-p & top-k sampling. For the best performance, please install FlashInfer.

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

# Model loading took 64.7087 GiB and 106.928545 seconds
# Encoder cache will be initialized with a budget of 4096 tokens, and profiled with 1 video items of the maximum feature size.
# Available KV cache memory: 1.81 GiB
# GPU KV cache size: 7,904 tokens
# Maximum concurrency for 4,096 tokens per request: 1.93x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 4096 --kv-cache-memory-bytes 2G"
ARGS="${ARGS} --max-num-batched-tokens 12288"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/llava-hf/LLaVA-NeXT-Video-34B-hf" \
	--served-model-name llava-next-video-34b-hf llava-next-video-34b llava-next-video llava-next VisionModel ${GPU} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
