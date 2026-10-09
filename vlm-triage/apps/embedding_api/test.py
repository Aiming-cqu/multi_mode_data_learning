#!/bin/sh
""":"
exec pixi run -e vllm -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -e vllm -- test

from __future__ import absolute_import, annotations

import pytest

import io
import PIL.Image

from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from main import app


VL_MODEL_IDS: list[str] = [
    'Qwen/Qwen3-VL-Embedding-8B',
]

client = TestClient(app)


def get_image_files():
    r"""
    生成测试图像文件。

    创建不同颜色的简单测试图像，
    用于测试图像 embedding 和相似度计算。

    Parameters:
        -
    """

    colors = ["red", "yellow", "green"]

    files = []
    for color in colors:
        image = PIL.Image.new("RGB", (224, 224), color=color)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        files.append(('image_files', buf.getvalue()))
    return files


@pytest.mark.smoke
def test__smoke__embed():
    r"""
    冒烟测试：/embed 端点默认参数通断。

    验证:
        - 使用默认 model_ids 和 fmt
        - API 返回状态码 200

    Parameters:
        -
    """

    files = get_image_files()
    resp = client.post('/embed', files=files)
    assert resp.status_code == 200, resp.content


@pytest.mark.functional
@pytest.mark.resource
def test_embed_images_vl():
    r"""
    测试图像 embedding API 端点。

    验证:
        - 成功提取图像 embedding
        - API 返回状态码 200

    Parameters:
        -
    """

    files = get_image_files()
    resp = client.post(
        '/embed',
        files=files,
        params={"model_ids": VL_MODEL_IDS, "text": 'box'},
    )
    assert resp.status_code == 200, resp.content


@pytest.mark.stress
def test_embed_images_concurrent():
    r"""
    测试图像 embedding API 的并发请求处理。

    验证:
        - 使用线程池并发发送多个请求
        - 所有请求返回状态码 200

    Parameters:
        -
    """

    files = get_image_files()

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(
            lambda _: client.post('/embed', files=files),
            range(100),
        )

    for i, resp in enumerate(results):
        assert resp.status_code == 200, f"Request {i} failed: {resp.content}"


@pytest.mark.smoke
def test__smoke__compute_similarity():
    r"""
    冒烟测试：/compute_similarity 端点默认参数通断。

    验证:
        - 使用默认 model_ids 和 metric_names
        - API 返回状态码 200

    Parameters:
        -
    """

    files = get_image_files()
    resp = client.post('/compute_similarity', files=files)
    assert resp.status_code == 200, resp.content


@pytest.mark.functional
@pytest.mark.resource
def test_compute_images_similarity_vl():
    r"""
    测试图像相似度计算 API 端点。

    验证:
        - 成功计算图像相似度
        - API 返回状态码 200

    Parameters:
        -
    """

    files = get_image_files()
    resp = client.post(
        '/compute_similarity',
        files=files,
        params={"model_ids": VL_MODEL_IDS, "text": 'box'},
    )
    assert resp.status_code == 200, resp.content


@pytest.mark.stress
def test_compute_images_similarity_concurrent():
    r"""
    测试图像相似度 API 的并发请求处理。

    验证:
        - 使用线程池并发发送多个请求
        - 所有请求返回状态码 200

    Parameters:
        -
    """

    files = get_image_files()

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(
            lambda _: client.post('/compute_similarity', files=files),
            range(100),
        )

    for i, resp in enumerate(results):
        assert resp.status_code == 200, f"Request {i} failed: {resp.content}"
