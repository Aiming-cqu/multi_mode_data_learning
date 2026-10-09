#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -e modelscope -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -e modelscope -- sh

set -u

test -z "${MODELSCOPE_CACHE}" && echo '❗️ MODELSCOPE_CACHE required to be set' && exit 1

NUM_WORKERS=3
DOWNLOAD_CMD="modelscope download --max-workers ${NUM_WORKERS} --model"

${DOWNLOAD_CMD} 01ai/Yi-34B-Chat-8bits
${DOWNLOAD_CMD} AI-ModelScope/clip-vit-large-patch14
# ${DOWNLOAD_CMD} AI-ModelScope/llava-next-72b-hf
${DOWNLOAD_CMD} AI-ModelScope/PE-Lang-G14-448
${DOWNLOAD_CMD} apple/aimv2-huge-patch14-448
${DOWNLOAD_CMD} BAAI/BGE-VL-MLLM-S1 # 更贴近 image + text 组合查询场景，适合 conditional query embedding 探索
${DOWNLOAD_CMD} ByteDance-Seed/BAGEL-7B-MoT
# ${DOWNLOAD_CMD} cpatonn-mirror/Qwen3-Next-80B-A3B-Thinking-AWQ-4bit
${DOWNLOAD_CMD} cpatonn-mirror/Qwen3-Omni-30B-A3B-Thinking-AWQ-4bit
${DOWNLOAD_CMD} facebook/dinov2-base
${DOWNLOAD_CMD} facebook/dinov2-large
${DOWNLOAD_CMD} google/gemma-4-26B-A4B-it
${DOWNLOAD_CMD} google/gemma-4-31B-it
${DOWNLOAD_CMD} google/gemma-4-E4B-it
# ${DOWNLOAD_CMD} google/medgemma-27b-it
${DOWNLOAD_CMD} google/siglip-base-patch16-224
${DOWNLOAD_CMD} google/siglip-so400m-patch14-384
${DOWNLOAD_CMD} google/siglip2-base-patch16-224
${DOWNLOAD_CMD} google/siglip2-so400m-patch16-512
${DOWNLOAD_CMD} Hyggge/Valley-Eagle-7B
${DOWNLOAD_CMD} iic/GVE-7B # 视频检索方向的统一 embedding 候选，当前优先级低于通用图文检索主线
${DOWNLOAD_CMD} jinaai/jina-embeddings-v4 # 多模态多语言统一 embedding，支持 dense 与 late interaction
${DOWNLOAD_CMD} Kwai-Keye/Keye-VL-1.5-8B
# ${DOWNLOAD_CMD} llava-hf/LLaVA-NeXT-Video-34B-hf
${DOWNLOAD_CMD} LLM-Research/Llama-3.2-11B-Vision
${DOWNLOAD_CMD} LLM-Research/Meta-Llama-3.1-8B-Instruct
${DOWNLOAD_CMD} mistralai/Mistral-Small-3.2-24B-Instruct-2506
${DOWNLOAD_CMD} moonshotai/Kimi-VL-A3B-Instruct
${DOWNLOAD_CMD} moonshotai/Kimi-VL-A3B-Thinking-2506
${DOWNLOAD_CMD} moonshotai/Moonlight-16B-A3B-Instruct
${DOWNLOAD_CMD} nv-community/Alpamayo-R1-10B  # structure data in
${DOWNLOAD_CMD} nv-community/Cosmos-Reason2-8B  # structure data out
${DOWNLOAD_CMD} nv-community/nemotron-colembed-vl-8b-v2 # 视觉文档检索强候选，但推理成本与许可证约束更强
${DOWNLOAD_CMD} OpenGVLab/InternVideo2-Stage2_1B-224p-f4
${DOWNLOAD_CMD} OpenGVLab/InternVL3_5-241B-A28B-Flash
${DOWNLOAD_CMD} OpenGVLab/InternVL3_5-38B-Flash
${DOWNLOAD_CMD} OpenGVLab/VideoMAEv2-Huge
# ${DOWNLOAD_CMD} PaddlePaddle/ERNIE-4.5-VL-28B-A3B-Paddle
${DOWNLOAD_CMD} PaddlePaddle/ERNIE-4.5-VL-28B-A3B-PT
${DOWNLOAD_CMD} Qwen/Qwen3-235B-A22B-Thinking-2507-FP8
${DOWNLOAD_CMD} Qwen/Qwen3-30B-A3B-FP8
${DOWNLOAD_CMD} Qwen/Qwen3-32B
${DOWNLOAD_CMD} Qwen/Qwen3-32B-AWQ
${DOWNLOAD_CMD} Qwen/Qwen3-32B-FP8
# ${DOWNLOAD_CMD} Qwen/Qwen3-8B-AWQ
${DOWNLOAD_CMD} Qwen/Qwen3-Embedding-8B
# ${DOWNLOAD_CMD} Qwen/Qwen3-Next-80B-A3B-Thinking-FP8
${DOWNLOAD_CMD} Qwen/Qwen3-Reranker-8B
${DOWNLOAD_CMD} Qwen/Qwen3-VL-30B-A3B-Instruct-FP8
${DOWNLOAD_CMD} Qwen/Qwen3-VL-30B-A3B-Thinking-FP8
${DOWNLOAD_CMD} Qwen/Qwen3-VL-8B-Instruct-FP8
${DOWNLOAD_CMD} Qwen/Qwen3-VL-8B-Thinking-FP8
${DOWNLOAD_CMD} Qwen/Qwen3-VL-Embedding-8B
${DOWNLOAD_CMD} Qwen/Qwen3-VL-Reranker-8B
${DOWNLOAD_CMD} Qwen/Qwen3.5-122B-A10B-FP8
${DOWNLOAD_CMD} Qwen/Qwen3.5-27B-FP8
${DOWNLOAD_CMD} Qwen/Qwen3.6-27B-FP8
${DOWNLOAD_CMD} Qwen/Qwen3.6-35B-A3B-FP8
${DOWNLOAD_CMD} Salesforce/blip2-opt-2.7b
${DOWNLOAD_CMD} stepfun-ai/step3-fp8
${DOWNLOAD_CMD} stepfun-ai/Step3-VL-10B-FP8
${DOWNLOAD_CMD} swift/llama3-llava-next-8b-hf
# ${DOWNLOAD_CMD} swift/LLaVA-NeXT-Video-7B-hf
# ${DOWNLOAD_CMD} tclf90/Step3-VL-10B-AWQ
${DOWNLOAD_CMD} ZhipuAI/GLM-4.5-Air-FP8
${DOWNLOAD_CMD} ZhipuAI/GLM-4.5V-FP8
${DOWNLOAD_CMD} ZhipuAI/GLM-4.6V-Flash
${DOWNLOAD_CMD} ZhipuAI/GLM-4.6V-FP8

tree -L 4 "${MODELSCOPE_CACHE}"/
