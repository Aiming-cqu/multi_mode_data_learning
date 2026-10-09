#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import typing as tp
import pandas as pf

from operator import itemgetter


def normalize_dpe_output(
    output: tp.Mapping[str, tp.Any],
    *,
    metric_names: tp.Optional[tp.Collection[str]] = None,
    start_time_ms: tp.Optional[int] = None,
) -> tuple[pf.Series, pf.DataFrame]:
    r"""
    Normalize DPE output to a Series of metrics and a DataFrame of events.

    Examples:
        >>> dpe_output = {
        ...     "results": {"collision": {"val": 0.01}, "safety_score": {"val": 0.95}},
        ...     "events": [
        ...         {"event_key": "collision", "timestamp": 5000},
        ...         {"event_key": "collision", "timestamp": 3144},
        ...     ],
        ... }
        >>> metric_s, event_f = normalize_dpe_output(
        ...     dpe_output,
        ...     metric_names=['collision'],
        ...     start_time_ms=1000,
        ... )
        >>> metric_s
        metric
        collision    0.01
        Name: value, dtype: object
        >>> event_f
               event  timestamp
        0  collision       2144
        1  collision       4000
    """

    series = pf.Series(data={k: v["val"] for k, v in output["results"].items()}, dtype="object")  # type: Series[Union[int, float]]
    series.index.name = "metric"
    series.name = "value"

    keys: list[str] = ["event_key", "timestamp"]
    df = pf.DataFrame.from_records(list(map(itemgetter(*keys), output["events"])), columns=keys)
    df = df.rename(columns={"event_key": "event", "timestamp": "timestamp"})

    if metric_names is not None:
        series = series[list(metric_names)]
        df = df.loc[df["event"].isin(metric_names)]

    if start_time_ms is not None:
        df["timestamp"] = df.timestamp.mask(
            df.timestamp > start_time_ms,
            other=(df.timestamp - start_time_ms),
        )

    return (series.sort_index(), df.sort_values(["timestamp"]).reset_index(drop=True))
