#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e vllm-latest --as-is -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e vllm-latest --as-is -- sh
# pixi env: vllm-latest (vllm 0.19.x + transformers 5.6.x)
# upstream native inference reference (non-pixi):
# python=3.10
# torch>=2.1.0
# transformers=4.48.2
# MAX_JOBS=4 pip install vllm==0.9.1 blobfile flash-attn --no-build-isolation
# Kimi-VL custom architecture depends on --trust-remote-code
# current vllm env lacks transformers.activations.PytorchGELUTanh, which Kimi-VL imports;
# use vllm-latest instead of patching parser logic.

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

# Model loading took 30.7 GiB memory and 214.748260 seconds
# Encoder cache will be initialized with a budget of 16384 tokens, and profiled with 11 image items of the maximum feature size.
# GPU KV cache size: 276,160 tokens
# Maximum concurrency for 131,072 tokens per request: 2.11x

# Kimi-VL-A3B-Thinking-2506 keeps the 128K context window and can decode up to 32K tokens.
# Reasoning spans are emitted as '◁think▷ ... ◁/think▷'; vLLM does not expose a dedicated kimi_vl parser, so downstream should parse the tags if needed.

ARGS="${VLLM_SERVE_VLM_ARGS}"
ARGS="${ARGS} --max-model-len 131072 --kv-cache-memory-bytes 8G"
ARGS="${ARGS} --trust-remote-code"

echo ${ARGS} | CUDA_VISIBLE_DEVICES=${GPU} xargs vllm serve "${MODELSCOPE_CACHE}/models/moonshotai/Kimi-VL-A3B-Thinking-2506" \
	--served-model-name Kimi-VL-A3B-Thinking-2506 Kimi-VL-A3B-Thinking Kimi-VL-A3B Kimi-VL Kimi ReasonModel VisionModel ${GPU} "$@" \
	--dtype bfloat16 \
	--port ${PORT} # multi # numeric
