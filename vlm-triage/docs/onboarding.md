# Development Onboarding

新成员和 Agent 的开发上手指南，适合人类和 Agent 使用。

## 环境搭建

```bash
# 1. 安装 Pixi（项目唯一依赖管理工具，不用 pip/conda）
curl -fsSL https://pixi.sh/install.sh | bash

# 2. 安装项目依赖
pixi install

# 3. 可选：软链缓存目录（避免重复下载）
ln -s ~/mount-env/luonairui/cache/ cache
```

## 开发工作流

```bash
pixi run etest                              # 运行所有测试
pixi run fastapi dev apps/<name>/main.py   # 启动服务
python lib/tools/resources/__init__.py     # 快速测试资源工具
dcl                                         # 提交代码（不要 git commit）
```

## 测试策略

- **内联测试**（优先）：在模块内写 doctest，通过 shebang 直接运行文件
- **复杂测试**：位于 `tests/`，通过 `pixi run etest` 批量运行
- **pytest**：VS Code 测试扩展可自动发现并运行

## 关键概念

| 概念 | 说明 |
|------|------|
| **CR** | Code Review（代码评审）；CR 定位 = 找出引起产品表现变更的 commit |
| **Resource** | 可寻址的数据单元，通过 ID 访问（`FileStorage`/`HTTPStorage`） |
| **Deps** | Agent 依赖 dataclass，含 `session_id`、模型、provider 等 |
| **session_context** | 资源访问必须在此 context 内进行 |

## DO / DON'T

**DO**
- 优先写 doctest（在 conftest.py 满足依赖的情况下）
- 添加显式依赖到 pyproject.toml（严禁 pip install、添加 uv、conda 依赖）
- 使用 dcl 提交代码

**DON'T**
- 不用 pip/conda 直接安装（用 pixi）
- 不直接 git commit（用 dcl）
- 不跳过环境配置直接运行代码

## 参考资料

- [project-orientation.md](project-orientation.md) — 项目架构和场景理解
- [rules/README.md](rules/README.md) — 代码规范（必读）
- [skills/README.md](skills/README.md) — 具体技能文档
- [CONTRIBUTING.md](CONTRIBUTING.md) — 贡献流程
