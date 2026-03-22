from __future__ import annotations

import collections

import numpy as np
import pandas as pd

from moa_allocations.engine.algos import (
    SelectAll,
    SelectBottomN,
    SelectIfCondition,
    SelectTopN,
    WeightEqually,
    WeightInvVol,
    WeightSpecified,
)
from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, StrategyNode, WeightNode
from moa_allocations.engine.strategy import RootNode


class PriceDataError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def _collect_tickers(root: RootNode) -> set[str]:
    """BFS walk — collect all tickers referenced in AssetNode leaves and IfElseNode conditions."""
    tickers: set[str] = set()
    queue: collections.deque = collections.deque([root.root])
    while queue:
        node = queue.popleft()
        if isinstance(node, AssetNode):
            tickers.add(node.ticker)
        elif isinstance(node, IfElseNode):
            for cond in node.conditions:
                lhs = cond.get("lhs", {})
                if "asset" in lhs:
                    tickers.add(lhs["asset"])
                rhs = cond.get("rhs")
                if isinstance(rhs, dict) and "asset" in rhs:
                    tickers.add(rhs["asset"])
            queue.append(node.true_branch)
            queue.append(node.false_branch)
        elif isinstance(node, (WeightNode, FilterNode)):
            for child in node.children:
                queue.append(child)
    return tickers


def _compute_max_lookback(root: RootNode) -> int:
    """BFS walk — return maximum lookback (trading days) across all nodes."""
    max_lb = 0
    queue: collections.deque = collections.deque([root.root])
    while queue:
        node = queue.popleft()
        if isinstance(node, FilterNode):
            max_lb = max(max_lb, node.sort_by.get("lookback", 0))
            for child in node.children:
                queue.append(child)
        elif isinstance(node, WeightNode):
            if node.method == "inverse_volatility":
                max_lb = max(max_lb, node.method_params.get("lookback", 0))
            for child in node.children:
                queue.append(child)
        elif isinstance(node, IfElseNode):
            for cond in node.conditions:
                lhs = cond.get("lhs", {})
                max_lb = max(max_lb, lhs.get("lookback", 0))
                rhs = cond.get("rhs")
                if isinstance(rhs, dict):
                    max_lb = max(max_lb, rhs.get("lookback", 0))
            queue.append(node.true_branch)
            queue.append(node.false_branch)
    return max_lb


def _build_algo_stack(node: StrategyNode) -> list:
    """Return the AlgoStack list for *node* based on its concrete class and parameters."""
    if isinstance(node, WeightNode):
        if node.method == "equal":
            return [SelectAll(), WeightEqually()]
        elif node.method == "defined":
            return [SelectAll(), WeightSpecified(node.method_params["weights"])]
        elif node.method == "inverse_volatility":
            return [SelectAll(), WeightInvVol(node.method_params["lookback"])]
    elif isinstance(node, FilterNode):
        n = node.select["count"]
        metric = node.sort_by["function"]
        lookback = node.sort_by["lookback"]
        if node.select["mode"] == "top":
            return [SelectTopN(n, metric, lookback), WeightEqually()]
        else:
            return [SelectBottomN(n, metric, lookback), WeightEqually()]
    elif isinstance(node, IfElseNode):
        return [SelectIfCondition(node.conditions, node.logic_mode), WeightEqually()]
    return []


class Runner:
    def __init__(self, root: RootNode, price_data: pd.DataFrame) -> None:
        self.root = root
        self.price_data = price_data
        self.settings = root.settings

        # --- Collect all required tickers and max lookback (single BFS each) ---
        tickers = _collect_tickers(root)
        self.max_lookback = _compute_max_lookback(root)

        # --- Validation ---
        missing = tickers - set(price_data.columns)
        if missing:
            raise PriceDataError(
                f"Missing tickers in price_data: {', '.join(sorted(missing))}"
            )

        idx = price_data.index
        start_ts = pd.Timestamp(self.settings.start_date)
        end_ts = pd.Timestamp(self.settings.end_date)

        # Need max_lookback trading days before the first sim day (start_date position in index)
        if self.max_lookback == 0:
            if len(idx) == 0 or idx[0] > start_ts:
                first = idx[0].date() if len(idx) > 0 else "empty"
                raise PriceDataError(
                    f"price_data starts at {first}, after start_date {self.settings.start_date}"
                )
        else:
            start_pos = idx.searchsorted(start_ts, side="left")
            if start_pos < self.max_lookback:
                first = idx[0].date() if len(idx) > 0 else "empty"
                raise PriceDataError(
                    f"Insufficient price history: need {self.max_lookback} trading days before "
                    f"{self.settings.start_date}, but price_data starts at {first}"
                )
        if len(idx) == 0 or idx[-1] < end_ts:
            last = idx[-1].date() if len(idx) > 0 else "empty"
            raise PriceDataError(
                f"price_data ends at {last}, before end_date {self.settings.end_date}"
            )

        # --- AlgoStack attachment + child_series pre-computation (single BFS) ---
        queue: collections.deque = collections.deque([root.root])
        while queue:
            node = queue.popleft()
            if isinstance(node, AssetNode):
                continue

            node.algo_stack = _build_algo_stack(node)
            child_series: dict[str, np.ndarray] = {}

            if isinstance(node, (WeightNode, FilterNode)):
                for child in node.children:
                    if isinstance(child, AssetNode):
                        child_series[child.id] = price_data[child.ticker].to_numpy()
                    else:
                        child_series[child.id] = np.array([], dtype=np.float64)
                    queue.append(child)

            elif isinstance(node, IfElseNode):
                for branch in (node.true_branch, node.false_branch):
                    if isinstance(branch, AssetNode):
                        child_series[branch.id] = price_data[branch.ticker].to_numpy()
                    else:
                        child_series[branch.id] = np.array([], dtype=np.float64)
                    queue.append(branch)
                for cond in node.conditions:
                    lhs = cond.get("lhs", {})
                    if "asset" in lhs:
                        asset = lhs["asset"]
                        child_series[asset] = price_data[asset].to_numpy()
                    rhs = cond.get("rhs")
                    if isinstance(rhs, dict) and "asset" in rhs:
                        asset = rhs["asset"]
                        child_series[asset] = price_data[asset].to_numpy()

            node.perm["child_series"] = child_series
