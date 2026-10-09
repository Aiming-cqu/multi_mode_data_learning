#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

from lib.utils.containers import CacheDict


@pytest.mark.functional
def test__functional__cache_dict__lru():
    r"""
    测试读取命中会将键移动到 LRU 尾部。

    验证:
        - __getitem__ 后被访问键移动到末尾

    Parameters:
        -
    """
    cache = CacheDict[str, int](max_size=3)
    cache['a'] = 1
    cache['b'] = 2
    cache['c'] = 3

    assert cache['a'] == 1
    assert list(cache.keys()) == ['b', 'c', 'a']


@pytest.mark.coverage
def test__coverage__cache_dict__eviction():
    r"""
    测试 mayevict 会弹出最旧元素。

    验证:
        - 容量达到上限时返回并删除最早元素

    Parameters:
        -
    """
    cache = CacheDict[str, int](max_size=2)
    cache['a'] = 1
    cache['b'] = 2

    assert cache.mayevict() == ('a', 1)
    assert list(cache.items()) == [('b', 2)]


@pytest.mark.coverage
def test__coverage__cache_dict__mayevict():
    r"""
    测试未达到容量上限时 mayevict 返回 None。

    验证:
        - 小于最大容量时不触发淘汰

    Parameters:
        -
    """
    cache = CacheDict[str, int](max_size=2)
    cache['a'] = 1

    assert cache.mayevict() is None
