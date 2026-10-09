#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

import re

from lib.utils.s3_utils import prepend_object_partition


@pytest.mark.functional
def test__functional__prepend_object_partition():
    r"""
    测试 S3 对象名会拼接前缀、应用名和日期分区。

    验证:
        - 非空 prefix 会保留并补齐分隔符
        - 结果路径包含 8 位日期分区

    Parameters:
        -
    """
    result = prepend_object_partition('artifact.txt', app_name='triage-app', prefix='runs')

    assert re.fullmatch(r'runs/triage-app/\d{8}/artifact.txt', result)


@pytest.mark.coverage
def test__coverage__prepend_object_partition__empty_prefix():
    r"""
    测试空 prefix 时不会产生多余的路径分隔符。

    验证:
        - 空 prefix 会直接从 app_name 开始拼接
        - 结果路径包含 8 位日期分区

    Parameters:
        -
    """
    result = prepend_object_partition('artifact.txt', app_name='triage-app', prefix='')

    assert re.fullmatch(r'triage-app/\d{8}/artifact.txt', result)
