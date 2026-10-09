# 编码规范

## 1. 基本规范

### 1.1 模块和导入规范

```python
# GOOD: import 只导入模块
import os.path as osp
import asyncio, logging, os  # 多个标准库可一行

# GOOD: from ... import 只导入非模块
from lib.tools.resources import get_default_resource_repo, session_context

# BAD
from os import path          # from 导入模块
import lib.tools.resources.storage  # 过深
```

### 1.2 通用命名规范（种-属-名三段式）

```python
# 种-属-名三段式
image_storage      # storage 是种，image 是属
trip_id_provider   # provider 是种，trip_id 是属
visual_model_client # client 是种，visual_model 是属

# 集合命名
resources: list[Resource]               # 一层集合
resources_by_id: dict[str, Resource]    # 映射
resource_ids: list[str]                 # ID 列表
resource_idss: list[list[str]]          # 嵌套列表（少见，慎用）

# 科学计算命名（张量）
x_a: np.ndarray       # 一维
x_nhw3: np.ndarray    # N×H×W×3
x_nc: np.ndarray      # N×C，广播时写 x_1c 或 x_nc 明确维度

# 科学计算命名（DataFrame）
data_f: pd.DataFrame      # 无特定 index
pose_t_f: pd.DataFrame    # index 为 timestamp
score_ci_f: pd.DataFrame  # MultiIndex: (category, item)
```

### 1.3 参数末位逗号

```python
# GOOD: 后面可能有更多参数，加逗号
def create(
        image_id: str,
        session_id: str,
        **kwargs)  # **kwargs 后不加

# BAD: slice 最多 3 个参数，逗号产生误导
x = slice(1, 9, 2,)
```

### 1.4 其他约束

- repr/str 转换：用 `ast.literal_eval`，禁用 `eval`
- `zip()` 必须显式写 `strict=True/False`
- 集合排升序（import、.gitignore 等）
- builtin 冲突用下划线规避：`id_`, `type_`, `filter_`

---

## 2. 约定俗成

### 2.1 字符串字面量引号

| 场景 | 引号 |
|------|------|
| docstring、多行字面量 | 双引号 `"` |
| Schema Literal、enum、API/JSON 相关 | 双引号 `"` |
| 一般自由形态字符串 | 单引号 `'` |
| Python 空串（非 schema/enum） | `''` |
| YAML 字符串 | 双引号 `"` |

### 2.2 Shebang（模块运行入口）

**App 入口**（切换 Pixi 环境运行）：
```python
#!/usr/bin/env -S pixi run -e vllm -- python
```

**lib 模块内联测试**（shell trick 形式，无法写模块 docstring）：
```python
#!/bin/sh
""":"
exec pixi run -- test "$0" "$@"
"""
```

直接运行文件即可启动：
```bash
apps/embedding_cr_locator_api/main.py   # 启动服务
lib/algorithms/max_coverage.py          # 运行内联测试
```

> ⚠️ shell trick shebang 占用时**禁止**写模块 root docstring。

### 2.3 模式匹配 match-case

优先于 `if ... elif ...`，尤其处理 enum/Literal：

```python
for part in node.model_response.parts:
    match part:
        case TextPart() | ThinkingPart():
            st.markdown(part.content)
        case ToolCallPart(tool_name=tool_name, args=args):
            st.info(f'{tool_name} <- {args}')
        case _:              # 必须写 case _:
            st.warning(f'{part}')
```

- 尽量做抽取收窄变量 scope
- 不必硬套，复杂条件 `if` 更清晰时用 `if`

### 2.4 数据模型

用 `pydantic, dataclass, TypedDict` 做约束，**禁止** `dict[str, Any]`（除非兼容外部无用字段）。

构造时**必须关键字传参**：

```python
@dataclass
class TaskMeta:
    id: int
    job_id: int  # 外联 ID 加修饰区分

# 构造
meta = TaskMeta(id=1, job_id=42)  # 关键字传参
```

### 2.5 异常和断言

```python
# GOOD：断言友好，必须有说明信息
assert len(x) > 0, '`x` is empty!'
assert res["errno"] == 0, f'API error {res["errno"]}: {res["msg"]}'
assert isinstance(x, (int, float)), f'number expected, got {type(x)!r}'

# BAD：无说明信息的裸断言
assert len(x) > 0
assert isinstance(x, (int, float))

# IMPORTANT：线上代码不能assert，换成对应的 Exception，仅测试、脚本、工具可用
if len(x) == 0:
    raise ValueError('`x` is empty!')
```

---

## 3. 风格指南

### 3.1 Docstring 格式

**单行**（标题行不换行）：
```python
def f():
    r"""A simple func"""
    return 1
```

**多行**（前后各换一行）：
```python
def g():
    r"""
    A more descriptive func.

    Returns:
        int: The answer
    """
    return 42
```

**禁止写 `return None`**（下划线方法、测试、辅助函数尤其禁止）。

#### 测试函数 docstring

用 `验证` section（必须在 `Parameters` 前面，`Parameters` 写 `-`）：
```python
def test_batch_arrow_roundtrip():
    r"""
    测试 PyArrow RecordBatch 往返序列化。

    验证:
        - 可序列化为 Arrow IPC 格式
        - 反序列化后是 pandas DataFrame
        - 列名、行数、列数一致

    Parameters:
        -
    """
```

#### 模块 docstring

用 `Attributes` 触发 admonition：
```python
r"""
PyArrow 数据序列化工具模块。

主要功能:
    - tensor2batch: numpy → PyArrow RecordBatch
    - dump: 序列化为 Arrow IPC 或 Parquet
    - load: 反序列化

Attributes:
    -
"""
```

#### Section 多行文本缩进

```
Returns:
    A list of ``(start_index, end_index)`` tuples representing the selected
        intervals (inclusive indices).
```

---

## 4. 类型注解（详见 type-annotations.md）

类型注解相关规范请参阅专门的 [type-annotations.md](type-annotations.md) 文档。

---

## 5. 特殊场景

### 5.1 模块入口规范

**App 入口**（切换 Pixi 环境运行）：
```python
#!/usr/bin/env -S pixi run -e vllm -- python
```

**lib 模块内联测试**（shell trick 形式，无法写模块 docstring）：
```python
#!/bin/sh
""":"
exec pixi run -- test "$0" "$@"
"""
```

直接运行文件即可启动：
```bash
apps/embedding_cr_locator_api/main.py   # 启动服务
lib/algorithms/max_coverage.py          # 运行内联测试
```

> ⚠️ shell trick shebang 占用时**禁止**写模块 root docstring。

---

## 6. 文档治理规范

### 6.1 验证 section

测试函数 docstring 用 `验证` section（必须在 `Parameters` 前面，`Parameters` 写 `-`）：
```python
def test_batch_arrow_roundtrip():
    r"""
    测试 PyArrow RecordBatch 往返序列化。

    验证:
        - 可序列化为 Arrow IPC 格式
        - 反序列化后是 pandas DataFrame
        - 列名、行数、列数一致

    Parameters:
        -
    """
```

## Shell 编码规范

- 最大化兼容性：支持 shell，避免 bash/zsh 特有语法
- 引号使用：字符串默认双引号
- 变量：写 `${var}` 而非 `$var`
- 命名：全局 const 变量大写，局部变量小写，函数小写
