#!/bin/sh
""":"
exec pixi run -e vllm -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -e vllm -- test

from __future__ import absolute_import, annotations

import pytest

import io, PIL.Image

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def get_image_files():
    colors = ["red", "yellow", "green"]
    files = []
    for color in colors:
        image = PIL.Image.new("RGB", (224, 224), color=color)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        files.append(('image_files', buf.getvalue()))
    return files


@pytest.mark.resource
def test_embed_vl_with_resource_monitor(resource_monitor):
    r"""测试 resource_monitor 对真实 VL 模型加载的监控效果。

    验证:
        - 资源监控 fixture 正常运行不干扰测试逻辑
        - API 返回状态码 200

    Parameters:
        -
    """
    files = get_image_files()
    resp = client.post(
        '/embed',
        files=files,
        params={
            "model_ids": ['Qwen/Qwen3-VL-Embedding-8B'],
            "text": 'box',
        },
    )
    assert resp.status_code == 200, resp.content
