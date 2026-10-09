#!/usr/bin/env -S pixi run -- test

r"""
最大覆盖问题求解模块。

使用动态规划解决在一维有序点集上的最大覆盖问题，
选择最多 n 个长度不超过 w 的区间，覆盖尽可能多的点。

Attributes:
    -
"""

from __future__ import absolute_import, annotations

import typing as tp


_TN = tp.TypeVar('_TN', int, float)  # Number type


def max_coverage(xs: tp.Sequence[_TN], n: int, w: _TN) -> list[tuple[int, int]]:
    r"""
    Solve the maximum coverage problem using dynamic programming.

    Given a **sorted** sequence of points, selects up to ``n`` intervals of maximum
    length ``w`` to cover as many points as possible. Uses DP with O(n*m) complexity
    where m is the number of points.

    Args:
        xs: A **sorted** sequence of **numeric values (ascending order)**.
        n: Maximum number of intervals to select.
        w: Maximum length of each interval.

    Returns:
        A list of ``(start_index, end_index)`` tuples representing the selected
            intervals (inclusive indices). Intervals are sorted by start index.

    Examples:
        >>> max_coverage([1, 2, 4, 5, 6, 9], 2, 2)
        [(0, 1), (2, 4)]

        >>> max_coverage([1, 1, 1], 3, 1)
        [(0, 2)]

        >>> max_coverage([1, 1, 3], 3, 1)
        [(0, 1), (2, 2)]

        >>> xs = [13750, 13750, 13750, 13750, 13750, 13750, 13750, 14150,
        ...       14150, 14150, 14150, 14150, 14150, 14150, 17550, 17550]
        >>> rs = max_coverage(xs, 3, 1510)
        >>> rs
        [(0, 13), (14, 15)]
        >>> [(xs[r[0]], xs[r[1]]) for r in rs]
        [(13750, 14150), (17550, 17550)]
    """

    m = len(xs)

    # prepare left bound for each right bound
    ls = [0] * m
    l = 0
    for r in range(m):
        while xs[l] + w < xs[r]: l += 1  # fmt:skip
        ls[r] = l

    # dp[i][r]: max coverage with i intervals and right bound <= r
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for r in range(1, m + 1):
            l = ls[r - 1]
            dp[i][r] = max(dp[i][r - 1], dp[i - 1][l] + r - l)

    # traceback results
    rs = []
    r = m
    for i in range(n, 0, -1):
        if r == 0: break  # fmt:skip
        while dp[i][r] == dp[i][r - 1]: r -= 1  # fmt:skip
        r -= 1
        l = ls[r]
        rs.append((l, r))
        r = l
    return rs[::-1]


if __name__ == '__main__':
    print(max_coverage([1, 2, 4, 5, 6, 9], 2, 2))
    print(max_coverage([1, 1, 1], 3, 1))
    print(max_coverage([1, 1, 3], 3, 1))
    xs = [13750, 13750, 13750, 13750, 13750, 13750, 13750, 14150, 14150, 14150, 14150, 14150, 14150, 14150, 17550, 17550]
    rs = max_coverage(xs, 3, 1510)
    print(rs)
    print([(xs[r[0]], xs[r[1]]) for r in rs])
