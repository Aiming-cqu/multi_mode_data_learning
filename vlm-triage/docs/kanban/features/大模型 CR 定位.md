# 大模型 CR 定位

| 属性 | 值 |
| ---- | --- |
| ID | ai-cr-locator |
| 类型 | feature |
| 优先级 | high |
| 状态 | active |
| 创建日期 | 2026-03-01 |
| 更新日期 | 2026-05-17 |

## 概述

基于大模型（LLM / VLM / Embedding）补充 DPE metric 的不足，实现 Base vs Feature 行为差异的场景级判断（diff_type）和 CR 序列拐点精确定位。

## 背景

自动驾驶仿真回归测试中，DPE metric 存在漏召回、误召回、定位不准等问题，需要视觉模型能力补充。

## 范围

**在范围内：**

- 视觉特征相似度定位（CLIP / DINOv2 / SigLIP / SIFT）
- VLM 多帧理解探索（GPT-4o、Qwen-VL）
- 传统 CV 方法探索（光流、帧差分）
- 人工标注数据集构建
- Streamlit 可视化 + 标注前端

**不在范围内：**

- 不修改 DPE metric 计算逻辑
- 不替代仿真测试流程

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| 单拐点定位 Top-1 精度 | 85%+ (DPE 基线) | ≥ 90% | 标注数据集评测 |
| 多拐点召回率 | 无基线 | Recall@ALL ≥ 60% | 标注数据集评测 |
| 标注数据集规模 | 2 个数据集 | ≥ 5 个数据集 | 标注进度跟踪 |

---

## 方案原理

### 核心流程

```
locator_id
    │
    ▼
CRLocatorData（从 te-tools API 获取）
    │  包含：场景 ID、CR 序列、Base/Feature task_id
    ▼
采样策略（LocatorConfig）
    │  参数：窗口数、窗口时长/偏移、采样间隔、分辨率
    ▼
仿真图像采样（SampleImageInfo）
    │  每个 CR × 每个时间窗口 × 每个采样点
    ▼
特征提取 & 相似度计算
    │  视觉特征距离 / VLM 直接判断
    ▼
CR 定位算法（投票聚合）
    │  predicate矩阵 + 切割分数投票
    ▼
LocatorScenarioResult（拐点 CR + 置信度）
```

### diff_type 分类

每个场景被标记为 Base 与 Feature 行为变化方向：
- `P2F`（Pass→Fail）：Feature 使原本通过的场景变为不通过（回退）
- `F2P`（Fail→Pass）：Feature 修复了原本不通过的场景（改进）
- `P2P`：两个版本都通过（差异来源于驾驶质量，非通过/不通过）
- `F2F`：两个版本都不通过（行为变化但不影响通过率）

### 视觉特征定位算法

对于 CR 序列中每个 CR 的每个采样样本，计算 predicate：
```
predicate(cr, sample) = distance(cr, base) > distance(cr, feature)
```
- `TRUE`：该 CR 在该样本上更接近 Feature
- `FALSE`：该 CR 在该样本上更接近 Base

通过**切割分数**投票选出最优拐点 CR（详见 [标注指南](../../guides/cr-locator-annotation-guide.md)）。

---

## 评价手段

### 人工标注

- 工具：Streamlit 标注前端（[CR 定位可视化前端](CR%20定位可视化前端.md)）
- 标注入口：http://10.152.24.170:8085/?task=%F0%9F%8F%B7%EF%B8%8F+CR+%E6%A0%87%E6%B3%A8
- 标注指南：[cr-locator-annotation-guide.md](../../guides/cr-locator-annotation-guide.md)
- 标注内容：每个场景 × 每个 CR × 每个采样点标注 `diff_type`（变化类型）和 `rank`（拐点重要性，置空=关键）

### 指标

| 指标 | 说明 |
|------|------|
| **Top-1 精度** | 算法定位 CR 与人工标注拐点 CR 一致的比例 |
| **Top-3 精度** | 算法 Top-3 候选 CR 包含人工标注拐点的比例 |
| **场景级准确率** | diff_type 分类与人工判断一致的比例 |
| **标注召回率** | 算法命中被标注为关键（rank 缺省）的样本的比例 |
TODO：反转率才是业务核心指标，给出解释，并更新指标拆解，找出核心研发指标

### 标注数据集

| 数据集 | 场景数 | 说明 |
|--------|--------|------|
| 0313 collision | ~ | [Cooper 表格](https://cooper.didichuxing.com/docs2/sheet/2207120954333?sheetId=MODOC) |
| 0327 collision | ~ | [Cooper 表格](https://cooper.didichuxing.com/docs2/sheet/2207258701214?sheetId=Q0BBF) |

---

## 进展与计划

### 当前进展

- [x] CR 定位 API 服务（`apps/visual_cr_locator_api/`）
- [x] 可视化 + 标注前端（`apps/visual_cr_locator_fe/`）
- [x] 视觉特征相似度定位算法（`lib/algorithms/cr_locate.py`）
- [x] 多模型并发推理支持（`lib/services/`）
- [x] 人工标注数据集（0313、0327 collision）

### 待完成

- [ ] 基于标注数据集的算法量化评估
- [ ] VLM 直接判断方法探索（多帧图像理解）
- [ ] 定位结果置信度校准
- [ ] 更多数据集标注（扩大覆盖范围）

---

## 关联文档

| 文档 | 说明 |
|------|------|
| [CR 定位可视化前端](CR%20定位可视化前端.md) | 前端需求与迭代历史 |
| [标注指南](../../guides/cr-locator-annotation-guide.md) | 人工标注操作规范 |
| [CR 定位聚合算法优化](../tasks/CR%20定位聚合算法优化.md) | 算法优化任务 |
| [CR 定位传统 CV 方法探索](../tasks/CR%20定位传统%20CV%20方法探索.md) | CV 方法探索任务 |

---

## Iteration 20260414.2004

- 将前端需求从本文件抽取到「CR 定位可视化前端」feature 文件
- 标注前端 cell 标注增加 `rank` 字段，明确拐点重要性：置空=关键；`次要`=不影响核心指标的行为变化；`轻微`=噪声级别
- 重写本文件，明确方案原理、评价手段和数据集，便于团队快速理解
- 标注 `rank` 字段要保留显式 关键 值，更新实现代码

## Iteration 20260415.1057

- [text](../../guides/cr-locator-service.md) 在指南中增加复杂采样参数 locate 示例

## Iteration 20260424.1153

- 评测 badcase 分析 WIP
- 感知场景无抽帧效果验证 WIP
- 定位接口改造升级，输出多候选拐点，提升召回能力 WIP
- 分析采用时间偏差问题

- 将 @apps/visual_cr_locator/_page_annotation.py 升级
- 保存标注时保存当前标注图片的 s3 前缀
- 支持 加载标注成功则从已标注s3路径加载当前locator id所有图片，不再从API 重新获取图片
- 对已标注的数据，添加 s3 前缀，标注数据路径如 data/l-cr-locator-fe/202604/locator_id=4785425-scenario_id=12441516.f6383cad9cae.json ，图片路径如  data/visual-cr-locator-api/202604/2c08d64898f3/locator_id=4779925-scenario_id=18375519-cr_index=30-task_id=3719593500000000-commit=b92017b3f9e0c3f006e6cf710008a8d87d17622f-window_index=01-window_time=13086-sample_index=01-sample_time=11576.jpg

- 我把 字段换成 image_prefix 了
- 加载功能不生效，例如 data/visual-cr-locator-fe/202604/locator_id=4769805-scenario_id=5525738.f6383cad9cae.json 这个数据
传入 4769805 依旧是解图失败而非从 image_prefix 加载已有标注
- 测试链接 http://10.152.24.170:8085/?task=%F0%9F%8F%B7%EF%B8%8F+CR+%E6%A0%87%E6%B3%A8 你可以用playwright测

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

## Iteration 20260514.1610

更新接口&链路以更好支持多 CR 定位结果输出

## Iteration 20260517.1800

- 多候选拐点输出支持，提升召回能力
- 评测模块多对多准召评价逻辑调整（进行中）
- 定位接口改造升级完成，支持零/多拐点正常输出
