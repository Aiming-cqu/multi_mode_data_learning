# CR 定位传统 CV 方法探索

| 属性 | 值 |
| ---- | --- |
| ID | cr-location-traditional-cv-methods-exploration |
| 类型 | task |
| 优先级 | medium |
| 状态 | planning |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

探索传统 CV 方法（光流、帧差分、SIFT 等）在 CR 定位中的应用，作为 VLM 方法的补充基线。

## 背景

承接 [大模型 CR 定位](../features/大模型%20CR%20定位.md)。`lib/algorithms/cv_similarity.py` 作为初版 CV 相似度算法，展示了传统 CV 方法的可用性。在 CR 定位聚合算法优化评测中已纳入 SIFT 作为基线模型，初步结果显示 SIFT 的 Recall 仅次于 DINOv2-base。

## 范围

**在范围内：**

- 评测现有 CV 方法的定位性能（已在 `experiments/cr-locator-eval/` 中实现 SIFT 基线）
- 探索光流、帧差分、特征匹配等额外 CV 方法
- 与 VLM embedding 方法做横向对比

**不在范围内：**

- 不替代 VLM 方法（CV 方法是补充基线）
- 不涉及深度学习模型训练

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| CV 方法覆盖率 | SIFT 已接入 | ≥ 3 种 CV 方法在评测框架中可运行 | 检查 `experiments/cr-locator-eval/` 支持的模型列表 |
| SIFT+新方法整体 Recall@1 | 38.7% (SIFT) | 提升 ≥ 5pp | 在 49+ 标注样本上评测 |

## 验证方案

### 评价方法

- 在 `experiments/cr-locator-eval/` 评测框架中注册新 CV 方法
- 与 DINOv2-base、SIFT 等基线做横向对比
- 按场景类型（single_cr / multi_cr）分报告

### 测试计划

- [ ] 光流方法接入评测框架
- [ ] 帧差分方法接入评测框架
- [ ] CV 方法组合/融合实验

## 关联

- [大模型 CR 定位](../features/大模型%20CR%20定位.md) — 上游 feature
- [CR 定位聚合算法优化](CR%20定位聚合算法优化.md) — 评测框架共享

## 迭代记录

### Iteration 20260517.01

按新模板改写，补齐范围、成功指标、验证方案。
