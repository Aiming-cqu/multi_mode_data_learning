#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# python=3.10
# torch>=2.1.0
# transformers=4.57.0
# vllm>= 0.14.0

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

# Model loading took 14.09 GiB memory and 95.530742 seconds
# Encoder cache will be initialized with a budget of 16384 tokens, and profiled with 5 image items of the maximum feature size.
# GPU KV cache size: 87,376 tokens
# Maximum concurrency for 40,960 tokens per request: 2.13x

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 40960 --kv-cache-memory-bytes 12G"
ARGS="${ARGS} --enable-auto-tool-choice --tool-call-parser hermes"
ARGS="${ARGS} --reasoning-parser deepseek_r1"
ARGS="${ARGS} --trust-remote-code"
ARGS="${ARGS} --compilation-config '{\"pass_config\":{\"fuse_act_quant\": false}}'"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/stepfun-ai/Step3-VL-10B-FP8" \
	--served-model-name Step3-VL-10B Step3-VL Step3 AgentModel CompletionModel ReasonModel VisionModel ${GPU} "$@" \
	--port ${PORT} # multi # numeric
