# CR 定位可视化前端

| 属性 | 值 |
| ---- | --- |
| ID | cr-locator-fe |
| 类型 | feature |
| 优先级 | high |
| 状态 | active |
| 创建日期 | 2026-04-14 |
| 更新日期 | 2026-05-17 |

## 概述

基于 Streamlit 实现 CR 定位结果可视化与人工标注前端，支持多 locator tab 对比、标注持久化、参数 URL 持久化。

## 背景

CR 定位算法需要人工标注作为真值，标注工具需要可视化算法输出并支持逐 cell 标注。

## 范围

**在范围内：**

- 定位展示（输入 locator_id，展示定位结果、commit 信息、帧图像）
- 多 locator tab 对比
- 标注前端（逐 cell 标注 diff_type / rank / scene_invalid）
- 标注结果持久化 JSONL（按 S3 data prefix）
- URL query param 参数持久化

**不在范围内：**

- 不修改后端 API
- 不实现非 Streamlit 的前端

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| 标注效率 | — | 单场景标注 ≤ 5 分钟 | 人工计时 |
| 稳定性 | — | 无 500 错误中断标注流程 | 实际使用 |
| 已有标注加载 | — | 自动加载已标注数据，无需重新获取图片 | 回归测试 |

## 需求与迭代

### Iteration 20260414.0815

根据最新类型定义 `lib/services/visual_cr_locator_types.py` 和 API `apps/visual_cr_locator_api/main.py`，重写定位展示前端 `apps/visual_cr_locator_fe/main.py` 和标注前端 `apps/visual_cr_locator_annotation_fe/main.py`：

- 不编辑除了 fe 以外的代码
- 严格按照 streamlit 开发规范
- 使用 data model
- 使用同步请求
- 使用入参缓存 + st_paramed 请求参数
- 工具支持多 locator id 请求，分 tab 展示
- 标注存储的 jsonl 按 s3 data prefix 存到 `data/app_name/partition/object_name.jsonl` 目录下，不带 session id 等随机数
- 展示规划的类型和函数列表

标注结果路径：`DATA_DIR/visual-cr-locator-fe/202507/{locator_id=}-{scenario_id=}-{sample_config_hash}.jsonl`

### Iteration 20260414.0919

annotation fe:
- Locator IDs 支持空格、制表符、换行符分隔
- API 请求失败：HTTPStatusError("Server error '500 Internal Server Error' ... 未指定 return images & return excels
- 增加一个可选的场景级标注：场景无效，选项：端到端无效、非链路拐点

locator fe:
- 参数未暴露 `use_vlm_animation`

### Iteration 20260414.1114

annotation fe 反馈：

- ~~标题放到导航栏~~ 标题不放到导航栏，和 locator fe 保持一致
- locator_id tab 可以固定在页面顶部吗？或者放到导航栏，方便页面滚动后也能切换，如果放到导航栏，url, diff type 这些元信息也放过去
- base 和 feature 不能标注
- 标注文件格式用 `"annotations": [{"window_index", "cr_index", "sample_index", "diff_type"}]` 这种形式，只存有标注的 cell
- 自动加载已有标注
- 在导航栏增加 st_report

locator fe 反馈：

- `use_vlm_animation` 不是输出选项，而是输入选项
- 与 annotation fe 相同的元信息展示
- 命名统一，去掉 Embedding 词汇
- 分行或者表格展示定位结果
- 移除 `st.divider()` 结构紧凑点

### Iteration 20260414.1210

locator fe 反馈：

- report 指定要反馈的 locator id
- st_report Submit 了为啥不会关闭对话框？帮我看看怎么修
- `result.commit.task_id.animation` 用列式表格或者多行，不要横向的

annotation fe 反馈：

- 还是展示 base feature task id 吧
- `locator_id`, `window_index` 都 sticky 叠在一起了，有办法解决吗

locator fe 反馈：

- 选择要 Report 的 Locator 切换后主页面刷新为「请在左侧配置参数并点击「运行分析」」，而 annotation fe 就不会

### Iteration 20260414.1352

- shared/cache 不用 API 的 datamodel 改用 dataclass 缓存（streamlit 支持嵌套 dataclass 缓存）
- 任务没做成 url path 或 param
- 已有标注加载失败/不兼容应当放弃加载
- 标注把尽量多的 `AnnotationInfo` `SampleImageInfo` 都存进去
- 不应该等待「正在获取标注网格…」，tab 每加载一页就可以显示并加载下一页

### Iteration 20260414.1434

- 根据 `st.tabs` 的 `.open` 属性（Streamlit 1.55.0+）自动跟踪当前 tab，从而移除人工填写
- 不做懒加载，所有 tab 内容在页面加载时全量渲染（eager loading），切换 tab 无等待感
- 输入表单的默认值、类型、desc 等从 Pydantic model 里自动抽取（`st_config_fields`）

### Iteration 20260414.1611

- 给所有 `@retry` 加上 `reraise=True`，重试耗尽后直接 re-raise 原始异常而非包成 `RetryError`

### Iteration 20260414.1700

- fe 不缓存 result/images 为 None 的 API 响应（`_cached_locate`, `_cached_annotation` 遇到空结果抛异常）

### Iteration 20260414.2004

- 将前端需求从「大模型 CR 定位」feature 中抽取到本文件
- 标注前端 cell 标注增加 `rank` / `importance` 字段，标识召回必要性/判定清晰度（相对应 ignore 难以判定的拐点）

## Iteration 20260414.2131

- 针对 streamlit 将你的开发经验固化到 docs/skills/streamlit-app-development/SKILL.md

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

### Iteration 20260415.1232

重构 `_page_annotation.py` 标注键类型：移除字符串拼接键，改用天然的 `tuple[int, str, str]` 键，确保保存时按数值顺序排列。

变更：
- 新增类型别名 `AnnKey = tuple[int, str, str]`
- `load_annotations` 返回类型改为 `tuple[dict[AnnKey, str], dict[AnnKey, str], str, str]`，四元组为 `(annotations, ranks, comment, scene_invalid)`，rank 和 meta 字段不再混入同一个 dict
- `save_annotations` 拆分参数：`annotations: dict[AnnKey, str]`、`ranks: dict[AnnKey, str]`、`comment: str`、`scene_invalid: str`；`cell_lookup` 键从 `tuple[str, str, str]` 改为 `AnnKey`，消除 `str(c.cr_index)` 转换
- `render_annotation_scenario` 中 `cell_key` 改为 `(cr_index, win_idx, samp_idx)` tuple；`ann_state`/`rank_state` 独立为两个 `dict[AnnKey, str]`；comment/scene_invalid 作为独立变量传递
- `sorted(annotations.items())` 基于 tuple 天然比较，cr_index 按整数数值排序（修复原字符串排序 "10" < "2" 的问题）

### Iteration 20260415.1246

为标注行（CR）增加高亮底色：当该行任意样本已有标注时（既检查已保存的 `existing`，也检查当前 session 的 `st.session_state`），以绿色背景（`#d4edda`）高亮行标题，否则保持原始 markdown 样式。`NON_ANNOTATABLE` 行（cr_index -1/-2）不参与高亮逻辑。

## Iteration 20260415.1234

增加一个功能，当一行（CR）有样本有标注时，为这行上高亮底色，作视觉提示

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。
