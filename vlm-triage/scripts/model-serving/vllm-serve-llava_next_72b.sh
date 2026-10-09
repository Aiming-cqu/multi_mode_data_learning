#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm -- sh
# transformers>=4.42.0,<4.58
# mistral_common<1.9
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

# Model loading took 67.6808 GiB memory and 357.444035 seconds
# Available KV cache memory: 22.88 GiB
# GPU KV cache size: 18,736 tokens
# Maximum concurrency for 16,384 tokens per request: 1.14x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 16384 --kv-cache-memory-bytes 23G"

if [ ${GPU_COUNT} -gt 1 ]
then
	ARGS="${ARGS} --tensor-parallel-size ${GPU_COUNT}"
fi

echo ${ARGS} | CUDA_VISIBLE_DEVICES="${GPU}" xargs vllm serve "${MODELSCOPE_CACHE}/models/AI-ModelScope/llava-next-72b-hf" \
	--served-model-name llava-next-72b-hf llava-next-72b llava-next VisionModel ${GPU_NAMES} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
