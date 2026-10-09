#!/bin/sh
""":"
exec pixi run -e opencv -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -e opencv -- test

from __future__ import absolute_import, annotations

import pytest

import typing as tp
import numpy as np

from lib.services.cv_service import CvService

from tests.common import read_data


# 定义测试用例数据
TEST_CASES = [
    (
        '01',
        ['base-no-collision.png', 'cr-collision.png', 'feature-collision.png'],
        [False, True, True],
    ),
    (
        '02',
        ['base-no-collision.png', 'cr-collision.png', 'feature-collision.png'],
        [False, True, True],
    ),
    (
        '03',
        ['base-no-collision.png', 'cr-collision.png', 'feature-collision.png'],
        [False, True, True],
    ),
    (
        '04',
        ['base-no-collision.png', 'cr-collision.png', 'feature-collision.png'],
        [False, True, True],
    ),
    (
        '9a0684e039c7d2f407f051698f8ae914e29ff7ac',
        [
            'base-no-collision.jpg',
            'cr-01-no-collision.jpg',
            'cr-02-no-collision.jpg',
            'feature-collision.jpg',
        ],
        [False, False, False, True],
    ),
]

ALGORITHM_NAMES = ["SIFT"]


@pytest.fixture(scope="session")
def service() -> CvService:
    r"""
    Create a shared CvService instance for all tests.

    The service is lightweight as it doesn't load any models,
    so it can be reused efficiently across all tests.

    Returns:
        Configured CvService instance.
    """
    return CvService()


@pytest.mark.parametrize('group_name,image_names,gts', TEST_CASES)
def test_sift_similarity(
    service: CvService,
    group_name: str,
    image_names: tp.Sequence[str],
    gts: tp.Sequence[bool],
):
    r"""
    测试基于 SIFT 的图像相似度在碰撞检测图像上的效果。

    将第一张（基准）和最后一张（特征）图像与组内所有图像进行比较，
    验证相似度分数是否符合预期模式。
    自相似度应约为 1，特征相对于基准的比较应与真值匹配。

    验证:
        - 基准图像与自身的相似度约为 1
        - 特征图像与自身的相似度约为 1
        - 碰撞图像的特征参考相似度高于基准参考相似度

    Parameters:
        -
    """

    print(f'test group {group_name=}')
    print(f'{image_names=} {gts=}')

    images_data = read_data([f'cr_locator/images/{group_name}/{n}' for n in image_names])

    scores_nam2 = service.compute_images_similarity(
        images_data,
        algorithm_names=ALGORITHM_NAMES,
    )
    print(f'scores_nam2=\n{scores_nam2}')

    # Shape test: (num_images, num_algorithms, num_metrics, 2)
    assert scores_nam2.shape == (len(gts), len(ALGORITHM_NAMES), len(ALGORITHM_NAMES), 2), (
        scores_nam2.shape
    )

    # Self-similarity should be ~1 (perfect similarity for identical images)
    # Index [0, 0, 0, 0]: base image vs base reference
    # Index [-1, 0, 0, 1]: feature image vs feature reference
    b2b_score = scores_nam2[0, 0, 0, 0]
    np.testing.assert_allclose(b2b_score, 1, atol=0.1)
    f2f_score = scores_nam2[-1, 0, 0, 1]
    np.testing.assert_allclose(f2f_score, 1, atol=0.1)

    # For collision images, feature reference should give higher similarities
    # (more similar) than base reference, since collision images are closer to
    # feature image than base image.
    # scores_nam2[..., 0]: base reference similarities
    # scores_nam2[..., 1]: feature reference similarities
    fob_n = scores_nam2[..., 0] < scores_nam2[..., 1]
    print(f'fob_n=\n{fob_n}')
    gt_n = np.array(gts)[..., np.newaxis, np.newaxis]
    assert (fob_n == gt_n).all(), fob_n
