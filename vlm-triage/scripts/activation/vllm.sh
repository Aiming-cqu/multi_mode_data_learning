#!/bin/sh

test -z "${TRIAGE_CACHE_DIR}" && echo '❗️ TRIAGE_CACHE_DIR not set' && exit 1

# export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
# export VLLM_ATTENTION_BACKEND='FLASH_ATTN'
# export VLLM_ATTENTION_BACKEND='FLASHINFER'
export VLLM_DO_NOT_TRACK=1
export VLLM_ENABLE_V1_MULTIPROCESSING=0
export VLLM_ENGINE_ITERATION_TIMEOUT_S=60  # 针对高负载，允许请求在队列中等待更久而不报错
export VLLM_HOST_IP='0.0.0.0'
export VLLM_LOG_BATCHSIZE_INTERVAL=60
# export VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1
export VLLM_NO_USAGE_STATS=1
export VLLM_RPC_TIMEOUT=30000  # 增加推理流水线深度（针对 VLM）
# export VLLM_USE_AOT_COMPILE=0
# export VLLM_USE_DEEP_GEMM=1
export VLLM_USE_MODELSCOPE=1
export VLLM_USE_PRECOMPILED=1
export VLLM_USE_TRITON_AWQ=1
export VLLM_USE_V1=1
export VLLM_WORKER_MULTIPROC_METHOD='spawn'
export VLLM_ENABLE_CUDA_COMPATIBILITY=1

export VLLM_SERVE_ARGS="--uvicorn-log-level info --seed 3407 --gpu-memory-utilization 0.1"
export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --otlp-traces-endpoint \"${OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces\""
export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --enable-log-requests --enable-log-outputs"
export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --enable-chunked-prefill"
# export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --enable-prompt-tokens-details"
# export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --disable-frontend-multiprocessing"
export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --disable-custom-all-reduce"
# export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --disable-hybrid-kv-cache-manager"
export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --max-num-seqs 3 --max-num-batched-tokens 16384"  # NOTE: production default
# export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --max-num-seqs 1 --max-num-batched-tokens 16384"  # WORKAROUND: --max-num-seqs 1 for reproducibility
# export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --max-log-len 4096"
export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --kv-cache-dtype auto"
# export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --kv-offloading-size 4.0"  # GB
# export VLLM_SERVE_ARGS="${VLLM_SERVE_ARGS} --gdn-prefill-backend triton"

export VLLM_SERVE_LLM_ARGS="${VLLM_SERVE_ARGS}"

export VLLM_SERVE_VLM_ARGS="${VLLM_SERVE_ARGS}"
export VLLM_SERVE_VLM_ARGS="${VLLM_SERVE_VLM_ARGS} --limit-mm-per-prompt '{\"image\":12,\"video\":3}'"
export VLLM_SERVE_VLM_ARGS="${VLLM_SERVE_VLM_ARGS} --allowed-local-media-path \"${TRIAGE_CACHE_DIR}\""
export VLLM_SERVE_VLM_ARGS="${VLLM_SERVE_VLM_ARGS} --mm-processor-cache-gb 4"  # NOTE: avoid OOM
# export VLLM_SERVE_VLM_ARGS="${VLLM_SERVE_VLM_ARGS} --mm-processor-cache-gb 0"  # WORKAROUND: --mm-processor-cache-gb 0 to bypass mm cache-miss issue
# export VLLM_SERVE_VLM_ARGS="${VLLM_SERVE_VLM_ARGS} --skip-mm-profiling"

export MAX_JOBS=8
export NVCC_THREADS=2
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL='http/protobuf'
export UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN=1
export VERBOSE=1
