#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# vllm>=0.19.0

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

# Model loading took 34.22 GiB memory and 237.684362 seconds
# Encoder cache will be initialized with a budget of 16384 tokens, and profiled with 1 image items of the maximum feature size.
# GPU KV cache size: 419,232 tokens
# Maximum concurrency for 262,144 tokens per request: 6.30x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 262144 --kv-cache-memory-bytes 10G"
# ARGS="${ARGS} --rope-scaling '{\"mrope_interleaved\":true,\"mrope_section\":[11,11,10],\"rope_type\":\"yarn\",\"rope_theta\":10000000,\"partial_rotary_factor\":0.25,\"factor\":4.0,\"original_max_position_embeddings\":262144}'"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser qwen3_coder"
ARGS="${ARGS} --reasoning-parser qwen3"
ARGS="${ARGS} --speculative-config '{\"method\":\"mtp\",\"num_speculative_tokens\":2}'"
ARGS="${ARGS} --compilation-config '{\"pass_config\":{\"fuse_act_quant\": false}}'"
ARGS="${ARGS} --gdn-prefill-backend triton"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/Qwen/Qwen3___6-35B-A3B-FP8" \
	--served-model-name Qwen3.6-35B-A3B-FP8 Qwen3.6-35B-A3B Qwen3.6 AgentModel CoderModel CompletionModel ReasonModel VisionModel ${GPU} "$@" \
	--port ${PORT} # multi # numeric
