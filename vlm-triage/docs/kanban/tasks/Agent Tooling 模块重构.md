# Agent Tooling 模块重构

| 属性 | 值 |
| ---- | --- |
| ID | agent-tooling-module-refactor |
| 类型 | task |
| 优先级 | high |
| 状态 | planning |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

重构 Agent Tooling 模块（`lib/tools/`），优化 Resource 设计，为重新接入 LLM agent 做准备。

## 背景

v0.2 优化了 Resource 设计（`lib/tools/resources/__init__.py`），但在重新接入 pydantic-ai LLM agent 前，tools/providers、toolset 装饰器等需要整体梳理和重构。

## 范围

**在范围内：**

- Resource/ResourceRepository 缓存层测试覆盖（见 [Resource 模块测试覆盖](Resource%20模块测试覆盖.md)）
- pydantic-ai toolset 模式统一（`wrap_transformer` + `FunctionToolset`）
- providers 模块重构（`lib/tools/data_providers/`）
- pydantic-ai Openai VideoUrl patch 合入

**不在范围内：**

- 不新增 tool 功能（纯重构）
- 不变更 Resource 对外接口语义

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| Resource 测试覆盖 | 0 个用例 | ≥ 19 个测试用例全部通过 | `pixi run testp -- tests/resources_test.py` |
| Toolset 模式一致性 | 混用多种模式 | 全部使用 `wrap_transformer` + `FunctionToolset` | 代码审查 |
| 无回归 | — | 现有 agent 功能不受影响 | 运行全量测试 |

## 关联

- [Resource 模块测试覆盖](Resource%20模块测试覆盖.md) — 本任务的核心测试依赖
- [缓存系统](../features/缓存系统.md) — Resource 缓存层的上游 feature

## 迭代记录

### Iteration 20260517.01

按新模板改写，补齐范围、成功指标。

**原始内容存档：**

- TODO: 合入 pydantic-ai openai VideoUrl patch
