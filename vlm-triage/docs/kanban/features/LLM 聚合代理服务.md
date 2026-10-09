# LLM 聚合代理服务

| 属性 | 值 |
| ---- | --- |
| ID | llm-aggregation-proxy |
| 类型 | feature |
| 优先级 | high |
| 状态 | done |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

基于 LiteLLM 提供一站式内外模型接入代理，支持自部署模型负载均衡、按功能聚合模型，便于测试多种模型能力。

## 背景

项目依赖多种 LLM（Claude、Gemini、本地部署模型），各自接入方式不同。需要一个统一代理层收敛差异。

## 范围

**在范围内：**

- 三级服务架构：公开（内网免费模型）、团队（商用模型）、个人（用户自有模型）
- LiteLLM Master Key 配置和管理
- 统一 OpenAI 兼容接口

**不在范围内：**

- 不实现模型训练/微调
- 不负责模型推理本身（那是 vLLM serve 脚本的职责）

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| 模型接入数 | 0 | ≥ 3 级服务各至少 1 个模型可用 | 实际调用验证 |
| 接口兼容性 | — | 所有模型通过统一 `/v1/chat/completions` 调用 | curl 验证 |

## 用户故事

- 作为开发者，我希望一站式接入内外部模型，无需分别配置
- 作为团队管理员，我希望自部署模型能够实现负载均衡
- 作为测试人员，我希望按功能聚合模型，方便对比不同模型能力

## 需求详情

### 三级服务架构

| 级别 | 说明 | Master Key | 配置方式 |
| ---- | ---- | :--------: | -------- |
| 公开 | 本地部署免费模型供内网使用 | 不需要 | `third-party/litellm-public.yaml` |
| 团队 | 聚合团队购买的商业模型 | 需要 | `third-party/litellm-private.yaml` |
| 个人 | 用户个人购买的模型 | 需要 | `third-party/litellm-private.yaml` |

## 关联

- `pyproject.toml` — litellm 服务启动命令
- `scripts/activation/litellm.sh` — 环境变量
- `litellm.yaml` / `third-party/litellm-public.yaml` / `third-party/litellm-private.yaml`

## 迭代记录

### Iteration 20260517.01

按新模板改写，补齐范围、成功指标。
