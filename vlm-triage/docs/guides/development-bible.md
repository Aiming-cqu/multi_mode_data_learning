# DEVELOPMENT BIBLE

下面的规则非常主观，建议先写代码，到写不动或者想提交的时候来看一看，然后再去修改。

## Code Style

* 集合尽量排升序（如 import, .gitignores 等）
* zip(..., strict=...) 显式 `strict`
* 偶遇 repr/str 表示怎么办？用 `ast.literal_eval` 而不是 `eval`
* 所有标准库可以放第一行导入，去 TM 的 E401：`import asyncio, logging, inspect, io, os, typing as tp, weakref`
* `import ... (as ...)` 只能导入 **模块**，`from ... import ... (as ...)` 只能导入 **非模块**

```python
# GOOD
import os.path as osp

# BAD
from os import path
```

* 参数末位的逗号表明了传参的可延续性：

```python
# GOOD
1.__add__(
    a_long_long_expression  # add 是二元运算，不准加参数
)
def wrapper(
        arg1, arg2,
        **kwds)  # **kwds 后面不会有更多参数了

# BAD
x = slice(
    1,
    9,
    2,  # slice 至多接收 3 个参数，逗号产生误导
)
```

### Naming

命名非常重要

* 名词的三段命名：种-属-名，二级前缀足够准确，如果做不到，说明代码是大锅炖
* 复数：复数表述要精确，复数的位置表达了集合的层次
    - 注意本身是复数的名词：data，不能写 datas
    - 推荐表达 `objs: Sequence[Obj]`，`objs_by_name: Mapping[str, Obj]` ，`objs_name: Sequence[str]`, `objs_names: Sequence[Sequence[str]]`
    - 大数据类型用单数：`message_t_f: DataFrame` row 是 message，index 是 time；`feature_nc: Tensor` N x C 维的特征矩阵；
* 属性：...
* builtin 冲突：非构造场景建议用下划线规避：`def __init__(self, id: str, date: dt.datetime)`，`filter(obj_id: str, date_: dt.datetime, max_: int)`

#### 属性命名

作为数据结构体字段，命名应当简洁无歧义，而脱离结构时应当保持至少一段修饰：

```python
class TaskMeta:
    id: int
    job_id: int  # 外联 ID 应当有修饰区分

def get_issue_detail(issue_id: str) -> IssueDetail:
    ...
    return IssueDetail.validate({**res, "id": issue_id})
```

例中 `IssueDetail.id` 在结构体外应当命名为 `issue_id`

### 类型批注

* 写类型批注，除非：
	- 测试代码不用写，因为量大还会跟着变
	- 后面提到的写不出来的情况不用写
	- 纯数值短平快算法不用写，没有类型运算，阅读代码成本本身就高
	- 数据科学数据对象不用写：ndarray, Tensor, Series, DataFrame，写了没用，重在命名

* 使用类型批注前向声明：`from __future__ import absolute_import, annotations`
* 如果不需要具体类型，搭配 `if tp.TYPE_CHECKING: from module import Type` 使用前向声明
* 如果类型所在模块已经被导入，那就直接导入声明
* Python 版本锚定 3.10，新功能通过 `typing_extensions` 引入：`from typing_extensions import Self, override`
* 写 `Optional[int]` 而不是 `int | None`，`| None` 类型是糟粕
* 使用 `Annotated` 做代码类型注释，便于自动化生成文档，对下例这种单位需要说明的情况请务必编写。但不要用占位符：

```python
# GOOD
issue_time: tp.Annotated[
    int,
    Field(description='接管时间点，单位毫秒'),
]

# BAD
issue_time: int = Field(description='接管时间点，单位毫秒')
```

* `Coroutine` 和 `Callable[..., Awaitable]` 是不同的，前者一定是 async func，而后者可以是 sync 的
* 使用 `# type: xxx` 批注连等表达式：

```python
x = y = 1  # type: int
```

#### 抽象容器类型批注

* 不要写 `Tuple[T, ...], List[T], Dict[K, V]`，写 `tuple[T, ...], list[T], dict[K, V]` 或者 `Sequence[T], Mapping[K, V]`
* 合理使用抽象容器类型批注：
	- `Collection` 是不是比 `Sequence` 合适
	- 是否需要可变的 `MutableSequence, MutableMapping` ?
	- 入参用抽象类型因为它兼容（`Sequence`），返回值用具体类型因为它精确（`list`），当然，还得看你的抽象意图
	- 对于一些数据序列化反序列化的场景，只支持 native type，就写 `list, dict` 就好

#### 抽象接口批注

* 接口抽象：使用 `ABC` 声明需继承重载的实现，使用 `Protocol` 声明鸭子 trait，且不能带有实现
* 重载记得写 `@override`
* 不要轻易上 `@final` ，不可以禁止队友二次开发，除非有什么强副作用类型操作，使得它的继承毫无意义
* 类变量使用 `ClassVar` 批注，这在 `dataclass, Protocol` 中是必须的

### Shebang

我们通过强大的 shebang 切换 Pixi 环境并运行相应的模块功能。
如 VLLM 环境下的模型推理 app，它的 shebang 是：
> #!/usr/bin/env -S pixi run -e vllm -- python

对于 lib 目录下的大多数模块，它们支持内联测试，因此 shebang 是：
> #!/bin/sh
""":"
exec pixi run -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -- test

无论是运行 app 还是单测，只需要运行文件本身即可，如：

```shell
apps/embedding_cr_locator_api/main.py

lib/algorithms/max_coverage.py
```

注意当我们使用 shell trick 形式的 shebang 时，
我们无法编写模块 root docstring。
因此此时请不要编写 docstring
我们应尽快升级 coreutils 以支持 env -S 正常 shebang

### 字符串字面量引号使用

* 双引号用于：
	- docstring
	- 多行字面量
	- Schema Literal，enum 等可穷尽的特定值
	- API / JSON 相关高可交换写法：方便粘贴到其他语言/平台
* 单引号用于：
	- 自由形态字符串
	- 一般 Python 空串也用 ''，除非出现在  schema / enum 中

* 对于 YAML 字符串，默认用双引号引起来

### 科学计算

* 对于 tensor 类型使用 命名维度 命名法：
	- `x_a`: 表示一维数组
	- `x_nhw3`: 表示四维数组，维度是 N x H x W x 3
	- `x_nc + y_c`: 表示一个二维张量与一维张量运算，此时在第一维发生广播
	- `x_x1c + y_1yc`: 使用 xyz 表示 ... 不定维度，方便明确不固定维数张量的广播行为
* 对于 dataframe 类型使用 索引 命名法：
	- `data_f`: 表示未设置索引的表
	- `pose_t_f`: 表示 index 为 time(stamp) 的 pose 表，可以通过 time(stamp) 进行索引
* 关于 GEMM 广播：`einsum` is all you need

### schema

* schema 用 `pydantic, dataclass, TypedDict` 做约束和抽取，不要整 `dict[str, tp.Any]` 除非是去兼容外部用不上的字段
* 上述三类结构体构造时，必须采用关键字传参

### 条件控制

使用 `match ... case ...` 模式匹配优先于 `if ... elif ...`

* 尤其是处理 enum, literal
* 尽量做抽取收窄变量 scope
* 务必写上 `case _:`
* 模式匹配不是万能的，不必硬套

```python:
for part in node.model_response.parts:
    match part:
        case TextPart() | ThinkingPart():
            st.markdown(part.content, help=part.part_kind)
        case ToolCallPart(tool_name=tool_name, args=args):
            st.info(f'{tool_name} <- {args}', icon='🔥')
        case _:
            st.warning(f'{part}')
```

### 异步

* 同步链接池可以作为模块全局变量使用，同步链接池要使用 `LoopLocal` 或者放到 context lifespan 中
* 使用 `httpx`，别用 `requests`

### 异常

* 断言是友好的，推荐在简单场景用

```python
# GOOD
assert len(x) > 0, '`x` is empty!'

# BAD
if len(x) == 0: raise ValueError('`x` is empty!')

# OK
match x:
    case [y, *z]: pass
    case _: raise ValueError('`x` is empty!')
```

* 如果 `assert` 不够直观，务必补充说明

```python
# GOOD
assert res["errno"] == 0, f'API error {res["errno"]}: {res["msg"]}'
assert isinstance(x, (int, float)), f'number expected, got {type(x)!r}'
assert tensor.ndim == 2, f'tensor{tensor.shape} is not a matrix'

# BAD
assert res["errno"] == 0
assert isinstance(x, (int, float))
assert tensor.ndim == 2
```

### 传参

* 可选参数超过 4 个，考虑一下是否需要打包成 struct
* 递归透传参数，可以写成类：

```python
# GOOD
class _recurse_impl(tp.NamedTuple, tp.Generic[_P, _R]):
    fmt: str
    callback: tp.Callable[_P, _R]
    cb_kwds: _P.kwargs

    def recurse(self, x):
        self.callback(x, self.fmt, **self.cb_kwds)
        for i in x: self.recurse(i)

# BAD
def recurse(x, fmt: str, callback: tp.Callable, **cb_kwds):
    callback(x, fmt, **cb_kwds)
    for i in x: recurse(i, fmt, callback, **cb_kwds)
```

* 不要随便给 args, kwds 上类型批注
	- 自身明确类型的可以批注
	- 包装其他函数的可以使用 `ParamSpec` 批注
	- 其他情况 Python 还无法抽取，不要批注
	- 对复杂流程的部分透传要写明修饰

```python
# GOOD
class MyDict(tp.Generic[K, V]):
    def __init__(self, **kwds: V): ...

def wrap(func: tp.Callable[P, R], *args: P.args, **kwds: P.kwargs) -> R: ...

def load_and_plot(data_dir: str, *load_names: str, **plot_kwds):
    data = [load(f'{data_dir}/{name}', fmt='...') for name in load_names]
    plot(data, **plot_kwds)

# BAD
def load_and_plot(data_dir: str, *args: str, **kwds: Any):
    r"""
    1. 不知道 args, kwds 是给 load 还是 plot 传的
    2. plot 的参数类型抽取不了，写 **kwds: Any 货不对板
    """
```

* 参数重载写 `@overload`，写法参考：

```python
@tp.overload  # 1. 写 @overload
def chunks(
    iterable: tp.Iterable[_T],
    *,
    max_size: int,  # 2. 对当前重载收窄类型：非可选参数
    max_length: tp.Literal[0] = 0,  # 2. 对当前重载收窄类型：仅当为 0 时
) -> tp.Generator[tp.Sequence[_T], None, None]:
    r"""
    将可迭代对象按指定的批次数量切分为多个批次。  # 3. 当前重载的一句话 docstring
    """
    ...


@tp.overload  # 1. 下一个重载
def chunks(
    iterable: tp.Iterable[_TS],
    *,
    max_size: tp.Literal[0] = 0,
    max_length: int,
) -> tp.Generator[tp.Sequence[_TS], None, None]:  # 2. 当前重载的返回类型也要收窄
    r"""
    将可迭代对象按指定的批次总长度切分为多个批次。
    """
    ...


@tp.overload
def chunks(
    iterable: tp.Iterable[_TS],
    *,
    max_size: int,
    max_length: int,
) -> tp.Generator[tp.Sequence[_TS], None, None]:
    r"""
    将可迭代对象按指定的批次数量或总长度切分为多个批次，二者满足其一即生成。
    """
    ...

# 4. 函数实现，必须覆盖所有重载参数和类型组合，并给出默认值
def chunks(
    iterable: tp.Iterable[_T],
    *,
    max_size: int = 0,
    max_length: int = 0,
) -> tp.Generator[tp.Sequence[_T], None, None]:
    r"""
    # 5. 完整的 docstring，包含所有重载形式介绍，用例展示也在这里

    将可迭代对象按指定的批次数量或总长度切分为多个批次。

    该函数支持以下两种模式:
    1. 按 `max_size` 进行切分，每 `max_size` 个元素生成一个批次。
    2. 按 `max_length` 进行切分，当累积的元素长度达到 `max_length` 时生成一个批次。

    Args:
        iterable: 要进行切分的可迭代对象。
        max_size: 每个批次的最大元素数量
        max_length: 每个批次的最大元素总长度

    Yields:
        切分后的批次。

    Raises:
        AssertionError: 当 `max_size` 和 `max_length` 均小于等于 0 时抛出。

    示例:
    >>> list(chunks(['a', 'bc', 'def', 'gh'], max_size=3))
    [['a', 'bc', 'def'], ['gh']]

    >>> list(chunks(['a', 'bc', 'def', 'gh'], max_length=3))
    [['a', 'bc'], ['def'], ['gh']]
    """
    ...
```

#### repr 写法

```python
# for data-store structures, easily eval(repr(obj)) to recontruct
def __repr__(self) -> str:
    return (
        f'{self.__class__.__name__}(path={self.path!r}'  # first attribute here for no leading comma
        f', is_end={self.is_end!r}'  # !r is always prefered
        f', nchildren={len(self.children_by_name)}'  # if collection is hard to display, use nxxxs / num_xxxs to display it's size
        ')'
    )

# for resource types, display key metadata, and prohibt recontruction
def __repr__(self) -> str:
    return (
        f'<{self.__class__.__name__}'
        f' path={self.path!r}' # first attribute here for the leading is space
        f' is_end={self.is_end!r}'
        f' nchildren={len(self.children_by_name)}'  # remember to help fix typo like childrens, datas, etc.
        '>'
    )
```
