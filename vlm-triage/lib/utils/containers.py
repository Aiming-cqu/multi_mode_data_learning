#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import typing as tp

from collections import OrderedDict


_K = tp.TypeVar('_K', bound=tp.Hashable)  # Key type
_V = tp.TypeVar('_V')  # Value type


class CacheDict(OrderedDict[_K, _V]):
    r"""
    OrderedDict for LRU.
    """

    def __init__(self, *, max_size: int):
        super().__init__()
        self.max_size: int = max_size

    def __getitem__(self, key: _K) -> _V:
        value: _V = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key: _K, value: _V):
        super().__setitem__(key, value)
        self.move_to_end(key)

    def mayevict(self) -> tp.Optional[tuple[_K, _V]]:
        if len(self) >= self.max_size: return self.popitem(last=False)  # fmt: skip
