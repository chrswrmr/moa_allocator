from __future__ import annotations

import logging
import math
from typing import Any

from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.algos.metrics import compute_metric
from moa_allocations.engine.node import StrategyNode

logger = logging.getLogger(__name__)


def _node_label(node) -> str:
    return node.name or node.id


_NODE_TYPE_MAP = {"IfElseNode": "if_else", "WeightNode": "weight", "FilterNode": "filter"}


def _node_type(node) -> str:
    return _NODE_TYPE_MAP.get(type(node).__name__, type(node).__name__)


class SelectAll(BaseAlgo):
    def __call__(self, target: StrategyNode) -> bool:
        target.temp["selected"] = [child.id for child in target.children]
        node_lbl = _node_label(target)
        child_labels = [getattr(c, "ticker", None) or getattr(c, "name", None) or c.id for c in target.children]
        node_type = _node_type(target)
        logger.debug(
            "SELECT  node=%s  type=%s  selected=%s  dropped=[]",
            node_lbl, node_type, child_labels,
            extra={"keyword": "SELECT", "node": node_lbl, "node_type": node_type,
                   "selected": child_labels, "dropped": []},
        )
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
    node_lbl = _node_label(target)
    node_type = _node_type(target)
    t_idx = target.temp["t_idx"]

    # Build child label map for readable log output
    child_label_map = {
        child.id: (getattr(child, "ticker", None) or getattr(child, "name", None) or child.id)
        for child in target.children
    }

    # Score each child; original index i preserves insertion-order for stable sort.
    scored: list[tuple[float, int, str]] = []
    for i, child in enumerate(target.children):
        child_lbl = child_label_map[child.id]
        series = target.perm["child_series"][child.id][: t_idx + 1]
        val = compute_metric(series, metric, lookback)
        logger.debug(
            "METRIC  node=%s  type=%s  ticker=%s  fn=%s  lookback=%d  value=%.6f",
            node_lbl, node_type, child_lbl, metric, lookback, val,
            extra={"keyword": "METRIC", "node": node_lbl, "node_type": node_type,
                   "ticker": child_lbl, "fn": metric, "lookback": lookback, "value": val},
        )
        if not math.isnan(val):
            scored.append((val, i, child.id))

    if not scored:
        return False

    # stable sort by metric value; secondary key `i` is never needed since sort is stable.
    scored.sort(key=lambda x: x[0], reverse=reverse)

    count = min(n, len(scored))
    selected_ids = [entry[2] for entry in scored[:count]]
    target.temp["selected"] = selected_ids

    selected_labels = [child_label_map[cid] for cid in selected_ids]
    dropped_labels = [child_label_map[c.id] for c in target.children if c.id not in set(selected_ids)]
    logger.debug(
        "SELECT  node=%s  type=%s  selected=%s  dropped=%s",
        node_lbl, node_type, selected_labels, dropped_labels,
        extra={"keyword": "SELECT", "node": node_lbl, "node_type": node_type,
               "selected": selected_labels, "dropped": dropped_labels},
    )
    return True


def _evaluate_condition_at_day(
    target: StrategyNode,
    condition: dict[str, Any],
    day_idx: int,
    day_offset: int = 0,
) -> bool:
    """Evaluate a single condition dict at a single day index.

    Returns False (rather than raising) for NaN lhs or rhs values.
    """
    node_lbl = _node_label(target)
    node_type = _node_type(target)
    lhs_cfg = condition["lhs"]
    lhs_series = target.perm["child_series"][lhs_cfg["asset"]][: day_idx + 1]
    lhs_value = compute_metric(lhs_series, lhs_cfg["function"], lhs_cfg.get("lookback", 1))
    logger.debug(
        "METRIC  node=%s  type=%s  ticker=%s  fn=%s  lookback=%d  value=%.6f",
        node_lbl, node_type, lhs_cfg["asset"], lhs_cfg["function"], lhs_cfg.get("lookback", 1), lhs_value,
        extra={"keyword": "METRIC", "node": node_lbl, "node_type": node_type,
               "ticker": lhs_cfg["asset"], "fn": lhs_cfg["function"],
               "lookback": lhs_cfg.get("lookback", 1), "value": lhs_value},
    )

    rhs = condition["rhs"]
    if isinstance(rhs, dict):
        rhs_series = target.perm["child_series"][rhs["asset"]][: day_idx + 1]
        rhs_value = compute_metric(rhs_series, rhs["function"], rhs.get("lookback", 1))
        logger.debug(
            "METRIC  node=%s  type=%s  ticker=%s  fn=%s  lookback=%d  value=%.6f",
            node_lbl, node_type, rhs["asset"], rhs["function"], rhs.get("lookback", 1), rhs_value,
            extra={"keyword": "METRIC", "node": node_lbl, "node_type": node_type,
                   "ticker": rhs["asset"], "fn": rhs["function"],
                   "lookback": rhs.get("lookback", 1), "value": rhs_value},
        )
        if math.isnan(rhs_value):
            return False
    else:
        rhs_value = float(rhs)

    if math.isnan(lhs_value):
        return False

    cmp = condition["comparator"]
    result = lhs_value > rhs_value if cmp == "greater_than" else lhs_value < rhs_value
    cmp_sym = ">" if cmp == "greater_than" else "<"
    logger.debug(
        "CONDITION  node=%s  type=%s  lhs=%.6f  op=%s  rhs=%.6f  result=%s  day=%d",
        node_lbl, node_type, lhs_value, cmp_sym, rhs_value, result, day_offset,
        extra={"keyword": "CONDITION", "node": node_lbl, "node_type": node_type,
               "lhs_value": lhs_value, "comparator": cmp_sym,
               "rhs_value": rhs_value, "result": result, "day_offset": day_offset},
    )
    return result


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
                _evaluate_condition_at_day(target, condition, day_idx, day_idx - window_start)
                for day_idx in range(window_start, t_idx + 1)
            )
            condition_results.append(passed)

        if self.logic_mode == "any":
            combined = any(condition_results)
        else:  # "all"
            combined = all(condition_results)

        if combined:
            target.temp["selected"] = [target.true_branch.id]
            branch_dir = "true"
            branch_lbl = (getattr(target.true_branch, "ticker", None)
                          or getattr(target.true_branch, "name", None) or target.true_branch.id)
        else:
            target.temp["selected"] = [target.false_branch.id]
            branch_dir = "false"
            branch_lbl = (getattr(target.false_branch, "ticker", None)
                          or getattr(target.false_branch, "name", None) or target.false_branch.id)

        node_lbl = _node_label(target)
        logger.debug(
            "DECISION  node=%s  type=if_else  branch=%s  selected=%s",
            node_lbl, branch_dir, branch_lbl,
            extra={"keyword": "DECISION", "node": node_lbl, "node_type": "if_else",
                   "branch": branch_dir, "selected": branch_lbl},
        )
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
