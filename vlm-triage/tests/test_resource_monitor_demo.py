#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import pytest

import time


@pytest.mark.resource
def test_heavy_simulated(resource_monitor):
    r"""验证 resource_monitor 能正确捕获内存和耗时。"""
    data = [bytearray(50 * 1024 * 1024) for _ in range(10)]  # 500 MB
    time.sleep(0.3)
    del data
    assert True


def test_no_marker_without_fixture():
    r"""没有 @pytest.mark.resource 的不应依赖 resource_monitor。"""
    assert True
