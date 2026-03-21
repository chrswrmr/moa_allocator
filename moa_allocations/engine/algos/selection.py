from __future__ import annotations

import math

from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.algos.metrics import compute_metric
from moa_allocations.engine.node import StrategyNode


class SelectAll(BaseAlgo):
    def __call__(self, target: StrategyNode) -> bool:
        target.temp["selected"] = [child.id for child in target.children]
        return True


def _rank_and_select(
    target: StrategyNode,
    n: int,
    metric: str,
    lookback: int,
    reverse: bool,
) -> bool:
    """Rank children by *metric* and select top *n* (descending if *reverse*, ascending otherwise).

    Children whose metric returns NaN are excluded from ranking.
    Returns True if at least one child is selected, False if none remain.
    Tie-breaking is stable: children retain their original order in target.children.
    """
    t_idx = target.temp["t_idx"]

    # Score each child; original index i preserves insertion-order for stable sort.
    scored: list[tuple[float, int, str]] = []
    for i, child in enumerate(target.children):
        series = target.perm["child_series"][child.id][: t_idx + 1]
        val = compute_metric(series, metric, lookback)
        if not math.isnan(val):
            scored.append((val, i, child.id))

    if not scored:
        return False

    # stable sort by metric value; secondary key `i` is never needed since sort is stable.
    scored.sort(key=lambda x: x[0], reverse=reverse)

    count = min(n, len(scored))
    target.temp["selected"] = [entry[2] for entry in scored[:count]]
    return True


class SelectTopN(BaseAlgo):
    """Rank children descending by *metric* and select top *n*."""

    def __init__(self, n: int, metric: str, lookback: int) -> None:
        self.n = n
        self.metric = metric
        self.lookback = lookback

    def __call__(self, target: StrategyNode) -> bool:
        return _rank_and_select(target, self.n, self.metric, self.lookback, reverse=True)


class SelectBottomN(BaseAlgo):
    """Rank children ascending by *metric* and select bottom *n*."""

    def __init__(self, n: int, metric: str, lookback: int) -> None:
        self.n = n
        self.metric = metric
        self.lookback = lookback

    def __call__(self, target: StrategyNode) -> bool:
        return _rank_and_select(target, self.n, self.metric, self.lookback, reverse=False)
