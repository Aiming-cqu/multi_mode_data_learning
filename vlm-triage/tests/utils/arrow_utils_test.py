#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import io
import pytest
import numpy as nt

from lib.utils.arrow_utils import dump, load


@pytest.mark.coverage
def test_dump_invalid_format():
    r"""不支持的格式 → ValueError。"""
    with pytest.raises(ValueError):
        dump(nt.zeros((2, 2)), "invalid")


@pytest.mark.coverage
def test_dump_parquet_requires_names():
    r"""Parquet 缺 names → ValueError。"""
    with pytest.raises(ValueError):
        dump(nt.zeros((2, 2)), "parquet")


@pytest.mark.coverage
def test_load_invalid_format():
    r"""load 不支持的格式 → ValueError。"""
    with pytest.raises(ValueError):
        load(io.BytesIO(), "invalid")
