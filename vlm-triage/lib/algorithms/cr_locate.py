#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import dataclasses as dc, logging, typing as tp
import pandas as pf
import numpy as np
from itertools import combinations


logger: logging.Logger = logging.getLogger(name=__name__)


@dc.dataclass(slots=True)
class CRLocateResult:
    crs: tp.Sequence[tp.Hashable] = dc.field(
        metadata={'doc': 'CR 定位结果，重要性从高到低'},
    )
    scores_by_cr: tp.Mapping[tp.Hashable, int] = dc.field(
        default_factory=dict,
        metadata={'doc': '每个 CR 的支持度分数（可选）'},
    )
    threshold: tp.Optional[float] = dc.field(
        default=None,
        metadata={'doc': '定位阈值（可选）'},
    )
    message: str = dc.field(
        default='',
        kw_only=True,
        metadata={'doc': '补充说明'},
    )  # kw_only: support inheritance


@dc.dataclass(slots=True)
class ZeroCRLocated(CRLocateResult):
    crs: tp.Sequence[tp.Hashable] = dc.field(
        default_factory=list,
        metadata={'doc': 'CR 定位结果，重要性从高到低'},
    )


@dc.dataclass(slots=True)
class SingleCRLocated(CRLocateResult):
    pass


@dc.dataclass(slots=True)
class MultiCRLocated(CRLocateResult):
    pass


def get_fob_and_outliers(
    cr_metric_f: pf.DataFrame,
) -> tuple[pf.DataFrame, pf.DataFrame]:
    r"""
    Extract FoB(Feature-over-Base) and outlier dataframes from CR metrics.
    """
    sb_f = cr_metric_f.xs("base", axis="columns", level="end")
    sf_f = cr_metric_f.xs("feature", axis="columns", level="end")
    s_e2e_s = sf_f.iloc[0]
    fob_f = sf_f.iloc[1:-1] - sb_f.iloc[1:-1]
    logger.debug('fob_f:\n%s', fob_f.to_csv(sep='\t'))
    outlier_f = (sb_f.iloc[1:-1] < s_e2e_s) & (sf_f.iloc[1:-1] < s_e2e_s)
    logger.debug('outlier_f:\n%s', outlier_f.to_csv(sep='\t'))
    return (fob_f, outlier_f)


def locate_cr_by_voting(
    fob_f: pf.DataFrame,
    outlier_f: pf.DataFrame,
    total_outlier_ratio_threshold: float = 0.7,
    loc_support_ratio_threshold: float = 0.4,
    loc_outlier_ratio_threshold: float = 0.8,
) -> CRLocateResult:
    r"""
    Locate CR by voting mechanism on FoB and outlier data.

    Uses a voting-based approach to identify the most likely CR
    location by analyzing FoB scores and outlier patterns across
    simulation frames.

    Returns:
        The identified CR location (typically an index value).

    Raises:
        TooManyOutliersError: If total_outlier_ratio exceeds threshold.
        AmbiguousSupportError: If loc_support_ratio is below threshold.
        InsufficientSupportError: If loc_outlier_ratio exceeds threshold.
    """
    total_outlier_ratio: float = (outlier_f.sum().sum() / outlier_f.notna().sum().sum()).item()
    logger.info('total_outlier_ratio=%.2f', total_outlier_ratio)
    if total_outlier_ratio > total_outlier_ratio_threshold:
        return ZeroCRLocated(
            threshold=total_outlier_ratio_threshold,
            message=(
                'CRs may not match either ends'
                f': total outlier ratio {total_outlier_ratio:.2f} exceeds threshold'
            ),
        )

    nn_f = fob_f.le(0).astype("Int32")
    np_f = fob_f.gt(0).astype("Int32")
    sn_f = nn_f.cumsum().shift(fill_value=0)
    sp_f = np_f.loc[::-1].cumsum()
    cut_score_f = sn_f + sp_f
    logger.debug('cut_score_f:\n%s', cut_score_f.to_csv(sep='\t'))

    cut_loc_s = cut_score_f.iloc[::-1].idxmax()  # NOTE: argmax: latest first
    cut_vote_s = cut_loc_s.sort_values().iloc[::-1].value_counts()  # NOTE: vote: latest first
    logger.info('cr_votes:\n%s', cut_vote_s.to_csv(sep='\t'))
    cut_score_s = cut_vote_s / len(cut_loc_s)
    series = cut_score_s.cumsum().shift(fill_value=0)
    cut_score_s = cut_score_s.loc[series < loc_support_ratio_threshold]
    logger.info('cut_scores:\n%s', cut_score_s.to_csv(sep='\t'))

    if len(cut_score_s) > 1:
        return MultiCRLocated(
            crs=cut_score_s.index.tolist(),
            scores_by_cr=cut_score_s.to_dict(),
            threshold=loc_support_ratio_threshold,
        )

    loc = cut_vote_s.index[0]
    loc_outlier_ratio: float = outlier_f.loc[loc].mean().item()
    logger.info('loc_outlier_ratio=%.2f', loc_outlier_ratio)
    message: str = ''
    if loc_outlier_ratio > loc_outlier_ratio_threshold:
        return SingleCRLocated(
            crs=[loc],
            scores_by_cr={loc: cut_score_s.iloc[0].item()},
            threshold=loc_outlier_ratio_threshold,
            message=(
                'Weak single CR located'
                f': with high outlier ratio {loc_outlier_ratio:.2f} exceeds threshold'
            ),
        )

    return SingleCRLocated(
        crs=[loc],
        scores_by_cr={loc: cut_score_s.iloc[0].item()},
        threshold=loc_support_ratio_threshold,
        message=message,
    )


def segment_variance(values: np.ndarray, start: int, end: int) -> float:
    """计算区间 [start, end) 内的方差和（L2 cost）"""
    segment = values[start:end]
    if len(segment) == 0:
        return 0.0
    return segment.var()


def _find_best_changepoints(
    values: np.ndarray, indices: np.ndarray, min_size: int = 2
) -> dict[int, dict[str, tp.Any]]:
    """找到不同拐点数量下的最优解，并计算各拐点的个体贡献度"""
    n, best_results = len(values), {}
    total_variance = float(np.sum((values - np.mean(values)) ** 2))

    for n_bkps in range(1, 4):
        best_cost, best_bkps = float('inf'), None
        for bkps in combinations(range(min_size, n - min_size), n_bkps):
            if bkps[-1] <= n - min_size:
                segments = (
                    [(0, bkps[0])]
                    + [(bkps[i], bkps[i + 1]) for i in range(n_bkps - 1)]
                    + [(bkps[-1], n)]
                )
                if all(end - start >= min_size for start, end in segments):
                    cost = sum(segment_variance(values, s, e) for s, e in segments)
                    if cost < best_cost:
                        best_cost, best_bkps = cost, bkps

        if best_bkps:
            # 计算每个拐点的个体贡献度（单独存在时的方差减少量）
            individual_contributions = {}
            best_cp_indices = indices[list(best_bkps)]

            for cp in best_cp_indices:
                # 找到该拐点在原始数据中的位置
                cp_pos = np.where(indices == cp)[0][0]
                # 计算只有这个拐点时的方差
                left_var = segment_variance(values, 0, cp_pos)
                right_var = segment_variance(values, cp_pos, len(values))
                single_cp_variance = left_var + right_var
                # 贡献度 = (总方差 - 单拐点方差) / 总方差 * 100，保留两位小数
                contribution = round(
                    (total_variance - single_cp_variance) / total_variance * 100, 2
                )
                individual_contributions[cp] = contribution

            best_results[n_bkps] = {
                'cp': best_cp_indices,
                'cost': best_cost,
                'individual_contributions': individual_contributions,
            }

    return best_results


def _select_optimal_n_breaks(variances: list[float]) -> int:
    """使用肘部法则选择最优拐点数量"""
    if len(variances) <= 1:
        return 0

    # 计算边际收益（最多3个拐点）
    marginal_gains = [variances[i - 1] - variances[i] for i in range(1, min(len(variances), 4))]
    if not marginal_gains or marginal_gains[0] < variances[0] * 0.3:
        return 0

    # 找到收益显著下降的点
    for i in range(1, len(marginal_gains)):
        if marginal_gains[i] < marginal_gains[i - 1] * 0.08:
            return i

    return min(len(marginal_gains), 3)


def locate_cr_by_variance_minimization(cr_changes: pf.Series, min_size: int = 2) -> CRLocateResult:
    """
    基于方差最小化的拐点检测算法

    该算法通过暴力搜索所有可能的拐点组合，找到使分段方差最小的最优解，
    并使用肘部法则自动确定最优拐点数量。

    Args:
        cr_changes: Series，索引为 cr_index，值为 change_mean
        min_size: 每个分段的最小长度

    Returns:
        CRLocateResult 包含检测到的拐点位置
    """
    # 过滤有效数据
    valid_mask = ~np.isnan(cr_changes.values)
    values = cr_changes.values[valid_mask]
    indices = cr_changes.index.values[valid_mask]

    # if len(values) < 4:
    #     logger.info('有效数据点太少 (<4)，跳过拐点检测')
    #     return ZeroCRLocated(message='Insufficient data points for changepoint detection')

    # 找到最优拐点组合
    results = _find_best_changepoints(values, indices, min_size=min_size)

    # 计算方差序列用于肘部法则
    var_0 = float(np.sum((values - np.mean(values)) ** 2))
    variances = [var_0]

    for n_bkps in [1, 2, 3]:
        variances.append(results[n_bkps]['cost'] if n_bkps in results else variances[-1])

    best_n = _select_optimal_n_breaks(variances)

    if best_n == 0:
        logger.info('肘部法则选择 0 个拐点 (方差变化不显著)')
        return ZeroCRLocated(
            message='No significant changepoints detected by elbow method', threshold=var_0
        )
    else:
        best_cp = results[best_n]['cp']
        best_cost = results[best_n]['cost']
        reduction = (var_0 - best_cost) / var_0
        logger.info(
            f'肘部法则选择 {best_n} 个拐点: {best_cp.tolist()}, 总方差减少: {reduction:.2%}'
        )

        if len(best_cp) == 1:
            return SingleCRLocated(
                crs=[best_cp[0]],
                scores_by_cr={best_cp[0]: reduction},
                threshold=best_n,
                message=f'Detected single changepoint with {reduction:.2%} variance reduction',
            )
        else:
            # 使用预计算的个体贡献度
            individual_contributions = results[best_n]['individual_contributions']
            # 按贡献度从大到小排序
            sorted_cps = sorted(
                individual_contributions.keys(),
                key=lambda x: individual_contributions[x],
                reverse=True,
            )

            return MultiCRLocated(
                crs=sorted_cps,
                scores_by_cr=individual_contributions,
                threshold=best_n,
                message=f'Detected {len(best_cp)} changepoints with {reduction:.2%} variance reduction',
            )
