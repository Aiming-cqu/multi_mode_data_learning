# Agent Shared Knowledge

所有 Agent 指令的共享基础，各厂商 instructions 应引用本文档，不重复其内容。

---

## 项目定位

**vlm-triage** — 基于 VLM 的自动驾驶路测问题排查工具集。

将多模态数据（图像、视频、日志、表格）结合 VLM + embedding + Agent，自动定位路测问题场景。

**三大应用场景：**

- Issue 场景分析：多模态结构化分析，输出道路信息、自驾状态、接管动作等
- 仿真 Diff 分析：对比两版本仿真动画，VLM Agent 自主采样归因
- 仿真拐点定位：定位仿真行为发生变化的时间点

---

## 代码库结构

```
apps/*/           应用入口（CLI / FastAPI / Streamlit），每个场景一个子目录
lib/tools/
  resources/      资源和存储抽象（FileStorage、HTTPStorage、pydantic_ai toolset）
  data_providers/ 将 issue_id/trip_id 转换为 Resource 对象
lib/utils/
  llm_utils.py    模型选择和 Provider 初始化
lib/algorithms/   核心算法（特征提取、相似度、CR定位等）
lib/platforms/    平台集成（Orion、Voyager）
```

---

## 核心编码模式

### Agent 构建
```python
from pydantic_ai import Agent
from dataclasses import dataclass

@dataclass
class Deps:
    session_id: str
    visual_model: str
    provider: OpenAIProvider  # 按需

agent = Agent(model, deps_type=Deps, toolsets=[ImageToolset(), ...])
```

### 工具函数
```python
from pydantic_ai import RunContext
from lib.tools.resources import session_context

async def my_tool(ctx: RunContext[Deps], resource_id: str) -> str:
    with session_context(session=ctx.deps.session_id):
        resource = get_default_resource_repo().get(resource_id)
        return resource.url
```

### 多媒体限制
- 视觉模型：≤5 张图像 **或** ≤2 段视频（二选一）
- 暂时性错误 → raise `ModelRetry`，不要吞异常

---

## 开发命令

```bash
pixi install              # 安装依赖（不用 pip/conda）
pixi run etest            # 运行所有测试
pixi run fastapi dev apps/<name>/main.py  # 启动 FastAPI 服务
dcl                       # 代码提交（不要直接 git commit）
```

---

## 协作与收尾

- 需求模糊时先澄清，不要脑补缺失约束。
- 一旦开始行动，无论任务受阻还是顺利完成，结束前都必须使用宿主提供的提问工具确认下一步行动；在 Copilot CLI 中使用 `ask_user`，若宿主命名为 `ask_question` 则使用其等价工具。提问时应给出明确示例（如“是否需要我 review 改动”），并保留自由输入选项。

---

## 编码规范要点

详见 [guides/development-bible.md](../guides/development-bible.md) 和 [rules/README.md](../rules/README.md)。关键约定：

- `import ...` 只导入模块；`from ... import ...` 只导入非模块
- 命名：种-属-名三段式（`image_storage`，`trip_id_provider`）
- docstring：单行 `r"""..."""`；多行前后换行；测试函数用 `验证:` section；模块用 `Attributes:` 触发 admonition

```python
# 单行
def f(): r"""A simple func"""

# 多行
def g():
    r"""
    A more descriptive func.

    Returns:
        int: The answer
    """

# 测试函数
def test_roundtrip():
    r"""
    测试往返序列化。

    验证:
        - 可序列化
        - 反序列化后结构一致

    Parameters:
        -
    """

# 模块
r"""
模块说明。

主要功能:
    - func_a: 做 A
    - func_b: 做 B

Attributes:
    -
"""
```
- 类型注解：用 `tuple/list/dict`（小写），入参用抽象类型（`Sequence`），返回值用具体类型
- 参数末位逗号：仅当后续可能还有参数时才加
- 张量命名：命名维度法（`x_nc`：N×C 矩阵）；DataFrame：索引法（`pose_t_f`：index 为 time 的 pose 表）
