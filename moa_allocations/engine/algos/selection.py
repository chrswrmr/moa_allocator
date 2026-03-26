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

    all_metrics: dict[str, float] = {}
    scored: list[tuple[float, int, str]] = []
    for i, child in enumerate(target.children):
        series = target.perm["child_series"][child.id][: t_idx + 1]
        val = compute_metric(series, metric, lookback)
        all_metrics[child.id] = val
        if not math.isnan(val):
            scored.append((val, i, child.id))

    target.temp["child_metrics"] = all_metrics

    if not scored:
        return False

    scored.sort(key=lambda x: x[0], reverse=reverse)

    count = min(n, len(scored))
    selected_ids = [entry[2] for entry in scored[:count]]
    target.temp["selected"] = selected_ids
    return True


def _evaluate_condition_at_day(
    target: StrategyNode,
    condition: dict[str, Any],
    day_idx: int,
    day_offset: int = 0,
    price_offset: int = 0,
) -> tuple[bool, float, float]:
    """Evaluate a single condition dict at a single day index.

    Returns (result, lhs_value, rhs_value). result is False (rather than raising)
    for NaN lhs or rhs values.
    """
    lhs_cfg = condition["lhs"]
    lhs_series = target.perm["child_series"][lhs_cfg["asset"]][: price_offset + day_idx + 1]
    lhs_value = compute_metric(lhs_series, lhs_cfg["function"], lhs_cfg.get("lookback", 1))

    rhs = condition["rhs"]
    if isinstance(rhs, dict):
        rhs_series = target.perm["child_series"][rhs["asset"]][: price_offset + day_idx + 1]
        rhs_value = compute_metric(rhs_series, rhs["function"], rhs.get("lookback", 1))
        if math.isnan(rhs_value):
            return False, lhs_value, rhs_value
    else:
        rhs_value = float(rhs)

    if math.isnan(lhs_value):
        return False, lhs_value, rhs_value

    cmp = condition["comparator"]
    result = lhs_value > rhs_value if cmp == "greater_than" else lhs_value < rhs_value
    return result, lhs_value, rhs_value


class SelectIfCondition(BaseAlgo):
    """Route to true_branch or false_branch based on one or more metric conditions."""

    def __init__(self, conditions: list[dict[str, Any]], logic_mode: str, price_offset: int = 0) -> None:
        self.conditions = conditions
        self.logic_mode = logic_mode
        self._price_offset = price_offset

    def __call__(self, target: StrategyNode) -> bool:
        t_idx: int = target.temp["t_idx"]

        condition_results: list[bool] = []
        condition_metrics: list[dict] = []
        for condition in self.conditions:
            duration: int = condition.get("duration", 1)
            window_start = max(0, t_idx - duration + 1)
            last_lhs = float("nan")
            last_rhs = float("nan")
            day_results: list[bool] = []
            for day_idx in range(window_start, t_idx + 1):
                result, lhs_val, rhs_val = _evaluate_condition_at_day(
                    target, condition, day_idx, day_idx - window_start, self._price_offset
                )
                day_results.append(result)
                last_lhs, last_rhs = lhs_val, rhs_val
            cond_passed = all(day_results)
            condition_results.append(cond_passed)
            condition_metrics.append({"lhs_value": last_lhs, "rhs_value": last_rhs, "result": cond_passed})

        target.temp["condition_metrics"] = condition_metrics

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
