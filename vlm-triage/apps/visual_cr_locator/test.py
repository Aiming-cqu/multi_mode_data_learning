#!/bin/sh
""":"
exec pixi run -- test -s "$0" "$@"
"""
#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import time

from fastapi.testclient import TestClient

from api import AnnotationInfo, LocatorResponse, app


client = TestClient(app)


def test_locate_sync():
    r"""
    测试同步 CR 定位 API 端点。

    验证:
        - API 返回状态码 200
        - 响应状态为 success
        - CR 定位结果正确

    Parameters:
        -
    """

    resp = client.post('/locate', params={"locator_id": 4391943})
    assert resp.status_code == 200, resp.content
    res = LocatorResponse.model_validate(resp.json())
    assert res.status == "success", res
    res = res.result
    assert res
    assert sorted(res) == ['10349_20260131_161655;1769847693917;1769847710567'], res
    cr = res['10349_20260131_161655;1769847693917;1769847710567']
    assert cr
    assert cr.cr_index == 19, cr
    assert cr.commit.task_id.id == 3567557100000039, cr


def test_locate_async():
    r"""
    测试异步 CR 定位 API 端点。

    验证:
        - 多个 locator_id 成功提交异步任务
        - 轮询获取结果返回状态码 200
        - 所有任务最终返回 success 状态

    Parameters:
        -
    """

    locator_ids = [
        4662583,
        4662595,
        4662619,
        4666427,
        4667803,
        4674461,
        4674467,
        4678899,
        4679163,
    ]
    tickets = [
        client.post('/locate/async', params={"locator_id": i}).json() for i in locator_ids
    ]
    while tickets:
        for ticket in tickets:
            resp = client.get(f'/locate/async/{ticket}')
            assert resp.status_code == 200, resp.content
            res = LocatorResponse.model_validate(resp.json())
            assert res.status == "success", res
            res = res.result
            assert res
        time.sleep(1)


def test_annotation_info():
    r"""
    测试获取标注信息的 API 端点。

    验证:
        - API 返回状态码 200
        - 响应包含有效的 AnnotationInfo 数据

    Parameters:
        -
    """

    resp = client.post('/annotation', params={"locator_id": 4391943})
    assert resp.status_code == 200, resp.content
    res = AnnotationInfo.model_validate(resp.json())
    assert res
