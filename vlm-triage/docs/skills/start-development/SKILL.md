---
name: start-development
description: 启动 kanban 中 feature 或 task 的开发流程，包括识别任务、建立开发环境、版本控制等。
---

# Skill: Start Development

Act 类技能：帮助 AI 工具识别和启动 kanban 中 feature 或 task 的开发流程。

## 何时使用

用户发起开发请求时使用，帮助识别待开发的 feature 或 task，建立开发环境并启动开发。

## 快速开始

```bash
# 1. 识别待开发任务
ls docs/kanban/features/   # 功能需求
ls docs/kanban/tasks/      # 工程任务

# 2. 创建开发分支
git checkout -b feature/<name>   # 功能分支
git checkout -b task/<name>      # 工程任务分支

# 3. 启动开发环境
pixi shell                       # 进入默认开发环境
```

## 开发流程

1. **阅读任务文档** — 在 `docs/kanban/` 找到对应 feature 或 task 文档，了解需求背景
2. **建立分支** — 分支名与任务名对应，使用 kebab-case
3. **阅读规范** — 开发前阅读 `docs/rules/coding-guidelines.md`
4. **开发实现** — 遵循编码规范，写单元测试
5. **完成确认** — 向用户确认下一步行动（如：是否需要 review、是否需要提交）

## DO / DON'T

**DO**
- 开发前先确认需求文档存在且内容清晰
- 分支名与任务文档文件名保持一致
- 完成后用 `ask_question`（Copilot CLI 中为 `ask_user`）向用户确认下一步行动，并带上自由输入选项

**DON'T**
- 不在 main/master 分支直接开发
- 需求不明时不要直接动手写代码，先澄清

## 故障排查

| 问题 | 解决 |
|------|------|
| 找不到任务文档 | 检查 `docs/kanban/features/` 和 `docs/kanban/tasks/` |
| 分支已存在 | `git checkout <branch>` 切换到已有分支 |
| 环境启动失败 | 检查 `scripts/activation/local.sh` 配置是否完整 |

## See Also

- `docs/kanban/` — 任务看板
- `docs/rules/coding-guidelines.md` — 编码规范
