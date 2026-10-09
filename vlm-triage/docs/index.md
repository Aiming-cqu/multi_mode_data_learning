# vlm-triage 文档

欢迎使用 vlm-triage 文档站点！

## 项目简介

**vlm-triage** 是一个基于视觉-语言模型（VLM）的自动驾驶路测问题切面化排查与分析工具集。

通过融合视觉-语言模型（VLM）、embedding 技术和智能代理系统，帮助工程师快速定位和分析路测中的问题场景。

## 核心特性

- **工具化设计**：所有功能模块支持 ① 独立测试 ② RESTful API 调用 ③ Agent 工具调用
- **功能为中心**：不限于 LLM，综合运用工具、特征工程、embedding、LLM、Agent 等技术
- **多环境部署**：支持批处理（CLI）、服务化（FastAPI）、可视化（Streamlit）三种形态

## 快速导航

### 🤖 Agent 系统

| 目录 | 描述 |
|------|------|
| [instructions/README.md](instructions/README.md) | 各厂商 Agent 微调指令；[shared-knowledge](instructions/shared-knowledge.md) 为共享基础 |
| [rules/README.md](rules/README.md) | 对 Agent 代码生成、命令执行的严格约束 |
| [skills/README.md](skills/README.md) | Agent 接入业务能力的技能文件 |
| [kanban/README.md](kanban/README.md) | 看板：需求、任务管理和记录 |

### 👥 人类开发者

| 文档 | 描述 |
|------|------|
| [project-orientation.md](project-orientation.md) | 项目概述与架构（for 人类 & agent） |
| [onboarding.md](onboarding.md) | 新成员快速上手（for 人类 & agent） |
| [guides/README.md](guides/README.md) | 人类向参考文档（开发圣经、标注指南等） |

### 📋 文档治理

| 资源 | 描述 |
|------|------|
| [templates/README.md](templates/README.md) | 标准文档模板（skill、rule、instruction、guide） |

## 开始使用

```bash
# 安装依赖
pixi install

# 运行测试
pixi run etest

# 启动服务
pixi run fastapi dev apps/visual_cr_locator_api/main.py
```

## 更多信息

- [GitHub 仓库](https://git.xiaojukeji.com/luonairui/vlm-triage)
- [贡献指南](CONTRIBUTING.md)
