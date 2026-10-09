#!/usr/bin/env -S pixi run -e vllm -- test

from __future__ import absolute_import, annotations

import dataclasses as dc, typing as tp
import torch


def ensure_2d(x_nx: torch.Tensor) -> torch.Tensor:
    r"""
    将输入张量转换为二维张量，保持第一个维度不变，其余维度展平成第二维度。

    Args:
        x_nx (torch.Tensor): 输入张量。

    Returns:
        torch.Tensor: 转换后的二维张量。

    Examples:
        >>> import torch
        >>> x = torch.randn(3, 2, 4)
        >>> y = ensure_2d(x)
        >>> y.shape
        torch.Size([3, 8])
    """

    return x_nx.view(x_nx.shape[0], -1)


def torch_to(
    x: tp.Any,
    *args: tp.Union[torch.device, torch.dtype, torch.Tensor, torch.nn.Module],
    **kwds: tp.Union[torch.device, torch.dtype],
) -> tp.Any:
    r"""
    将输入对象递归地转移到指定设备或类型。

    Args:
        x (Any): 输入对象，可以是张量、模块、映射或序列。
        *args (Union[torch.device, torch.dtype, torch.Tensor, torch.nn.Module]): 目标设备或类型。
        **kwds (Union[torch.device, torch.dtype]): 目标设备或类型。

    Returns:
        Any: 转移后的对象。

    Examples:
        >>> import torch
        >>> x = torch.tensor([1, 2])
        >>> y = torch_to(x, torch.device('cpu'))
        >>> y.device.type
        'cpu'
        >>> d = {'a': torch.tensor([1]), 'b': [torch.tensor([2])]}
        >>> dd = torch_to(d, dtype=torch.float16)
        >>> dd['b'][0].dtype
        torch.float16
    """

    if isinstance(x, (torch.Tensor, torch.nn.Module)): return x.to(*args, **kwds)  # fmt: skip
    if isinstance(x, tp.Mapping): return {k: torch_to(v, *args, **kwds) for k, v in x.items()}  # fmt: skip
    if isinstance(x, tp.Sequence): return [torch_to(i, *args, **kwds) for i in x]  # fmt: skip
    raise TypeError(f'Unsupported `x` type {type(x)}')


class _TensorInspector(tp.NamedTuple):
    print_fn: tp.Callable[[str], tp.Any]
    inspected_keys: tp.Optional[set[str]] = set()  # NOTE: global shared

    def inspect(
        self,
        key: str,
        x: tp.Any,
    ):
        if self.inspected_keys is not None:
            if key in self.inspected_keys: return  # fmt: skip
            self.inspected_keys.add(key)

        if isinstance(x, torch.Tensor):
            self.print_fn(f'{key}: {x.dtype}{tuple(x.shape)}@{x.device}')
        elif isinstance(x, tp.Mapping):
            for k, v in x.items(): self.inspect(f'{key}[{k!r}]', v)  # fmt: skip
        elif isinstance(x, tp.Sequence) and not isinstance(x, (str, bytes)):
            for i, v in enumerate(x): self.inspect(f'{key}[{i}]', v)  # fmt: skip
        elif dc.is_dataclass(x):
            for f in dc.fields(x): self.inspect(f'{key}.{f.name}', getattr(x, f.name))  # fmt: skip
        elif x is None or isinstance(x, (int, float, str, bool)):
            return
        else:
            self.print_fn(f'{key}: {type(x)}')


def inspect_tensors(
    key: str,
    tensors: tp.Any,
    *,
    once: bool = False,
    print_fn: tp.Callable[[str], tp.Any] = print,
):
    r"""
    打印张量及其结构信息，支持只打印一次或递归打印。

    Args:
        key (str): 根键名。
        tensors (Any): 张量或结构体。
        once (bool): 是否只打印一次。
        print_fn (Callable[[str], Any]): 打印函数。

    Examples:
        >>> import torch
        >>> x = {'a': torch.tensor([1, 2]), 'b': [torch.tensor([3, 4])]}
        >>> inspect_tensors('root', x)
        root['a']: torch.int64(2,)@cpu
        root['b'][0]: torch.int64(2,)@cpu
    """

    if once: return _TensorInspector(print_fn).inspect(key, tensors)  # fmt: skip
    return _TensorInspector(print_fn, inspected_keys=None).inspect(key, tensors)
