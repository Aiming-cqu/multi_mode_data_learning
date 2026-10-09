#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm -- sh
# pixi env: vllm (vllm 0.11.x + transformers 4.57.x)
# ModelScope BackendSupport.vllm.vlm = 0.9.2
# Native context length: 128K
# Mllama is available in the current vllm / transformers stack.
# In this repo, keep the serve boundary to image inputs + text outputs.

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

# Current local test falls back to TransformersForMultimodalLM and then fails before
# memory profiling, because MllamaProcessor does not expose _get_num_multimodal_tokens
# in either of the current Pixi transformers stacks.

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 131072"
ARGS="${ARGS} --limit-mm-per-prompt '{\"image\":12,\"video\":0}'"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/LLM-Research/Llama-3___2-11B-Vision" \
	--served-model-name Llama-3.2-11B-Vision Llama-3.2-Vision Llama-3.2 Llama CompletionModel VisionModel ${GPU} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
