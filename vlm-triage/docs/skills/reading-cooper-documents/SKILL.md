---
name: reading-cooper-documents
description: 读取 Cooper 平台上的文档内容（协作文档或团队文件），通过 CLI 导出后转换为 Markdown，供 Agent 分析和引用。
---

# Skill: Reading Cooper Documents

读取 Cooper 平台上的文档内容，供 Agent 分析和引用。

## Overview

Cooper 平台有两种文档类型，对应不同的下载方式和 URL 格式：

| 类型 | URL 格式 | CLI 命令 | 产物 |
|------|---------|---------|------|
| 协作文档 | `https://cooper.didichuxing.com/docs2/document/{resource_id}` | `pixi run -e prod cooper-read <URL>` 或 `pixi run cooper-cli export` | Markdown（直接）或 `.docx` |
| 团队文件 | `https://cooper.didichuxing.com/team-file/{group_id}/{resource_id}` | `pixi run cooper-cli get` | `.zip`（目录打包） |

## 推荐方式：一行命令 (cooper-read)

**最简单的方式是直接使用 `cooper-read` 命令**，自动完成导出 → 转换 → 输出：

```bash
# 直接获取 Markdown 内容
pixi run -e prod cooper-read https://cooper.didichuxing.com/docs2/document/2207083647552

# 保存到文件
pixi run -e prod cooper-read https://cooper.didichuxing.com/docs2/document/2207083647552 > /tmp/doc.md

# 使用 Agent 工具调用（通过 `markitdown-mcp-convert_to_markdown`）
# Agent 可直接调用该工具，传入 Cooper URL
```

`cooper-read` 工具：
- 自动解析 Cooper URL
- 从 Cooper 导出文档
- 通过 markitdown 转换为 Markdown
- 直接输出到 stdout（无需临时文件）
- 处理 DOCX 样式问题（自动归一化）

## 手动步骤（适用于调试或特殊需求）

### Step 1: 下载文档

**协作文档**（docs2 URL）— 使用 `export`：

```bash
# 通过 resource_id
pixi run cooper-cli export /tmp/doc.docx 2207460511730

# 通过 URL
pixi run cooper-cli export /tmp/doc.docx --url https://cooper.didichuxing.com/docs2/document/2207460511730

# 直接输出到 stdout，继续 pipe 给 markitdown（stdin 模式需要扩展名提示）
pixi run cooper-cli export - --url https://cooper.didichuxing.com/docs2/document/2207460511730 | pixi exec markitdown -x docx > /tmp/doc.md

# 如果遇到 `KeyError: 'w:type'`，先做 DOCX 归一化再转换
pixi run cooper-cli export - --url https://cooper.didichuxing.com/docs2/document/2207460511730 | pixi run cooper-cli normalize-docx | pixi exec markitdown -x docx > /tmp/doc.md
```

**团队文件**（team-file URL）— 使用 `get`：

```bash
# 通过 group_id + resource_id
pixi run cooper-cli get /tmp/files.zip 2199094698523 2207369729546

# 通过 URL（resource_id 指向目录时，Cooper 返回目录内容的 ZIP 包）
pixi run cooper-cli get /tmp/files.zip --url https://cooper.didichuxing.com/team-file/2199094698523/2207369729546
```

!!! note
    team-file URL 中的 resource_id 通常指向目录（当前浏览位置），get 会将整个目录打包为 ZIP。
    如需下载目录中的特定文件，先 `pixi run cooper-cli ls` 列出目录，再用具体的 resource_id 下载。

### Step 2: 转换为 Markdown

下载的 `.docx` / `.xlsx` 等文件需要转换为 Markdown 才能供 Agent 阅读。以下工具均可使用，按推荐顺序排列：

#### 方法 A: markitdown CLI（推荐，最简单）

```bash
pixi exec markitdown /tmp/doc.docx > /tmp/doc.md
```

#### 方法 B: mammoth（专用于 .docx，保留结构更好）

```bash
pixi exec mammoth /tmp/doc.docx /tmp/doc.md
```

#### 方法 C: markitdown MCP Server（适合 Agent 工具调用场景）

```bash
# 启动 MCP server（Agent 自动连接）
pixi exec markitdown-mcp-server
```

或者使用 uvx 方式：

```bash
uvx markitdown-mcp==0.0.1a4
```

MCP server 提供 `convert_to_markdown` 工具，Agent 可直接调用传入文件路径。

### Step 3: 读取 Markdown 内容

转换完成后，直接读取生成的 `.md` 文件即可。

## 一站式示例

### 使用 cooper-read（推荐，一行命令）

```bash
# 最简单的方式：直接获取 Markdown
pixi run -e prod cooper-read https://cooper.didichuxing.com/docs2/document/2207083647552

# 保存到文件
pixi run -e prod cooper-read https://cooper.didichuxing.com/docs2/document/2207083647552 > /tmp/report.md
cat /tmp/report.md

# Agent 通过 markitdown-mcp 工具调用（自动处理）
# 无需手动执行，Agent 可直接使用 markitdown-mcp-convert_to_markdown 工具
```

### 手动分步方式（仅用于调试）

```bash
# 导出 Cooper 协作文档并转换
pixi run cooper-cli export /tmp/report.docx --url https://cooper.didichuxing.com/docs2/document/2207460511730
pixi exec markitdown /tmp/report.docx > /tmp/report.md
cat /tmp/report.md
```

```bash
# 无临时文件：直接流式导出并转换
pixi run cooper-cli export - --url https://cooper.didichuxing.com/docs2/document/2207460511730 | pixi exec markitdown -x docx > /tmp/report.md
cat /tmp/report.md
```

```bash
# 如果 DOCX 样式不规范，先归一化再交给 markitdown
pixi run cooper-cli export - --url https://cooper.didichuxing.com/docs2/document/2207460511730 | pixi run cooper-cli normalize-docx | pixi exec markitdown -x docx > /tmp/report.md
cat /tmp/report.md
```

```bash
# 下载团队文件目录并处理
pixi run cooper-cli get /tmp/files.zip 2199094698523 2207369729546
unzip -o /tmp/files.zip -d /tmp/cooper_files/
# 逐个转换需要的文件
pixi exec markitdown /tmp/cooper_files/some_doc.docx > /tmp/some_doc.md
```

## URL 辨别指南

拿到一个 Cooper URL 时，根据路径判断使用哪个命令：

- 包含 `/docs2/document/` → **协作文档** → 用 `pixi run -e prod cooper-read <URL>`（推荐）或 `pixi run cooper-cli export`
- 包含 `/team-file/` → **团队文件** → 用 `pixi run cooper-cli get`

## 转换工具对比

| 工具 | 安装方式 | 支持格式 | 特点 |
|------|---------|---------|------|
| `markitdown` | `pixi exec markitdown` | docx, xlsx, pptx, pdf, html, ... | 通用，格式支持广 |
| `mammoth` | `pixi exec mammoth` | docx | 专注 docx，语义保留好 |
| `markitdown-mcp-server` | `pixi exec markitdown-mcp-server` | 同 markitdown | MCP 协议，Agent 工具调用 |
| `markitdown-mcp` (uvx) | `uvx markitdown-mcp==0.0.1a4` | 同 markitdown | 同上，uvx 安装方式 |

## Troubleshooting

### `COOPER_USERNAME` 未设置

Cooper CLI 需要 `COOPER_USERNAME` 环境变量。确保 `scripts/activation/local.sh` 中已配置：

```bash
export COOPER_USERNAME="your_username"
```

### export 命令报错 "resource_id or --url is required"

`export` 必须指定 resource_id 或 --url。检查是否遗漏了参数。

### get 得到空 ZIP

team-file URL 的 resource_id 可能指向空目录。先用 `pixi run cooper-cli ls` 确认目录内容。

### `markitdown` / `mammoth` 报 `KeyError: 'w:type'`

这通常不是 `cooper export -` 的 stdout 管道问题，而是导出的 `.docx` 本身带有不规范的样式定义。已验证某些 Cooper / Shimo 导出的文档在 `word/styles.xml` 中包含缺失 `w:type` 的自定义 `<w:style>`，`markitdown` 和 `mammoth` 都会因此报错。

可用绕过方式：

1. 直接在管道中加一层归一化：`pixi run cooper-cli export - --url ... | pixi run cooper-cli normalize-docx | pixi exec markitdown -x docx`
2. 用 Word / WPS 打开后重新另存为新的 `.docx`
3. 手工解压 `.docx`，给缺失 `w:type` 的自定义样式补 `w:type="paragraph"`，再重新打包后交给 `markitdown`

## Related Skills

- **codebase-navigation-tooling** — 代码库导航
- **serve-services-in-tmux** — 在 tmux 中持久化运行服务

## See Also

- `lib/platforms/ep/cooper.py` — Cooper 平台集成代码和 CLI
- `docs/kanban/features/Cooper 平台接入.md` — Feature 跟踪
