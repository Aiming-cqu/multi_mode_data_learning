#!/bin/sh
""":"
exec pixi run -e opencv -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -e opencv -- test

from __future__ import absolute_import, annotations

import cv2
import numpy as np

from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def get_image_files():
    r"""
    生成用于 SIFT 特征检测的测试图像。

    创建带有渐变模式和几何形状的彩色测试图像，
    用于测试 SIFT 特征检测和相似度计算。

    Parameters:
        -
    """

    files = []
    for color_name, bgr in (
        ("red", (0, 0, 255)),
        ("yellow", (0, 255, 255)),
        ("green", (0, 255, 0)),
    ):
        # Create image with gradient pattern for SIFT features
        img = np.zeros((224, 224, 3), dtype=np.uint8)
        # Add gradient pattern
        for j in range(224):
            intensity = int(255 * j / 224)
            img[j, :, :] = [min(c + intensity // 4, 255) for c in bgr]
        # Add some corners/edges for SIFT detection
        cv2.rectangle(img, (50, 50), (100, 100), (255, 255, 255), -1)
        cv2.circle(img, (150, 150), 30, (0, 0, 0), -1)

        # Encode to PNG bytes
        success, buf = cv2.imencode(".png", img)
        assert success, "Failed to encode image"
        files.append(("image_files", buf.tobytes()))
    return files


def test_compute_images_similarity():
    r"""
    测试 CV 相似度计算 API 端点。

    验证:
        - 使用 SIFT 算法计算图像相似度
        - API 返回状态码 200

    Parameters:
        -
    """

    files = get_image_files()
    resp = client.post('/compute_similarity', files=files, params={"fmt": "safetensors"})
    assert resp.status_code == 200, resp.content


def test_compute_images_similarity_concurrent():
    r"""
    测试 CV 相似度 API 的并发请求处理。

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
