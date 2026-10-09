# Project Orientation

vlm-triage 的项目背景和架构概览，适合人类和 Agent 快速建立认知。

## 项目定位

**vlm-triage** — 基于视觉-语言模型（VLM）的自动驾驶路测问题排查工具集。

将多模态数据（图像、视频、日志、表格）结合 VLM + embedding + Agent，帮助工程师自动定位路测问题场景。

## 三大应用场景

| 场景 | 描述 |
|------|------|
| **Issue 场景分析** | 多模态结构化分析，输出道路信息、自驾状态、接管动作、关键冲突对象 |
| **仿真 Diff 分析** | 对比两版本仿真动画，VLM Agent 在 30s 场景内自主采样归因 |
| **仿真拐点定位** | 定位仿真行为发生变化的时间点 |

## 架构三层

```
应用层     apps/*/     CLI / FastAPI / Streamlit（三种形态，同一业务逻辑）
           │
Agent层    lib/tools/  资源存储抽象（FileStorage、HTTPStorage）
           │           pydantic_ai FunctionToolset
           │           data_providers（trip_id/issue_id → Resource）
           │
Model层    lib/utils/llm_utils.py  模型选择 & Provider 初始化
           lib/algorithms/         核心算法（特征提取、相似度等）
           lib/platforms/          平台集成（Orion、Voyager）
```

## 核心设计原则

- **工具化设计**：所有模块支持 ① 独立测试 ② RESTful API ③ Agent 工具调用
- **功能为中心**：不限于 LLM，综合运用工具、特征工程、embedding、LLM、Agent
- **多环境部署**：CLI（批处理）、FastAPI（服务化）、Streamlit（可视化）

## 快速上手

```bash
pixi install              # 安装依赖
pixi run etest            # 运行测试
pixi run fastapi dev apps/<name>/main.py  # 启动 FastAPI
```

详细上手流程见 [onboarding.md](onboarding.md)。

