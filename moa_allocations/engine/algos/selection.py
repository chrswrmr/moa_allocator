from __future__ import annotations

import math
from typing import Any

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


def _evaluate_condition_at_day(
    target: StrategyNode,
    condition: dict[str, Any],
    day_idx: int,
) -> bool:
    """Evaluate a single condition dict at a single day index.

    Returns False (rather than raising) for NaN lhs or rhs values.
    """
    lhs_cfg = condition["lhs"]
    lhs_series = target.perm["child_series"][lhs_cfg["asset"]][: day_idx + 1]
    lhs_value = compute_metric(lhs_series, lhs_cfg["function"], lhs_cfg.get("lookback", 1))

    rhs = condition["rhs"]
    if isinstance(rhs, dict):
        rhs_series = target.perm["child_series"][rhs["asset"]][: day_idx + 1]
        rhs_value = compute_metric(rhs_series, rhs["function"], rhs.get("lookback", 1))
        if math.isnan(rhs_value):
            return False
    else:
        rhs_value = float(rhs)

    if math.isnan(lhs_value):
        return False

    if condition["comparator"] == "greater_than":
        return lhs_value > rhs_value
    else:  # "less_than"
        return lhs_value < rhs_value


class SelectIfCondition(BaseAlgo):
    """Route to true_branch or false_branch based on one or more metric conditions."""

    def __init__(self, conditions: list[dict[str, Any]], logic_mode: str) -> None:
        self.conditions = conditions
        self.logic_mode = logic_mode

    def __call__(self, target: StrategyNode) -> bool:
        t_idx: int = target.temp["t_idx"]

        condition_results: list[bool] = []
        for condition in self.conditions:
            duration: int = condition.get("duration", 1)
            window_start = max(0, t_idx - duration + 1)
            passed = all(
                _evaluate_condition_at_day(target, condition, day_idx)
                for day_idx in range(window_start, t_idx + 1)
            )
            condition_results.append(passed)

        if self.logic_mode == "any":
            combined = any(condition_results)
        else:  # "all"
            combined = all(condition_results)

        if combined:
            target.temp["selected"] = [target.true_branch.id]
        else:
            target.temp["selected"] = [target.false_branch.id]

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
