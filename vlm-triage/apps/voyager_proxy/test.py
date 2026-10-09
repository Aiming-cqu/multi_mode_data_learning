#!/usr/bin/env -S pixi run -e voyager-dev -- test

from __future__ import absolute_import, annotations

from fastapi.testclient import TestClient

from lib.platforms.orion_types import TaskData, TaskResult
from lib.platforms.trail_types import IssueDetail

from main import app


client = TestClient(app)


def test_get_trail_issue_detail():
    r"""
    测试获取 Trail issue 详情 API 端点。

    验证:
        - API 返回状态码 200
        - 响应数据正确解析为 IssueDetail
        - issue id 和 trip_id 正确

    Parameters:
        -
    """

    resp = client.get('/trail/issue/cn18732285')
    assert resp.status_code == 200, resp.content
    res = IssueDetail.validate(resp.json())
    assert res.id == 'cn18732285', res
    assert res.trip_id == '17166_20250529_090920', res


def test_get_orion_task_data():
    r"""
    测试获取 Orion 任务数据 API 端点。

    验证:
        - API 返回状态码 200
        - 响应数据正确解析为 TaskData
        - 任务 ID 正确

    Parameters:
        -
    """

    resp = client.get('/orion/task_data/3084586900000056')
    assert resp.status_code == 200, resp.content
    res = resp.json()
    res["result"] = TaskResult.from_dict(res["result"])
    res = TaskData.validate(res)
    assert res.id == 3084586900000056, res
