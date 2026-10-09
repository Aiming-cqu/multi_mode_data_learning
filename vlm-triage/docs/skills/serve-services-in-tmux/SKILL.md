---
name: serve-services-in-tmux
description: 在 tmux 中持久化运行 vlm-triage 服务，包括新建 session、启动服务、多服务管理、日志查看等。
---

# Serve Services in tmux Skill

Act 类技能：在 tmux 中持久化运行 vlm-triage 服务。

## 何时使用

需要在后台持久运行 FastAPI 服务、模型推理服务，或在 SSH 断开后保持服务存活时使用。

## 快速开始

```bash
# 新建 session 并启动服务
tmux new-session -d -s vlm-triage-dev 'pixi run fastapi dev apps/visual_cr_locator_api/main.py'

# 查看运行状态
tmux attach -t vlm-triage-dev

# 后台退出（不关闭服务）
# 按 Ctrl+B，然后按 D

# 停止服务
tmux kill-session -t vlm-triage-dev
```

## 多服务管理

```bash
# 同一 session 内开多个窗口
tmux new-session -s services
tmux new-window -t services -n api    'pixi run fastapi dev apps/embedding_api/main.py'
tmux new-window -t services -n model  'pixi run -e vllm -- python apps/vllm_serve/main.py'

# 列出所有 session
tmux ls

# 切换窗口
tmux select-window -t services:api
```

## DO / DON'T

**DO**
- 给 session 和 window 取有意义的名字
- 后台退出用 `Ctrl+B D`（detach），不要直接关终端
- 用 `tmux ls` 检查服务是否在运行

**DON'T**
- 不在主终端直接 `&` 后台运行（进程会随 SSH 断开）
- 不混用多个服务在同一个 tmux window（难以排查日志）
