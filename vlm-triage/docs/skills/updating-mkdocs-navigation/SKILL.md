---
name: updating-mkdocs-navigation
description: When adding new documentation pages or reorganizing the documentation structure, update mkdocs configuration and navigation to ensure pages are discoverable and properly linked.
---

# Skill: Updating mkdocs Configuration and Navigation

When adding new documentation pages or reorganizing the documentation structure, update `mkdocs.yml` to ensure all pages are discoverable and properly linked.

## Key Files

- **mkdocs.yml** — 主配置，包含导航结构
- **docs/** — 所有文档页面

## Current Navigation Structure

```yaml
nav:
  - 首页: index.md
  - 项目介绍:
      - 项目概述: project-orientation.md
      - 开发上手: onboarding.md
  - Agent 系统:
      - instructions/README.md
      - 共享知识库: instructions/shared-knowledge.md
      - Copilot 指令: instructions/copilot-instructions.md
  - 开发规范:
      - rules/README.md
      - 编码规范: rules/coding-guidelines.md
      - 类型注解: rules/type-annotations.md
      - 开发圣经: guides/development-bible.md
  - 使用技能:
      - 技能索引: skills/README.md
      - 项目与流程:
          - 开始开发: skills/start-development/SKILL.md
      - 文档治理:
          - MkDocs 导航更新: skills/updating-mkdocs-navigation/SKILL.md
          - 新增代码目录: skills/adding-new-code-directories/SKILL.md
          - 秘钥泄漏检查: skills/checking-for-secret-leaks/SKILL.md
      - 应用与服务:
          - Streamlit 应用开发: skills/streamlit-app-development/SKILL.md
          - tmux 服务管理: skills/serve-services-in-tmux/SKILL.md
  - 指南:
      - guides/README.md
  - 文档模板:
      - templates/README.md
  - 看板:
      - kanban/README.md
  - 代码文档: reference/
```

## Common Update Patterns

### 1. 新增页面到已有分类

```yaml
  - 使用技能:
      - 技能索引: skills/README.md
      - 应用与服务:
          - Streamlit 应用开发: skills/streamlit-app-development/SKILL.md
          - tmux 服务管理: skills/serve-services-in-tmux/SKILL.md
          - 新技能: skills/new-skill/SKILL.md  # 新增
```

### 2. 新增顶层分类

```yaml
nav:
  # ... 现有分类 ...
  - API 参考:
      - api/README.md
      - 核心模块: api/core.md
```

然后创建对应目录和文件：

```bash
mkdir -p docs/api/
touch docs/api/README.md docs/api/core.md
```

### 3. 仅修改显示标题（不改文件名）

```yaml
- 使用 Streamlit 开发应用: skills/streamlit-app-development/SKILL.md
```

### 4. Watch 列表

新增代码目录时同步更新 `watch:` 以支持热重载：

```yaml
watch: ["apps", "lib", "models", "scripts", "tests", "new-dir"]
```

## Verification Steps

```bash
# 构建文档，检查错误
pixi run mkdocs-build

# 检查缺失页面
pixi run mkdocs-build 2>&1 | grep -i "error\|404\|missing"

# 本地预览
pixi run mkdocs-serve
```

## Troubleshooting

| 问题 | 原因 | 修复 |
|------|------|------|
| 页面不出现 | 路径拼写错误 | 对比 mkdocs.yml 与 `ls docs/path/` |
| Build 失败 | 插件未安装或未配置 | `pixi list \| grep mkdocs` |
| 搜索失效 | 未重建索引 | 重跑 `pixi run mkdocs-build` 后清浏览器缓存 |

## Related Skills

- **adding-new-code-directories** — 新增代码目录时需一并更新 mkdocs.yml

## See Also

- `mkdocs.yml` — 主配置文件
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
