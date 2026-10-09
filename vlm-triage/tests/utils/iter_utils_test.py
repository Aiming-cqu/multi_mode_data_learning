#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

from lib.utils.iter_utils import chunks


@pytest.mark.functional
def test__functional__chunks__by_max_size():
    r"""
    测试按批次数量切分迭代器。

    验证:
        - 每批元素数量不超过 max_size
        - 保持原始元素顺序

    Parameters:
        -
    """
    assert list(chunks(['a', 'b', 'c', 'd', 'e'], max_size=2)) == [
        ['a', 'b'],
        ['c', 'd'],
        ['e'],
    ]


@pytest.mark.functional
def test__functional__chunks__by_max_length():
    r"""
    测试按累计长度切分迭代器。

    验证:
        - 每批累计长度达到阈值时切分
        - 保持原始元素顺序

    Parameters:
        -
    """
    assert list(chunks(['a', 'bc', 'd', 'ef'], max_length=3)) == [['a', 'bc'], ['d', 'ef']]


@pytest.mark.functional
def test__functional__chunks__both_conditions():
    r"""
    测试同时给出数量与长度阈值时任一满足即切分。

    验证:
        - max_length 先满足时立即切分
        - 后续批次继续按规则累积

    Parameters:
        -
    """
    assert list(chunks(['aa', 'b', 'ccc'], max_size=3, max_length=3)) == [['aa', 'b'], ['ccc']]


@pytest.mark.coverage
def test__coverage__chunks__empty_iterable():
    r"""
    测试空可迭代对象返回空结果。

    验证:
        - 空输入不会抛错
        - 返回空列表

    Parameters:
        -
    """
    assert list(chunks([], max_size=2)) == []


@pytest.mark.coverage
def test__coverage__chunks__single_element():
    r"""
    测试单元素输入保持单批次输出。

    验证:
        - 单元素输入返回一个批次

    Parameters:
        -
    """
    assert list(chunks(['solo'], max_size=10)) == [['solo']]
