# CR 定位服务使用指南

CR 定位服务由一个后端 API 和一个 Streamlit 前端组成，用于对比自动驾驶仿真版本间的行为差异、定位引入变化的 CR，并支持人工标注。

| 服务 | 默认地址 |
|------|----------|
| API | `http://10.152.24.170:8061` |
| 前端 | `http://10.152.24.170:8085` |

---

## 1. CR 定位 API（`visual_cr_locator_api`）

### 1.1 启动

```bash
# 生产模式
apps/visual_cr_locator_api/main.py

# 开发模式
pixi shell
fastapi dev --host 0.0.0.0 --port "${TRIAGE_LOCATOR_API_PORT}" apps/visual_cr_locator_api/main.py
```

API 文档：`http://<host>:8061/docs`（Swagger UI）

### 1.2 接口说明

#### POST `/locate` — 同步定位

输入 Locator ID，同步等待返回定位结果（适合单次调用或调试）。

```bash
curl -X POST "http://10.152.24.170:8061/locate?locator_id=4391943"
```

可选 `config` 参数（JSON body，见 [1.4 采样配置](#14-采样配置)）。

响应 `LocatorResponse`：
```json
{
  "ticket": "9b041765f3d6",
  "status": "success",
  "message": "",
  "result": {
    "<scenario_id>": {
      "cr_index": 11,
      "commit": {
        "binary": 123456,
        "commit": { "commit": "3c3602fe..." },
        "task_id": {
          "id": 3702162700000004,
          "animation": "https://...",
          "vlm_animation": null
        }
      },
      "images": [
        {
          "cr_index": 11,
          "cr_desc": "3702162700000004 / 3c3602fe...",
          "window_index": "01",
          "window_desc": "W01 @ 5601ms",
          "sample_index": "05",
          "sample_desc": "S05 @ +490ms",
          "image_url": "https://..."
        }
      ],
      "excels": null
    }
  }
}
```

`status` 取值：`pending` / `running` / `success` / `error`
`images` 仅在请求时设置 `return_images=true` 时返回；`excels` 仅在 `return_excels=true` 时返回。

#### POST `/locate/async` — 异步定位

提交任务后立即返回 ticket，适合批量处理。

```bash
# 提交
curl -X POST "http://10.152.24.170:8061/locate/async?locator_id=4391943"
# → "9b041765f3d6"

# 查询结果
curl "http://10.152.24.170:8061/locate/async/9b041765f3d6"
```

支持 `callback_url` 参数，任务完成后自动回调。

#### POST `/annotation` — 获取标注元信息

返回场景图像和元信息，供标注前端使用。

```bash
curl -X POST "http://10.152.24.170:8061/annotation?locator_id=4391943" \
  -H "Content-Type: application/json" \
  -d '{"return_images": true}'
```

响应 `AnnotationInfo`：包含 `base_task_id`、`feat_task_id`、`diff_type`、各场景图像列表。

### 1.3 状态码说明

| `status` | 含义 |
|----------|------|
| `success` | 定位成功，`result` 有完整结果 |
| `error` | 定位失败，`message` 有错误描述，`result` 可能有部分结果 |
| `pending` | 异步任务进行中（仅异步接口） |

### 1.4 采样配置（`LocatorConfig`）

| 参数 | 默认 | 说明 |
|------|------|------|
| `max_windows` | 3 | 最大采样时间窗口数 |
| `window_duration` | 3010 | 每窗口采样时长（ms） |
| `window_offset` | 1500 | 窗口结束于事件后的时间偏移（ms） |
| `sample_interval` | 500 | 窗口内采样间隔（ms） |
| `sample_wh` | (300, 400) | 采样图像宽高（px） |
| `sample_xy` | (904, 528) | 采样中心坐标（px） |
| `sample_xy_e2e` | (904, 528) | 端到端采样中心坐标（px） |
| `use_vlm_animation` | true | 是否使用 VLM 专用 layout 动画 |
| `return_images` | false | 是否在响应中返回图像 URL |
| `return_excels` | false | 是否生成 Excel 报告 |

**示例：复杂采样参数**

```bash
curl -X POST "http://10.152.24.170:8061/locate?locator_id=4391943" \
  -H "Content-Type: application/json" \
  -d '{
    "max_windows": 5,
    "window_duration": 3000,
    "window_offset": -1000,
    "sample_interval": 200,
    "sample_wh": [1280, 720],
    "sample_xy": [1920, 1080],
    "return_images": true,
    "return_excels": true
  }'
```

---

## 2. 服务核心架构（`visual_cr_locator_service`）

核心服务位于 `lib/services/visual_cr_locator_service.py`，包含三个主要类。

### 2.1 类结构

| 类 | 职责 |
|---|---|
| `LocatorService` | 对外服务入口，提供 `locate` 和 `get_annotation_info` 异步接口 |
| `LocatorTask` | 单次定位任务的完整生命周期管理 |
| `CRProcessTask` | 单个 CR 对应的图片采样子任务 |

### 2.2 数据流水线

`LocatorService.locate` 的完整流水线：

```
get_tasks              → 从 CR Locator 平台拉取任务和 CR 列表
  ↓
cluster_event_windows  → 根据 DPE 事件时间戳聚类采样窗口 (max_coverage 算法)
  ↓
get_sample_images      → FFmpeg 裁剪动画帧到本地临时目录
  ↓
compute_visual_metrics → 并发调用 embedding API + CV API 计算相似度
  ↓
get_result             → 投票定位拐点 + 可选生成 Excel/图片
```

`get_annotation_info` 只执行前 3 步（不计算视觉指标），直接返回图片和 Excel 用于人工标注。

### 2.3 存储策略

服务使用三种存储路径，依赖 `s3_utils`、`excel_utils`、`cooper` 三个模块：

| 数据 | 存储方式 | 工具 | URL 获取 |
|------|----------|------|----------|
| 采样图片 | `put_and_sign` 上传到 S3 | `s3_utils.put_and_sign` | 上传时签名返回 |
| Excel 报告 | 写入 `DATA_DIR` (S3 挂载盘) | `excel_utils.write_df` + `embed_images` | `s3_utils.sign` 直接签名 |
| Excel 副本 | 上传到 Cooper 测试目录 | `cooper.CooperClient.upload_file` | Cooper 平台查阅 |
| 临时帧图片 | `CACHE_DIR` 本地目录 | FFmpeg 输出 | `CRProcessTask.close()` 时清理 |

**路径结构：**

```
S3 对象名:
  {DEFAULT_DATA_PREFIX}/{session_hash}/locator_id=...-scenario_id=...-cr_index=...jpg   # 图片
  {DEFAULT_DATA_PREFIX}/{session_hash}/locator_id=...-scenario_id=...xlsx               # Excel

DATA_DIR (S3 挂载盘):
  {session_hash}/locator_id=...-scenario_id=...xlsx   # Excel 本地路径
```

### 2.4 并发控制

通过 class-level `asyncio.Semaphore` 限制各下游服务的并发度：

| 信号量 | 默认值 | 控制对象 |
|--------|--------|----------|
| `LocatorService.semaphore` | CONCURRENCY | 同时执行的定位任务数 |
| `LocatorTask.task_semaphore` | CONCURRENCY | CR Locator 平台请求 |
| `LocatorTask.embedding_semaphore` | 6 | Embedding API 调用 |
| `LocatorTask.cv_semaphore` | 16 | CV API 调用 |
| `LocatorTask.cooper_semaphore` | min(4, CONCURRENCY) | Cooper 文件上传 |
| `LocatorTask.s3_semaphore` | min(16, CONCURRENCY×4) | S3 上传/签名 |

### 2.5 异常处理

- `LocatorFail`: 定位完成但存在告警（歧义投票、支持度不足等），`result` 字段仍包含可用结果。API 层可选择降级使用。
- `CRLocateError` / `InsufficientSupportError` / `AmbiguousSupportError`: 算法层异常，由 `get_result` 捕获并转为告警消息。
- 所有网络调用使用 `tenacity.retry` 自动重试（默认 3 次）。

---

## 3. CR 定位前端（`visual_cr_locator_fe`）

### 3.1 启动

```bash
pixi run serve-fe
# 或
streamlit run apps/visual_cr_locator_fe/main.py
```

前端地址：`http://10.152.24.170:8085`

### 3.2 定位页（Locator）

用于查看 CR 定位结果，对比各 CR 版本的仿真截图。

**使用步骤：**

1. 在顶部输入框输入一个或多个 **Locator ID**（空格/换行分隔）
2. 在左侧 sidebar 配置采样参数（与 API 的 `LocatorConfig` 对应）
3. 点击「运行分析」触发定位请求
4. 主区域按 Locator ID 分 tab，每个 tab 展示：
   - 元信息（diff_type、metrics、commit 信息、Diff 链接）
   - 各场景定位结果（拐点 CR + 置信度）
   - 各 CR 的仿真截图网格

参数通过 URL query params 持久化，刷新页面不丢失。

**Report 反馈：** 左侧 sidebar 提供反馈入口，自动关联当前选中的 Locator ID。

### 3.3 标注页（Annotation）

用于对 CR 定位结果进行人工标注，详细使用说明见：
👉 [CR 定位标注手册](cr-locator-annotation-guide.md)

**快速入门：**

1. 切换到「🏷️ CR 标注」任务
2. 输入 Locator ID（支持批量）
3. 在 sidebar 配置 `return_excels` 等选项
4. 主区域按场景展示截图网格，每个 cell 下方有标注下拉框
5. 标注完成后点击「💾 保存标注」

---

## 4. 环境变量

| 变量 | 说明 |
|------|------|
| `TRIAGE_LOCATOR_API_PORT` | API 服务端口（默认 8061） |
| `TRIAGE_LOCATOR_API_URL` | FE 调用 API 的地址 |
| `TRIAGE_DATA_DIR` | 数据存储根目录（S3 挂载盘，Excel 写入路径） |
| `TRIAGE_CACHE_DIR` | 临时文件缓存目录（FFmpeg 输出帧等） |
| `TRIAGE_EMBEDDING_API_URL` | Embedding API 服务地址 |
| `TRIAGE_EMBEDDING_API_TIMEOUT` | Embedding API 超时（默认 90s） |
| `TRIAGE_CV_API_URL` | CV API 服务地址 |
| `TRIAGE_CV_API_TIMEOUT` | CV API 超时（默认 90s） |
| `TRIAGE_LOCATOR_API_CONCURRENCY` | 定位任务并发数（默认 4） |
| `OTEL_SERVICE_NAME` | OpenTelemetry 服务名 |

---

## 5. 相关文档

- [标注手册](cr-locator-annotation-guide.md) — 人工标注操作规范
- [大模型 CR 定位](../kanban/features/大模型%20CR%20定位.md) — 算法原理与评估指标
- [CR 定位可视化前端](../kanban/features/CR%20定位可视化前端.md) — 前端需求与迭代历史
