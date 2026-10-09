#!/bin/sh
""":"
exec pixi run -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

import pandas as pf

from lib.algorithms.cr_locate import (
    SingleCRLocated,
    get_fob_and_outliers,
    locate_cr_by_variance_minimization,
    locate_cr_by_voting,
)

from tests.common import TEST_DATA_DIR


@pytest.mark.parametrize(
    'cr_metric_path,gt',
    [
        ('cr_locator_4590613_converted.csv', 19),
    ],
)
def test_locate_cr(cr_metric_path: str, gt: int):
    r"""
    测试通过投票机制定位 CR。

    从包含多个 CR 的 embedding 指标的 CSV 文件中加载测试数据，
    提取谓词和异常值，并验证投票算法是否正确识别预期的 CR。

    验证:
        - 投票算法正确识别 CR 索引
        - 识别结果与预期值一致

    Parameters:
        -
    """

    print(f'test {cr_metric_path=}')

    cr_metric_f = pf.read_csv(
        TEST_DATA_DIR / f'cr_locator/{cr_metric_path}',
        header=list(range(5)),
        index_col=0,
    )

    predicate_f, outlier_f, predicate_d = get_fob_and_outliers(cr_metric_f)
    print(f'predicate_f=\n{predicate_f}')
    print(f'outlier_f=\n{outlier_f}')
    res = locate_cr_by_voting(predicate_f, outlier_f)
    print(f'{res=}')
    predicate_diff_mean = predicate_d.mean(axis=1)
    variance_res = locate_cr_by_variance_minimization(predicate_diff_mean)
    print(f'{variance_res=}')


    assert isinstance(res, SingleCRLocated), type(res)
    assert res.crs[0] == gt, res
