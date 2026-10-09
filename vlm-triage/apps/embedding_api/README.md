# Embedding API

基于预训练视觉模型的图像 Embedding 提取服务。

## 功能概述

本服务提供以下核心功能：

- **图像 Embedding 提取**：支持多种预训练视觉模型（CLIP、DINOv2、SigLIP、AIMv2 等）
- **图像相似度计算**：基于提取的 embedding 计算图像间相似度

## 支持的模型

默认支持的预训练模型列表：

| 模型 ID | 说明 |
|---------|------|
| `AI-ModelScope/clip-vit-large-patch14` | OpenAI CLIP ViT-L/14 |
| `apple/aimv2-huge-patch14-448` | Apple AIMv2 Huge |
| `facebook/dinov2-base` | Meta DINOv2 Base |
| `facebook/dinov2-large` | Meta DINOv2 Large |
| `google/siglip2-base-patch16-224` | Google SigLIP2 Base |

## API 端点

### POST `/embed`

提取上传图像的 embedding 向量。

**请求参数：**

- `image_files` (required): 图像文件列表（multipart/form-data）
- `model_ids` (optional): 使用的模型 ID 列表，默认为上述5个模型
- `fmt` (optional): 输出格式，可选值：
  - `arrow_tensor` - Apache Arrow Tensor 格式
  - `arrow_recordbatch` (默认) - Apache Arrow RecordBatch 格式
  - `safetensors` - SafeTensors 格式

**响应：**

- Content-Type: `application/vnd.apache.arrow.stream` 或 `application/octet-stream`
- 返回各模型提取的 embedding 数据

### POST `/compute_similarity`

计算图像序列的相似度矩阵。

**请求参数：**

- `image_files` (required): 图像文件列表（multipart/form-data）
- `model_ids` (optional): 使用的模型 ID 列表
- `metric_names` (optional): 相似度度量方法，默认 `["Cosine", "L2"]`
- `fmt` (optional): 输出格式，可选值：
  - `arrow_tensor` - Apache Arrow Tensor 格式
  - `arrow_recordbatch` (默认) - Apache Arrow RecordBatch 格式
  - `parquet` - Apache Parquet 格式
  - `safetensors` - SafeTensors 格式

**响应：**

- Content-Type: 根据 `fmt` 参数返回对应格式
- 返回图像间相似度矩阵（shape: `[n_images, n_models, n_metrics, 2]`）

## 运行方式

### 开发环境

```bash
# 使用 fastapi dev 启动（热重载）
pixi shell -e vllm
env OTEL_ENVIRONMENT_NAME=dev fastapi dev --host 0.0.0.0 --port "${TRIAGE_EMBEDDING_API_PORT}" main.py
```

### 生产环境

```bash
# 直接运行
pixi run -e vllm -- env OTEL_ENVIRONMENT_NAME=prod python main.py

# 或使用 uvicorn
pixi run -e vllm -- python -c "
import uvicorn
uvicorn.run('main:app', host='0.0.0.0', port=int('\${TRIAGE_EMBEDDING_API_PORT}'))
"
```

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TRIAGE_EMBEDDING_API_PORT` | 服务端口 | 必需 |
| `OTEL_SERVICE_NAME` | OpenTelemetry 服务名称 | `embedding-api` |
| `OTEL_ENVIRONMENT_NAME` | 环境标识（dev/prod） | - |
| `MODELSCOPE_CACHE` | ModelScope 模型缓存目录 | - |

## 使用示例

### 提取图像 Embedding

```python
import requests

url = "http://localhost:8000/embed"
files = [
    ("image_files", open("image1.jpg", "rb")),
    ("image_files", open("image2.jpg", "rb")),
]
params = {
    "model_ids": ["facebook/dinov2-large"],
    "fmt": "arrow_recordbatch"
}

response = requests.post(url, files=files, params=params)
print(response.status_code)  # 200
```

### 计算图像相似度

```python
import requests

url = "http://localhost:8000/compute_similarity"
files = [
    ("image_files", open("frame1.jpg", "rb")),
    ("image_files", open("frame2.jpg", "rb")),
    ("image_files", open("frame3.jpg", "rb")),
]
params = {
    "model_ids": ["AI-ModelScope/clip-vit-large-patch14"],
    "metric_names": ["Cosine"],
    "fmt": "arrow_recordbatch"
}

response = requests.post(url, files=files, params=params)
print(response.status_code)  # 200
```

## 测试

```bash
# 运行单元测试
pixi run -e vllm -- python test.py
```

## 依赖模块

- `lib/services/embedding_service.py` - Embedding 服务核心逻辑
- `lib/algorithms/embedding_extractor.py` - 图像特征提取器
- `lib/algorithms/embedding_metrics.py` - 相似度计算指标
