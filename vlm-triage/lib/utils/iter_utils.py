#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import typing as tp


_T = tp.TypeVar('_T')  # Any type
_TS = tp.TypeVar('_TS', bound=tp.Sized)  # Sized type


@tp.overload
def chunks(
    iterable: tp.Iterable[_T],
    *,
    max_size: int,
    max_length: tp.Literal[0] = 0,
) -> tp.Generator[tp.Sequence[_T], None, None]:
    r"""
    将可迭代对象按指定的批次数量切分为多个批次。
    """
    ...


@tp.overload
def chunks(
    iterable: tp.Iterable[_TS],
    *,
    max_size: tp.Literal[0] = 0,
    max_length: int,
) -> tp.Generator[tp.Sequence[_TS], None, None]:
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

def chunks(
    iterable: tp.Iterable[_T],
    *,
    max_size: int = 0,
    max_length: int = 0,
) -> tp.Generator[tp.Sequence[_T], None, None]:
    r"""
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

    Examples:
        >>> list(chunks(['a', 'bc', 'def', 'gh'], max_size=3))
        [['a', 'bc', 'def'], ['gh']]

        >>> list(chunks(['a', 'bc', 'def', 'gh'], max_length=3))
        [['a', 'bc'], ['def'], ['gh']]
    """

    if not (max_size > 0 or max_length > 0):
        raise ValueError('either `max_size` or `max_length` should be specified')

    batch = list[_T]()
    cum_size: int = 0
    cum_length: int = 0
    for item in iterable:
        batch.append(item)

        flag: bool = False
        if max_size > 0:
            cum_size += 1
            flag |= cum_size >= max_size
        if max_length > 0:
            cum_length += len(tp.cast(tp.Sized, item))
            flag |= cum_length >= max_length

        if flag:
            yield batch
            batch = []
            cum_size = 0
            cum_length = 0

    if len(batch) > 0:
        yield batch
