# Vibe Coding 体验优化

| 属性 | 值 |
| ---- | --- |
| ID | vibe-coding-experience-optimization |
| 类型 | task |
| 优先级 | high |
| 状态 | active |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

优化 AI 辅助开发体验，包括多 agent 框架适配、开发指导完善、看板建设和 vibe-watcher 自动 checkpoint 工具。

## 背景

vibe coding 依赖优质模型、上下文工程和本地工具。当前项目使用 Copilot + Claude + Lingma 等多 agent，需要统一适配和指导。

## 范围

**在范围内：**

- 多 agent 框架适配（.github/copilot、.lingma 等）
- 开发指导完善（dev guide、code style、coding conventions）
- 看板建设（docs/kanban）
- vibe-watcher 工具（自动 checkpoint + push）
- 敏感信息脱敏检查

**不在范围内：**

- 不实现新的 agent 框架
- 不修改各 agent 厂商的工具链

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| agent 框架配置完整 | 缺 .lingma 等 | 所有常用 agent 有对应配置文件 | 代码审查 |
| vibe-watcher 可用 | 无 | start/status/finish 端到端通过 | 隔离仓库测试 |
| 看板卡片模板化 | 格式不统一 | 全部 active 卡片有 frontmatter + 成功指标 | 逐卡片审计 |

## Iterations

### Iteration 20260407.01

Vibe Coding 基建依赖：

- 优质模型
- 上下文工程
- 本地工具

模型体验现状

- Copilot + Claude Opus 4.6: 夯
- Lingma：捞
- 自定义模型：WIP

网络问题 - VS code 代理配置

```
    "http.noProxy": [
        "10.152.28.24",
        "10.152.24.170",
        "127.0.0.1"
    ],
    "http.proxy": "socks5://localhost:1080",
```

需求：

- Claude 走代理
- 其他模型和内网功能不走代理

代理设置 done

### Iteration 20260407.02

设想：通过 git checkout branch + git commit -m checkpoint + git push 的方式，保障 agent 产出及时落盘
调研相关方案，向我汇报，最后用 ask_question 向我确认下一步行动（如：在 scripts 下开发脚本），务必带上自由输入的选项。

### Iteration 20260407.03

不，我不希望这个工具能被agent干涉，我要的是在 vibe coding 启动时，自动/手动启动这个工具，作为后台进程，定时 commit 和 push 就好
回复我你的新设想
最后用 ask_question 向我确认下一步行动（如：在 scripts 下开发脚本），务必带上自由输入的选项。

### Iteration 20260407.04

讲讲脚本是如何被停止的，当vibe编码完成时应当如何合并回原来的分支？

最后用 ask_question 向我确认下一步行动（如：是否采取下一步行动），务必带上自由输入的选项。

### Iteration 20260407.05

watcher.sh finish 设计很好，监控 vscode, copilot 进程也很好，可以开发试试看吧

最后用 ask_question 向我确认下一步行动（如：review 代码），务必带上自由输入的选项。

## Iteration 20260410.2013

- finish 可以自动合并会原分支并添加（可交互）用户提供的message吗？
- feature/dev 分支是就地 snapshot commit 好还是 也 fork vibe 分支好呢


开始规划，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。

## Iteration 20260410.2030

解释

- squash-merge 是什么？
- finish 检查 working tree 是否干净 有必要吗？finish 自带 do_checkpoint

  origin_branch="$(cat /tmp/vibe-watcher-origin-branch 2>/dev/null || printf '')"
  vibe_branch="$(cat /tmp/vibe-watcher-vibe-branch 2>/dev/null || current_branch)"

是不是太不安全+健壮了

- 直接透传 git commit 参数，没有 -m 自动进入 editor 不好吗
- 各参数给个 short form

## Iteration 20260410.2044

- 健壮性我探讨的是如果有多个项目启动 vibe-watcher，临时文件会冲突
- 无参数应该这样：保护分支等只能 start -> 自动 start，已在 vibe 分支/运行中 -> status

改完提交代码再测

TODO:

- 设计测试方法，覆盖 vibe-watcher 所有功能
- 测试成功后将使用介绍更新到本文档
- 设计测试方法，覆盖 vibe-watcher 所有功能

## 脚本简介与测试结果

- 脚本路径: `scripts/vibe-watcher.sh`
- 功能: 在 Vibe Coding 会话期间作为后台守护进程，定时将变更 `git add`/`commit`/`push`，并在会话结束时提供 squash-merge 指南或自动合并。

### 已实现要点

- 支持参数: `--interval|-i`, `--branch-prefix|-p`, `--fork|-f`, `--auto-merge|-a`, `--origin|-o`。
- 每个项目使用基于仓库路径的 hash 生成唯一 PID 与状态临时文件，避免多项目冲突。
- `finish` 的实现改进：先停止后台 watcher，再做最终 checkpoint；在切换分支前临时抑制对日志文件的追加并 flush 残留变更，避免 "checkout would overwrite" 的竞态错误。
- `finish` 支持将后续参数透传给 `git commit`，请把 `git commit` 参数放在 `--` 之后，例如: `scripts/vibe-watcher.sh finish -a -- -m "feat: msg"`。

### 测试结果（已通过）

- 在隔离的临时仓库中进行了端到端验证：启动 `start`、触发变更、查看 `status`、执行 `finish --auto-merge --origin main -- -m ...`，自动合并成功。
- 使用的测试示例命令：

```
./scripts/vibe-watcher.sh start -i 2 -p test/vibe -f
./scripts/vibe-watcher.sh status
./scripts/vibe-watcher.sh finish --auto-merge --origin main -- -m "test-merged-by-test"
```

### 使用与注意事项

- 日志文件位置默认: `<repo-root>/logs/vibe-watcher.log`，可通过环境变量 `VIBE_WATCHER_LOG` 覆盖，建议放在仓库外或加入 `.gitignore` 避免被意外纳入提交。
- 传递给 `git commit` 的参数必须通过 `--` 隔开并正确引用（shell 引号），例如 `-- -m "your message"`。
- 如果需要，我可以把这段简介同步到 `README.md` 或 `docs` 的使用说明页。

开始规划，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。

## Iteration 20260412.1729

### 问题描述：`finish -a -m "msg"` 打开了 commit editor

用户运行 `scripts/vibe-watcher.sh finish -a -m 'add VLEmbeddingExtractor'`，预期直接提交，但弹出了 commit editor。

### 根本原因

`cmd_finish` 的参数解析中，`-m` 被 `*) shift ;;` 静默吞掉，没有传递给 `git commit`，导致 commit 无 `-m` 参数，进入 editor 模式。与此同时，脚本的非 auto-merge 提示文本里已经写了 `finish -a -m "feat: xxx"` 的用法，产生了文档和实现不一致的问题。

### 修复（`scripts/vibe-watcher.sh`）

将 `*) shift ;;` 改为"遇到未识别参数时 break，保留其及后续所有参数作为 git commit 参数"：

```sh
*) commit_args_provided=true; break ;;
```

效果：`finish -a -m "msg"` 和 `finish -a -- -m "msg"` 等价，均合法。同步更新 help 文本。

## Iteration 20260415.1820

- 扩展 `lib/utils/io_utils.py`：新增 `PathLikeStr`、`open_text_input()`、`open_text_output()`，统一 CLI 单文件 text/binary IO 的 stdio 入口
- `scripts/batch_locate.py` 改为通过 `io_utils` 处理 `--input/--output`，显式支持 `-` 映射到 stdin/stdout
- 当 `batch_locate` 输出到 stdout 时，进度和摘要信息改写到 stderr，避免污染 CSV 数据流
- 新增 `tests/batch_locate_test.py`，覆盖 stdin 读 locator_id、输出路径解析、stdout CSV 写入

## Iteration 20260416.0935

- `lib/utils/arrow_utils.py` 新增共享 seekable 适配层：对不可 seek 的 Arrow / Parquet 输入统一落到 spooled temp file，再交给 Arrow 读取逻辑
- Arrow `load()` 不再把 Parquet 的普通 Python 文件对象包进会关闭原流的 `pa.PythonFile` 路径；新增 non-seekable Arrow / Parquet 回归测试
- `lib/tools/resources/__init__.py` 中 `FileStorage.from_resource()` 现在优先走 `HTTPStorage -> FileStorage` 直连流式写盘，避免先转成 `MemoryStorage`
- `tests/resources_test.py` 增加本地 HTTP server 用例，验证 HTTP 资源可直接 materialize 为 `FileStorage` 且内容正确
- 复查 CLI 单文件 stdin/stdout 用法后，当前显著入口已收敛到 `lib/utils/io_utils.py` 和 `scripts/batch_locate.py`，未发现新的明显 ad hoc case
- 聚焦测试切片通过：`lib/utils/arrow_utils.py`、`tests/resources_test.py`、`tests/batch_locate_test.py`、`tests/cooper_test.py -k 'not test_upload_file and not test_export_cooperate'`
