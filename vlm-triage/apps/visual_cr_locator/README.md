# Visual CR Locator API

基于视觉 Embedding 的变更请求（CR）定位服务。通过分析仿真视频的图像相似度，自动定位引入问题的关键 CR。

## 功能概述

本服务提供以下核心功能：

- **同步定位**：实时处理单个 CR Locator，返回定位结果
- **异步定位**：支持批量任务排队处理，通过 ticket 查询结果
- **回调通知**：异步任务完成后可通过 webhook 回调通知
- **可视化输出**：支持返回关键帧图片和调试 Excel 文件

### 定位原理

1. **获取 CR Locator 数据**：从平台获取 base 版本、feature 版本及各候选 CR 的仿真任务
2. **事件窗口采样**：基于 DPE 事件（如接管、碰撞等）聚类，使用最大覆盖算法选取关键时间窗口
3. **图像采样**：从仿真视频中提取关键帧图像
4. **Embedding 计算**：调用 Embedding API 计算图像间的相似度
5. **CR 投票定位**：基于相似度变化趋势，通过投票算法定位引入问题的 CR

## API 端点

### POST `/locate`

同步定位接口，实时返回定位结果。

**请求参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `locator_id` | integer | ✅ | CR Locator ID，例如：`4391943` |
| `config` | object | ❌ | 定位配置参数（见下方配置说明） |

**响应：**

```json
{
  "ticket": "uuid-string",
  "status": "success",
  "message": "",
  "result": {
    "scenario_id": {
      "cr_index": 19,
      "commit": {
        "task_id": { "id": 3567557100000039 },
        "commit": "commit-hash"
      },
      "images_url": {},
      "excels_url": {}
    }
  }
}
```

**状态码：**
- `success` - 定位成功
- `error` - 处理出错（见 `message` 字段）

### POST `/locate/async`

异步定位接口，适用于批量处理场景。

**请求参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `locator_id` | integer | ✅ | CR Locator ID |
| `config` | object | ❌ | 定位配置参数 |
| `callback_url` | string | ❌ | 任务完成后的回调 URL |

**响应：**

返回任务 ticket（UUID 字符串），用于后续查询。

```
"550e8400-e29b-41d4-a716-446655440000"
```

### GET `/locate/async/{ticket}`

查询异步定位任务的结果。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `ticket` | string | 异步任务返回的 ticket |

**响应：**

与 `/locate` 接口相同的 `VisualCRLocatorResponse` 结构。

任务状态：
- `pending` - 等待执行
- `running` - 执行中
- `success` - 执行成功
- `error` - 执行失败

## 配置参数

`VisualCRLocatorConfig` 配置说明：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_windows` | int | 3 | 最大采样窗口数量 |
| `window_duration` | int | 3010 | 每个窗口采样时长（毫秒） |
| `window_offset` | int | 1500 | 窗口结束于事件后的时间偏移（毫秒） |
| `sample_interval` | int | 500 | 窗口内采样间隔（毫秒） |
| `sample_wh` | tuple[int, int] | (300, 400) | 图像采样宽高（像素） |
| `sample_xy` | tuple[int, int] | (904, 528) | 图像采样中心点（像素） |
| `sample_xy_e2e` | tuple[int, int] | (904, 528) | 端到端模式图像采样中心点 |
| `return_images` | bool | false | 是否返回关键帧图片 URL |
| `return_excels` | bool | false | 是否返回调试 Excel 文件 URL |

## 运行方式

### 开发环境

```bash
# 使用 fastapi dev 启动（支持热重载）
pixi shell
env OTEL_ENVIRONMENT_NAME=dev fastapi dev --host 0.0.0.0 --port "${TRIAGE_LOCATOR_API_PORT}" main.py
```

### 生产环境

```bash
# 直接运行（使用 prod 环境）
pixi run -e prod -- env OTEL_ENVIRONMENT_NAME=prod python main.py

# 或使用 uvicorn
pixi run -e prod -- python -c "
import uvicorn
uvicorn.run('main:app', host='0.0.0.0', port=int('\${TRIAGE_LOCATOR_API_PORT}'))
"
```

### 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `TRIAGE_LOCATOR_API_PORT` | 服务监听端口 | ✅ |
| `TRIAGE_EMBEDDING_API_URL` | Embedding API 服务地址 | ✅ |
| `TRIAGE_EMBEDDING_API_TIMEOUT` | Embedding API 超时时间（秒） | ❌（默认 90） |
| `TRIAGE_DATA_DIR` | 本地数据缓存目录 | ✅ |
| `TRIAGE_DATA_PREFIX_IN_S3` | S3 数据前缀 | ✅ |
| `TRIAGE_CACHE_DIR` | 本地缓存目录 | ✅ |
| `OTEL_SERVICE_NAME` | OpenTelemetry 服务名称 | ❌（默认 `visual-cr-locator-api`） |
| `OTEL_ENVIRONMENT_NAME` | 环境标识（dev/prod） | ❌ |

## 使用示例

### 同步定位

```python
import requests

url = "http://localhost:8000/locate"
params = {
    "locator_id": 4391943,
}
config = {
    "max_windows": 3,
    "return_images": True,
}

response = requests.post(url, params=params, json=config)
result = response.json()

print(f"状态: {result['status']}")
print(f"定位结果: {result['result']}")
```

### 异步定位

```python
import requests
import time

# 提交异步任务
url = "http://localhost:8000/locate/async"
params = {
    "locator_id": 4391943,
    "callback_url": "https://your-webhook.com/callback",  # 可选
}
config = {
    "return_images": True,
    "return_excels": True,
}

ticket = requests.post(url, params=params, json=config).text
print(f"任务 ticket: {ticket}")

# 轮询查询结果
while True:
    resp = requests.get(f"http://localhost:8000/locate/async/{ticket}")
    result = resp.json()

    if result['status'] in ('success', 'error'):
        print(f"任务完成: {result}")
        break

    print(f"任务状态: {result['status']}")
    time.sleep(5)
```

### 批量异步处理

```python
import requests

locator_ids = [4662583, 4662595, 4662619, 4666427]
tickets = []

# 提交所有任务
for locator_id in locator_ids:
    ticket = requests.post(
        "http://localhost:8000/locate/async",
        params={"locator_id": locator_id}
    ).json()
    tickets.append(ticket)

# 批量查询结果
for ticket in tickets:
    resp = requests.get(f"http://localhost:8000/locate/async/{ticket}")
    result = resp.json()
    print(f"{ticket}: {result['status']}")
```

## 响应数据结构

### VisualCRLocatorResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `ticket` | string | 任务唯一标识（UUID） |
| `status` | string | 任务状态：pending/running/success/error |
| `message` | string | 状态说明或错误信息 |
| `result` | object | 定位结果（按 scenario_id 组织） |

### LocatorScenarioResult

| 字段 | 类型 | 说明 |
|------|------|------|
| `cr_index` | int | 拐点在 CR 列表中的序号（从 1 开始） |
| `commit` | object | CR 提交信息（包含 task_id、commit hash） |
| `images_url` | object | 关键帧图片 URL 映射（当 `return_images=true`） |
| `excels_url` | object | 调试 Excel 文件 URL（当 `return_excels=true`） |

## 测试

```bash
# 运行单元测试
pixi run -- python apps/visual_cr_locator_api/test.py

# 或使用 pytest
pixi run -e test -- pytest apps/visual_cr_locator_api/test.py
```

## 依赖模块

- `lib/services/embedding_cr_locator_service.py` - 核心定位服务逻辑
- `lib/services/embedding_cr_locator_types.py` - 数据类型定义
- `lib/algorithms/cr_locate.py` - CR 定位算法（投票、异常检测）
- `lib/algorithms/max_coverage.py` - 最大覆盖采样算法
- `lib/platforms/tetools/cr_locator.py` - CR Locator 数据获取
- `lib/platforms/voyager_proxy.py` - Voyager 平台数据接口

## 性能指标

服务通过 OpenTelemetry 暴露以下指标：

- `visual-cr-locator-api.requests.locate_sync` - 同步请求计数
- `visual-cr-locator-api.requests.locate_async` - 异步请求计数
- `visual-cr-locator-api.counter.locate.success` - 成功计数
- `visual-cr-locator-api.counter.locate.error` - 错误计数
- `visual-cr-locator-api.counter.locate.not_found` - 查询未找到计数

## 注意事项

1. **并发控制**：服务内部使用信号量控制并发（任务并发 16，Embedding 请求并发 16，FFmpeg 处理并发 min(64, CPU 数)）
2. **任务限制**：已完成任务队列限制为 10000 个，超出后会自动清理最早的任务
3. **资源清理**：任务处理完成后会自动清理本地临时文件
4. **超时处理**：Embedding API 调用默认 90 秒超时，可通过环境变量调整
