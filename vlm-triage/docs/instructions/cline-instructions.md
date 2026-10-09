# Cline Agent Instructions

背景和编码规范见 [shared-knowledge.md](shared-knowledge.md)。

## Cline 特定约束

**命令执行**
- 能用 shell 一行搞定的，不要生成 Python 脚本
- 运行服务优先用 tmux，见 [skills/serve-services-in-tmux/SKILL.md](../skills/serve-services-in-tmux/SKILL.md)

**文件操作**
- 修改配置文件前先备份
- 大规模重构前确认范围

**代码生成**
- 遵循 [rules/coding-guidelines.md](../rules/coding-guidelines.md)
- 工具函数必须有 `RunContext[Deps]` 参数并使用 `session_context`
- 不直接调用模型 API，通过 pydantic_ai 封装

## 常用入口

```bash
# 快速测试资源工具
python lib/tools/resources/__init__.py

# 运行测试
pixi run etest

# 启动服务
pixi run fastapi dev apps/<name>/main.py
```
