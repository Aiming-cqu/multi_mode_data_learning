#!/usr/bin/env -S pixi run -- test

r"""
PyArrow 数据序列化与反序列化工具模块。

该模块提供了对 numpy 数组、PyArrow Tensor、RecordBatch 和 Table 等数据类型的
序列化（dump）和反序列化（load）功能，支持 Arrow IPC 和 Parquet 两种格式。

主要功能:
    - tensor2batch: 将二维 numpy 数组转换为 PyArrow RecordBatch
    - dump: 将数据对象序列化为 Arrow IPC 或 Parquet 格式
    - load: 从 Arrow IPC 或 Parquet 格式反序列化数据

支持的数据类型:
    - numpy.ndarray: 二维数组，可序列化为 RecordBatch 或 Tensor
    - pyarrow.Tensor: 张量数据
    - pyarrow.RecordBatch: 记录批次
    - pyarrow.Table: 表格数据

支持的格式:
    - "arrow": Arrow IPC 格式，支持流式读写
    - "parquet": Parquet 列式存储格式

Attributes:
    -
"""

from __future__ import absolute_import, annotations

import typing as tp
import numpy as nt
import pyarrow as pa
import pyarrow.ipc as ipc

from pyarrow.parquet import ParquetFile, ParquetWriter

from .io_utils import ensure_seekable_input

if tp.TYPE_CHECKING:
    from pandas import DataFrame


DataType: tp.TypeAlias = tp.Union[pa.RecordBatch, pa.Table, pa.Tensor, nt.ndarray]
FormatType: tp.TypeAlias = tp.Literal["arrow", "parquet"]
StreamType: tp.TypeAlias = tp.Union[pa.NativeFile, tp.BinaryIO]


def tensor2batch(tensor: nt.ndarray, names: tp.Sequence[str]) -> pa.RecordBatch:
    r"""
    将二维 numpy 数组转换为 PyArrow RecordBatch。

    该函数将形状为 (n_rows, n_cols) 的二维数组转换为包含 n_cols 个列的 RecordBatch，
    每列对应原数组的一列数据。

    Args:
        tensor: 输入的二维 numpy 数组，形状为 (n_rows, n_cols)
        names: 列名列表，长度必须等于数组的列数

    Returns:
        包含输入数组数据的 PyArrow RecordBatch

    Raises:
        ValueError: 如果输入数组不是二维矩阵

    Examples:
        >>> import numpy as np
        >>> arr = np.arange(6).reshape(2, 3)
        >>> batch = tensor2batch(arr, ["a", "b", "c"])
        >>> batch.num_rows
        2
        >>> batch.num_columns
        3
        >>> batch.column_names
        ['a', 'b', 'c']
    """

    if tensor.ndim != 2:
        raise ValueError(f'tensor{tensor.shape} is not a matrix')
    return pa.RecordBatch.from_arrays(
        [pa.array(tensor[:, i]) for i in range(tensor.shape[1])],
        names=names,
    )


@tp.overload
def dump(
    obj: pa.Tensor,
    fmt: tp.Literal["arrow"],
    *,
    names: tp.Literal[None] = None,
    dim_names: tp.Literal[None] = None,
    stream: tp.Optional[pa.NativeFile] = None,
) -> pa.NativeFile:
    r"""
    序列化 `pa.Tensor` 为 Arrow IPC 只支持到 `pa.NativeFile`
    """
    ...


@tp.overload
def dump(
    obj: nt.ndarray,
    fmt: tp.Literal["arrow"],
    *,
    names: tp.Literal[None] = None,
    dim_names: tp.Optional[tp.Sequence[str]] = None,
    stream: tp.Optional[pa.NativeFile] = None,
) -> pa.NativeFile:
    r"""
    序列化非二维命名 `nt.ndarray` 为 Arrow IPC 只支持到 `pa.NativeFile`
    """
    ...


@tp.overload
def dump(
    obj: tp.Union[pa.Tensor, nt.ndarray],
    fmt: tp.Literal["arrow"],
    names: tp.Sequence[str],
    dim_names: tp.Literal[None] = None,
    stream: tp.Optional[pa.NativeFile] = None,
) -> pa.NativeFile:
    r"""
    指定列名可按 `RecordBatch` 序列化二维 tensor 为 Arrow IPC
    """
    ...


@tp.overload
def dump(
    obj: tp.Union[pa.Tensor, nt.ndarray],
    fmt: tp.Literal["arrow"],
    names: tp.Sequence[str],
    dim_names: tp.Literal[None],
    stream: tp.BinaryIO,
) -> tp.BinaryIO:
    r"""
    指定列名可按 `RecordBatch` 序列化二维 tensor 为 Arrow IPC
    """
    ...


@tp.overload
def dump(
    obj: tp.Union[pa.Tensor, nt.ndarray],
    fmt: tp.Literal["parquet"],
    names: tp.Sequence[str],
    dim_names: tp.Literal[None] = None,
    stream: tp.Optional[pa.NativeFile] = None,
) -> pa.NativeFile:
    r"""
    序列化二维 tensor 为 Parquet 必须给出列名
    """
    ...


@tp.overload
def dump(
    obj: tp.Union[pa.Tensor, nt.ndarray],
    fmt: tp.Literal["parquet"],
    names: tp.Sequence[str],
    dim_names: tp.Literal[None],
    stream: tp.BinaryIO,
) -> tp.BinaryIO:
    r"""
    序列化二维 tensor 为 Parquet 必须给出列名
    """
    ...


@tp.overload
def dump(
    obj: DataType,
    fmt: FormatType,
    names: tp.Optional[tp.Sequence[str]] = None,
    dim_names: tp.Optional[tp.Sequence[str]] = None,
    stream: tp.Optional[pa.NativeFile] = None,
) -> pa.NativeFile:
    r"""
    不给定 stream 时会创建 `pa.NativeFile`
    """
    ...


@tp.overload
def dump(
    obj: DataType,
    fmt: FormatType,
    names: tp.Optional[tp.Sequence[str]],
    dim_names: tp.Optional[tp.Sequence[str]],
    stream: tp.BinaryIO,
) -> tp.BinaryIO: ...


def dump(
    obj: DataType,
    fmt: FormatType,
    names: tp.Optional[tp.Sequence[str]] = None,
    dim_names: tp.Optional[tp.Sequence[str]] = None,
    stream: tp.Optional[StreamType] = None,
) -> StreamType:
    r"""
    将数据对象序列化为 Arrow IPC 或 Parquet 格式。

    支持的数据类型包括 numpy 数组、PyArrow Tensor、RecordBatch 和 Table。
    对于 numpy 数组，可以指定列名以 RecordBatch 形式序列化，或以 Tensor 形式序列化。

    Args:
        obj: 要序列化的数据对象，支持 pa.Tensor、nt.ndarray、pa.RecordBatch、pa.Table
        fmt: 输出格式，可选 "arrow" 或 "parquet"
        names: 列名列表，用于将二维数组转换为 RecordBatch/Table 时指定列名
        dim_names: Tensor 的维度名称，仅在将 ndarray 以 Tensor 形式序列化时使用
        stream: 输出流，如果为 None 则创建 pa.BufferOutputStream

    Returns:
        包含序列化数据的流对象

    Raises:
        ValueError: 如果 fmt 不支持，或 parquet 格式未提供 names
        TypeError: 如果 obj 类型不支持

    Examples:
        >>> import numpy as np
        >>> arr = np.arange(6).reshape(2, 3)
        >>> # 以 Arrow IPC 格式序列化为 RecordBatch
        >>> stream = dump(arr, "arrow", names=["a", "b", "c"])
        >>> stream.seekable()
        False
        >>> # 以 Arrow IPC 格式序列化为 Tensor
        >>> stream = dump(arr, "arrow", dim_names=["row", "col"])
        >>> stream.seekable()
        False
    """

    match fmt:
        case "arrow":
            if isinstance(obj, nt.ndarray):
                if names is None:
                    obj = pa.Tensor.from_numpy(obj, dim_names=dim_names)
                else:
                    obj = tensor2batch(obj, names)
        case "parquet":
            if isinstance(obj, pa.Tensor):
                obj = obj.to_numpy()
            if isinstance(obj, nt.ndarray):
                if names is None:
                    raise ValueError('`names` required for creating table from tensor')
                obj = tensor2batch(obj, names)
        case _:
            raise ValueError(f'Unsupported {fmt=}')

    if stream is None:
        stream = pa.BufferOutputStream()

    match fmt:
        case "arrow":
            match obj:
                case pa.RecordBatch() | pa.Table():
                    with ipc.new_stream(stream, obj.schema) as writer:
                        writer.write(obj)
                case pa.Tensor():
                    ipc.write_tensor(obj, stream)
                case _:
                    raise TypeError(f'Unsupported `obj` type {type(obj)}')
        case "parquet":
            with ParquetWriter(stream, obj.schema) as writer:
                writer.write(obj)
        case _:
            raise ValueError(f'Unsupported {fmt=}')

    return stream


@tp.overload
def load(
    stream: StreamType,
    fmt: tp.Literal["arrow"],
    hint: tp.Literal["tensor"],
) -> pa.Tensor:
    r"""
    从 Arrow IPC 读 tensor
    """
    ...


@tp.overload
def load(
    stream: StreamType,
    fmt: tp.Literal["arrow"],
    hint: tp.Literal["table"],
) -> 'DataFrame':
    r"""
    从 Arrow IPC 以 DataFrame 形式读 table
    """
    ...


@tp.overload
def load(
    stream: StreamType,
    fmt: tp.Literal["parquet"],
    hint: tp.Optional[tp.Literal["table"]] = None,
) -> 'DataFrame':
    r"""
    从 Parquet 以 DataFrame 形式读 table
    """
    ...


def load(
    stream: StreamType,
    fmt: FormatType,
    hint: tp.Optional[tp.Literal["tensor", "table"]] = None,
) -> tp.Union[pa.Tensor, 'DataFrame']:
    r"""
    从 Arrow IPC 或 Parquet 格式反序列化数据。

    支持从 Arrow IPC 流中读取 Tensor 或 DataFrame，以及从 Parquet 文件中读取 DataFrame。
    对于 Arrow IPC 格式，如果没有提供 hint 且 stream 是 NativeFile，会自动检测数据类型。

    Args:
        stream: 输入数据流，支持 pa.NativeFile 或 tp.BinaryIO
        fmt: 输入格式，可选 "arrow" 或 "parquet"
        hint: 类型提示，可选 "tensor" 或 "table"，用于指定 Arrow IPC 数据的解析方式

    Returns:
        反序列化后的数据：pa.Tensor 或 pandas DataFrame

    Raises:
        TypeError: 如果 stream 类型不支持
        ValueError: 如果 fmt 或 hint 不支持

    Examples:
        >>> import numpy as np
        >>> import pyarrow as pa
        >>> # 创建测试数据并序列化
        >>> arr = np.arange(6).reshape(2, 3)
        >>> tensor = pa.Tensor.from_numpy(arr)
        >>> stream = dump(tensor, "arrow")
        >>> stream = pa.BufferReader(stream.getvalue())
        >>> # 以 tensor hint 读取
        >>> loaded = load(stream, "arrow", hint="tensor")
        >>> isinstance(loaded, pa.Tensor)
        True
        >>> np.array_equal(loaded.to_numpy(), arr)
        True
    """

    match fmt:
        case "arrow":
            hint_ = hint
            with ensure_seekable_input(stream) as file:
                if hint is None:
                    pos: int = file.tell()
                    hint_ = str(ipc.read_message(file).type)
                    file.seek(pos)
                match hint_:
                    case "tensor":
                        return ipc.read_tensor(file)
                    case "schema" | "table":
                        with ipc.open_stream(file) as reader:
                            return reader.read_pandas()
                    case _:
                        raise ValueError(f'Unsupported hint: {hint_!r}')
        case "parquet":
            with ParquetFile(stream) as reader:
                return reader.read().to_pandas()
        case _:
            raise ValueError(f'Unsupported {fmt=}')



def test_ndarray_arrow_tensor_roundtrip():
    r"""
    测试 numpy 数组以 Tensor 形式进行 Arrow IPC 序列化与反序列化的往返过程。

    验证:
        - 二维 numpy 数组可以正确序列化为 Arrow IPC Tensor 格式
        - 反序列化后得到的是 pa.Tensor 类型
        - 数据内容保持一致

    Parameters:
        -
    """

    arr = nt.arange(12).reshape(3, 4)

    out = dump(arr, "arrow")
    inp = pa.BufferReader(out.getvalue())
    tensor = load(inp, "arrow")

    assert isinstance(tensor, pa.Tensor), tensor
    nt.testing.assert_array_equal(tensor.to_numpy(), arr)


def test_ndarray_arrow_batch_roundtrip():
    r"""
    测试 numpy 数组以 RecordBatch 形式进行 Arrow IPC 序列化与反序列化的往返过程。

    验证:
        - 二维 numpy 数组可以正确序列化为 Arrow IPC RecordBatch 格式
        - 反序列化后得到的是 pandas DataFrame
        - 列名和数据内容保持一致

    Parameters:
        -
    """

    import pandas as pf

    arr = nt.arange(12).reshape(3, 4)
    names = ["a", "b", "c", "d"]

    out = dump(arr, "arrow", names=names)
    inp = pa.BufferReader(out.getvalue())
    df = load(inp, "arrow")

    assert isinstance(df, pf.DataFrame), df
    assert list(df.columns) == names, df.columns
    nt.testing.assert_array_equal(df.to_numpy(), arr)


def test_tensor_arrow_roundtrip():
    r"""
    测试 PyArrow Tensor 进行 Arrow IPC 序列化与反序列化的往返过程。

    验证:
        - pa.Tensor 可以正确序列化为 Arrow IPC 格式
        - 反序列化后数据内容保持一致

    Parameters:
        -
    """

    arr = nt.arange(6).reshape(2, 3)
    tensor = pa.Tensor.from_numpy(arr)

    out = dump(tensor, "arrow")
    inp = pa.BufferReader(out.getvalue())
    tensor2 = load(inp, "arrow")

    nt.testing.assert_array_equal(tensor.to_numpy(), tensor2.to_numpy())


def test_ndarray_parquet_roundtrip():
    r"""
    测试 numpy 数组进行 Parquet 序列化与反序列化的往返过程。

    验证:
        - 二维 numpy 数组可以正确序列化为 Parquet 格式
        - 反序列化后得到的是 pandas DataFrame
        - 列名和数据内容保持一致
        - 与 pandas 原生 read_parquet 结果一致

    Parameters:
        -
    """

    import io
    import pandas as pf

    arr = nt.arange(12).reshape(3, 4)
    names = ["a", "b", "c", "d"]

    stream = io.BytesIO()
    dump(arr, "parquet", names=names, stream=stream)
    stream.seek(0)
    df = load(stream, "parquet")
    stream.seek(0)
    df1 = pf.read_parquet(stream)

    assert list(df.columns) == names, df.columns
    nt.testing.assert_array_equal(df.to_numpy(), arr)
    assert list(df1.columns) == names, df1.columns
    nt.testing.assert_array_equal(df1.to_numpy(), arr)


def test_batch_arrow_roundtrip():
    r"""
    测试 PyArrow RecordBatch 进行 Arrow IPC 序列化与反序列化的往返过程。

    验证:
        - pa.RecordBatch 可以正确序列化为 Arrow IPC 格式
        - 反序列化后得到的是 pandas DataFrame
        - 列名、行数和列数保持一致

    Parameters:
        -
    """

    import io

    batch = pa.record_batch(
        [pa.array([1, 2, 3]), pa.array([4, 5, 6])],
        names=["a", "b"],
    )

    stream = io.BytesIO()
    dump(batch, "arrow", stream=stream)
    stream.seek(0)
    df = load(stream, "arrow", hint="table")

    assert list(df.columns) == ["a", "b"], df.columns
    assert df.shape == (3, 2), df.shape


def test_table_arrow_roundtrip():
    r"""
    测试 PyArrow Table 进行 Arrow IPC 序列化与反序列化的往返过程。

    验证:
        - pa.Table 可以正确序列化为 Arrow IPC 格式
        - 反序列化后得到的是 pandas DataFrame
        - 行数和列数保持一致

    Parameters:
        -
    """

    table = pa.table({"a": [1, 2, 3], "b": [4, 5, 6]})

    out = dump(table, "arrow")
    inp = pa.BufferReader(out.getvalue())
    df = load(inp, "arrow")

    assert df.shape == (3, 2), df.shape



if __name__ == '__main__':
    from conflog import configure_logging

    configure_logging(env="test")

    test_ndarray_arrow_tensor_roundtrip()
    test_ndarray_arrow_batch_roundtrip()
    test_tensor_arrow_roundtrip()
    test_ndarray_parquet_roundtrip()
    test_batch_arrow_roundtrip()
    test_table_arrow_roundtrip()
