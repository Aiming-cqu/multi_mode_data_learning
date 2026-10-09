# Type Annotations

## 基本约定

- 写类型批注，**除非**：
  - 测试代码（量大跟着变）
  - 纯数值短平快算法（阅读成本高于收益）
  - 数据科学对象（`ndarray, Tensor, Series, DataFrame`）——重在命名，批注无效
- Python 版本锚定 3.10，新功能通过 `typing_extensions` 引入

```python
from typing_extensions import Self, override
```

---

## 前向声明

```python
from __future__ import absolute_import, annotations  # 启用前向声明

import typing as tp

if tp.TYPE_CHECKING:
    from module import HeavyType  # 只在类型检查时导入
```

---

## Optional 写法

```python
# GOOD
field: tp.Optional[int]

# BAD：| None 是糟粕
field: int | None
```

---

## Annotated（带元数据的类型）

需要说明单位、含义等元数据时必须用 `Annotated`：

```python
# GOOD
issue_time: tp.Annotated[
    int,
    Field(description='接管时间点，单位毫秒'),
]

# BAD
issue_time: int = Field(description='接管时间点，单位毫秒')
```

---

## 容器类型

| 场景 | 写法 |
|------|------|
| 一般列表入参 | `Sequence[T]`（抽象，兼容性好） |
| 一般映射入参 | `Mapping[K, V]` |
| 需要可变 | `MutableSequence[T]`、`MutableMapping[K, V]` |
| 序列化场景 | `list`、`dict`（native 类型） |
| 返回值 | 具体类型（`list[T]`、`dict[K, V]`）——精确 |

禁止大写旧式：`List[T]`、`Dict[K, V]`、`Tuple[T, ...]`。

---

## 接口抽象

| 场景 | 用法 |
|------|------|
| 需继承重载的实现 | `ABC` |
| 鸭子 trait（无实现） | `Protocol`（禁止带实现） |
| 重载方法 | 必须写 `@override` |
| 禁止继承 | 慎用 `@final`（除非有强副作用，使继承毫无意义） |
| 类变量 | `ClassVar`（`dataclass, Protocol` 中必须写） |

---

## args/kwds 批注

```python
# GOOD：明确类型时批注
class MyDict(tp.Generic[K, V]):
    def __init__(self, **kwds: V): ...

# GOOD：包装函数用 ParamSpec
def wrap(func: tp.Callable[P, R], *args: P.args, **kwds: P.kwargs) -> R: ...

# GOOD：透传参数写明修饰
def load_and_plot(data_dir: str, *load_names: str, **plot_kwds):
    ...

# BAD：透传来源不明，类型写 Any 也错
def load_and_plot(data_dir: str, *args: str, **kwds: Any): ...
```

---

## 重载 @overload

```python
@tp.overload
def chunks(iterable: Iterable[T], *, max_size: int, max_length: Literal[0] = 0) -> Generator[Sequence[T], None, None]:
    r"""按 max_size 切分。"""
    ...

@tp.overload
def chunks(iterable: Iterable[T], *, max_size: Literal[0] = 0, max_length: int) -> Generator[Sequence[T], None, None]:
    r"""按 max_length 切分。"""
    ...

# 实现：覆盖所有重载参数组合，给默认值，写完整 docstring
def chunks(iterable: Iterable[T], *, max_size: int = 0, max_length: int = 0) -> Generator[Sequence[T], None, None]:
    r"""完整 docstring，包含所有重载形式介绍和示例。"""
    ...
```

---

## Coroutine vs Callable

`Coroutine` ≠ `Callable[..., Awaitable]`：

- `Coroutine`：一定是 async function
- `Callable[..., Awaitable]`：可以是 sync 的



## Use Constructor with Type Parameters

```
# GOOD
col_list = list[tp.Hashable](df.columns)

# NOT GOOD
col_list: list[tp.Hashable] = list(df.columns)
```
