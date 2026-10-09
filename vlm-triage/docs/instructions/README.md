# Agent Instructions

各 AI 编码工具的微调指令集。

## 共享基础

- [shared-knowledge.md](shared-knowledge.md) — 所有 Agent 共用的项目背景、架构、代码风格

## 厂商指令

- [copilot-instructions.md](copilot-instructions.md) — GitHub Copilot
- [cline-instructions.md](cline-instructions.md) — Cline
- [lingma-instructions.md](lingma-instructions.md) — 通义灵码

## 如何编写 Instruction

使用 `templates/instruction-template.md`。指令分两层：

1. **共享层** — 引用 `shared-knowledge.md`，避免重复
2. **厂商层** — 针对该工具特性的微调行为、输出格式、已知限制补偿
