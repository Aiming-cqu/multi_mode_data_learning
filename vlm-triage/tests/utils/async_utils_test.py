#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

from lib.utils.async_utils import async_run


@pytest.mark.functional
async def test__functional__async_run__sync_func():
    r"""
    测试 async_run 可在异步上下文执行同步函数。

    验证:
        - 默认执行路径返回同步函数结果

    Parameters:
        -
    """

    def add(x: int, y: int) -> int:
        return x + y

    assert await async_run(add, 10, 20) == 30


@pytest.mark.coverage
async def test__coverage__async_run__exception():
    r"""
    测试 async_run 不会吞掉同步函数异常。

    验证:
        - 同步函数抛出的异常会传播给调用方

    Parameters:
        -
    """

    def fail() -> None:
        raise ValueError('boom')

    with pytest.raises(ValueError, match='boom'):
        await async_run(fail, run_in_executor=False)
