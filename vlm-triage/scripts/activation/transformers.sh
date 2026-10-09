#!/bin/sh

test -z "${HF_HOME}" && echo '❗️ HF_HOME required to be set' && exit 1
test -z "${MODELSCOPE_CACHE}" && echo '❗️ MODELSCOPE_CACHE required to be set' && exit 1

# export CUDA_DEVICE_MAX_CONNECTIONS=1
export CUDA_DEVICE_ORDER='PCI_BUS_ID'  # 确保显卡 ID 顺序与物理插槽一致
export HF_ENDPOINT='https://hf-mirror.com'
export HF_HUB_DISABLE_TELEMETRY=1  # 如果你想关掉那个烦人的 Telemetry 遥测上传
export HF_HUB_ENABLE_HF_TRANSFER=1
export MKL_NUM_THREADS=4
export MODELSCOPE_DOWNLOAD_PARALLELS=3
# export NCCL_DEBUG='ERROR'  # 调试多卡通讯时的好帮手
# export NCCL_IB_DISABLE=1  # 如果没有 InfiniBand 网络，禁用它以防报错
# export NCCL_P2P_DISABLE=1  # 某些机器更稳
export OMP_NUM_THREADS=4
export PYTORCH_ALLOC_CONF='expandable_segments:True'  # 显存碎片管理。如果遇到 OOM，可以尝试这个配置来更激进地回收显存
export TOKENIZERS_PARALLELISM=0
export TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=1  # 启用 TensorFloat-32 (TF32) 运算，在保持精度的同时大幅提升算力（适用于 Ampere 架构及以后）
# export TORCHDYNAMO_ALLOW_NON_FAKE_INPUTS=1
# export TORCHDYNAMO_VERBOSE=1
# export TORCHINDUCTOR_FREEZING=1
export TRANSFORMERS_VERBOSITY='error'  # 屏蔽 Transformers 冗长的警告信息，只看 ERROR 或 WARNING
