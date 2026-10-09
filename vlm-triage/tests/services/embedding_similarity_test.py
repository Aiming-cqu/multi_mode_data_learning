#!/bin/sh
""":"
exec pixi run -e vllm -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -e vllm -- test

from __future__ import absolute_import, annotations

import pytest

import typing as tp
import torch

from lib.services.embedding_service import EmbeddingService, EmbeddingExtractorLoader

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

MODEL_IDS = [
    'AI-ModelScope/clip-vit-large-patch14',
    'apple/aimv2-huge-patch14-448',
    'facebook/dinov2-base',
    'facebook/dinov2-large',
    'google/siglip-base-patch16-224',
    'google/siglip-so400m-patch14-384',
    'google/siglip2-base-patch16-224',
    'google/siglip2-so400m-patch16-512',
    'Salesforce/blip2-opt-2.7b',
]
METRIC_NAMES = ["Cosine", "L2"]


@pytest.fixture(scope="session")
def service() -> EmbeddingService:
    r"""
    Create a shared EmbeddingService instance for all tests.

    The service is expensive to create because it loads multiple models,
    so it's reused across all tests in the session.

    Returns:
        Configured EmbeddingService instance.
    """
    return EmbeddingService(EmbeddingExtractorLoader())


@pytest.mark.parametrize('group_name,image_names,gts', TEST_CASES)
def test_embedding_similarity(
    service: EmbeddingService,
    group_name: str,
    image_names: tp.Sequence[str],
    gts: tp.Sequence[bool],
):
    r"""
    测试图像对的 embedding 相似度计算。

    验证 embedding 服务是否正确计算组内不同图像之间的相似度。
    检查相似度矩阵的形状、自相似度值以及特征相对于基准的比较。

    验证:
        - 相似度矩阵形状正确
        - 基准与基准、特征与特征的相似度为 1
        - 特征相对于基准的比较与真值匹配

    Parameters:
        -
    """

    print(f'test group {group_name=}')
    print(f'{image_names=} {gts=}')

    images_data = read_data([f'cr_locator/images/{group_name}/{n}' for n in image_names])

    s_nms2 = service.compute_images_similarity(
        images_data,
        MODEL_IDS,
        metric_names=METRIC_NAMES,
        text='',
    )
    print(f's_nms2=\n{s_nms2}')

    # shape test
    assert s_nms2.shape == (len(gts), len(MODEL_IDS), len(METRIC_NAMES), 2), s_nms2.shape

    # base to base, feature to feature should be 1
    b2b_ms = s_nms2[0, ..., 0]
    torch.testing.assert_allclose(b2b_ms, torch.full_like(b2b_ms, 1))
    f2f_ms = s_nms2[-1, ..., 1]
    torch.testing.assert_allclose(f2f_ms, torch.full_like(f2f_ms, 1))

    # feature over base should be [False, True, True]
    fob_nms = s_nms2[..., 0] < s_nms2[..., 1]
    print(f'fob_nms=\n{fob_nms}')
    gt_nms = torch.tensor(gts)[..., torch.newaxis, torch.newaxis]
    assert (fob_nms == gt_nms).all(), fob_nms
