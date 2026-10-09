#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

from lib.utils.dpe_helper import normalize_dpe_output


@pytest.mark.functional
def test__functional__normalize_dpe_output():
    r"""
    测试 DPE 输出标准化与过滤逻辑。

    验证:
        - metrics 按名称过滤并排序
        - events 仅保留目标指标并按时间排序
        - start_time_ms 会对较晚事件做相对时间归一化

    Parameters:
        -
    """
    output = {
        'results': {
            'collision': {'val': 0.01},
            'safety_score': {'val': 0.95},
        },
        'events': [
            {'event_key': 'collision', 'timestamp': 5000},
            {'event_key': 'safety_score', 'timestamp': 1000},
            {'event_key': 'collision', 'timestamp': 3144},
        ],
    }

    metric_s, event_f = normalize_dpe_output(
        output,
        metric_names=['collision'],
        start_time_ms=2000,
    )

    assert metric_s.to_dict() == {'collision': 0.01}
    assert event_f.to_dict(orient='records') == [
        {'event': 'collision', 'timestamp': 1144},
        {'event': 'collision', 'timestamp': 3000},
    ]
