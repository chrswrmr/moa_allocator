from __future__ import annotations

import collections
from pathlib import Path

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


def collect_tickers(root: RootNode) -> set[str]:
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


def compute_max_lookback(root: RootNode) -> int:
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


def _collect_leaf_order(root: RootNode) -> list[str]:
    """DFS walk returning asset tickers in DSL left-to-right order (pre-order)."""
    tickers: list[str] = []
    stack = [root.root]
    while stack:
        node = stack.pop()
        if isinstance(node, AssetNode):
            if node.ticker not in tickers:
                tickers.append(node.ticker)
        elif isinstance(node, (WeightNode, FilterNode)):
            for child in reversed(node.children):
                stack.append(child)
        elif isinstance(node, IfElseNode):
            stack.append(node.false_branch)
            stack.append(node.true_branch)
    return tickers


def _is_rebalance_day(current_date, prev_date, frequency: str) -> bool:
    """Return True if current_date is a rebalance day given frequency."""
    if frequency == "daily":
        return True
    elif frequency == "weekly":
        return current_date.isocalendar()[:2] != prev_date.isocalendar()[:2]
    elif frequency == "monthly":
        return current_date.month != prev_date.month
    return True


class Runner:
    def __init__(self, root: RootNode, price_data: pd.DataFrame) -> None:
        self.root = root
        self.price_data = price_data
        self.settings = root.settings

        # --- Collect all required tickers and max lookback (single BFS each) ---
        tickers = collect_tickers(root)
        self.max_lookback = compute_max_lookback(root)

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

        # --- Simulation date range and price offset ---
        self._sim_dates = idx[(idx >= start_ts) & (idx <= end_ts)]
        self._price_offset = int(idx.searchsorted(start_ts, side="left"))
        assert price_data.index[self._price_offset] == start_ts

        T = len(self._sim_dates)

        # --- AlgoStack attachment + child_series pre-computation (single BFS) ---
        depth_nodes: list[tuple[int, StrategyNode]] = []
        self._strategy_nodes: dict[str, StrategyNode] = {}
        self._asset_nodes: dict[str, AssetNode] = {}

        queue: collections.deque = collections.deque([(root.root, 0)])
        while queue:
            node, depth = queue.popleft()
            if isinstance(node, AssetNode):
                continue

            # Allocate nav_array if not already done (eagerly pre-allocated by parent, or root)
            if "nav_array" not in node.perm:
                node.perm["nav_array"] = np.ones(T, dtype=np.float64)

            self._strategy_nodes[node.id] = node
            depth_nodes.append((depth, node))
            node.algo_stack = _build_algo_stack(node)
            child_series: dict[str, np.ndarray] = {}

            if isinstance(node, (WeightNode, FilterNode)):
                for child in node.children:
                    if isinstance(child, AssetNode):
                        self._asset_nodes[child.id] = child
                        child_series[child.id] = price_data[child.ticker].to_numpy()
                    else:
                        if "nav_array" not in child.perm:
                            child.perm["nav_array"] = np.ones(T, dtype=np.float64)
                        child_series[child.id] = child.perm["nav_array"][:1]
                    queue.append((child, depth + 1))

            elif isinstance(node, IfElseNode):
                for branch in (node.true_branch, node.false_branch):
                    if isinstance(branch, AssetNode):
                        self._asset_nodes[branch.id] = branch
                        child_series[branch.id] = price_data[branch.ticker].to_numpy()
                    else:
                        if "nav_array" not in branch.perm:
                            branch.perm["nav_array"] = np.ones(T, dtype=np.float64)
                        child_series[branch.id] = branch.perm["nav_array"][:1]
                    queue.append((branch, depth + 1))
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

        # Sort by depth descending — deepest nodes first (bottom-up order)
        depth_nodes.sort(key=lambda x: x[0], reverse=True)
        self._upward_order: list[StrategyNode] = [n for _, n in depth_nodes]

        # Leaf order for DataFrame column assembly
        self._leaf_order: list[str] = _collect_leaf_order(root)

        # Per-node weight store: carries weights across days for upward pass and carry-forward
        self._prev_weights: dict[str, dict[str, float]] = {}

    def _flatten_weights(self) -> dict[str, float]:
        """DFS from root: multiply cumulative parent weight by local weights, accumulate leaf tickers."""
        acc: dict[str, float] = {}

        def _dfs(node, parent_weight: float) -> None:
            if isinstance(node, AssetNode):
                acc[node.ticker] = acc.get(node.ticker, 0.0) + parent_weight
                return
            weights = node.temp.get("weights", {})
            for child_id, local_w in weights.items():
                global_w = parent_weight * local_w
                if child_id == "XCASHX":
                    acc["XCASHX"] = acc.get("XCASHX", 0.0) + global_w
                elif child_id in self._strategy_nodes:
                    _dfs(self._strategy_nodes[child_id], global_w)
                elif child_id in self._asset_nodes:
                    _dfs(self._asset_nodes[child_id], global_w)

        _dfs(self.root.root, 1.0)
        total = sum(acc.values())
        assert abs(total - 1.0) < 1e-9, f"Global weights sum to {total}, expected 1.0"
        return acc

    def _upward_pass(self, t_idx: int) -> None:
        """Bottom-up NAV update: iterate _upward_order and compute each node's nav_array[t_idx]."""
        for node in self._upward_order:
            weights = node.temp.get("weights", {})
            if not weights:
                continue

            weighted_return = 0.0
            for child_id, weight in weights.items():
                if child_id == "XCASHX":
                    child_return = 0.0
                elif child_id in self._strategy_nodes:
                    child_nav = self._strategy_nodes[child_id].perm["nav_array"]
                    child_return = child_nav[t_idx] / child_nav[t_idx - 1] - 1.0
                else:
                    price_arr = node.perm["child_series"][child_id]
                    child_return = (
                        price_arr[self._price_offset + t_idx]
                        / price_arr[self._price_offset + t_idx - 1]
                        - 1.0
                    )
                weighted_return += weight * child_return

            node.perm["nav_array"][t_idx] = node.perm["nav_array"][t_idx - 1] * (1.0 + weighted_return)

    def _update_child_series_views(self, t_idx: int) -> None:
        """Update child_series views for StrategyNode children to include day t_idx."""
        for node in self._upward_order:
            child_series = node.perm["child_series"]
            for child_id in child_series:
                if child_id in self._strategy_nodes:
                    child_series[child_id] = self._strategy_nodes[child_id].perm["nav_array"][: t_idx + 1]

    def _downward_pass(self, t_idx: int) -> None:
        """Top-down AlgoStack execution: iterate root-first, run each node's algo_stack."""
        for node in reversed(self._upward_order):
            for algo in node.algo_stack:
                if not algo(node):
                    node.temp["weights"] = {"XCASHX": 1.0}
                    break
            else:
                # Normalise weights to sum to 1.0; fall back to XCASHX if sum is 0
                weights = node.temp.get("weights", {})
                total = sum(weights.values())
                if total == 0.0:
                    node.temp["weights"] = {"XCASHX": 1.0}
                elif abs(total - 1.0) > 1e-12:
                    node.temp["weights"] = {k: v / total for k, v in weights.items()}

            self._prev_weights[node.id] = node.temp["weights"]

    def run(self) -> pd.DataFrame:
        """Simulate over _sim_dates. Upward Pass every day (t_idx > 0); Downward Pass on rebalance days."""
        rows: list[dict] = []
        xcashx_seen = False

        for t_idx, current_date in enumerate(self._sim_dates):
            # Reset temp for all strategy nodes, then restore prior-day weights
            for node in self._strategy_nodes.values():
                node.temp = {"t_idx": t_idx}
            for node_id, w in self._prev_weights.items():
                self._strategy_nodes[node_id].temp["weights"] = w

            if t_idx > 0:
                self._upward_pass(t_idx)
                self._update_child_series_views(t_idx)

            if t_idx == 0:
                is_rebalance = True
            else:
                prev_date = self._sim_dates[t_idx - 1]
                is_rebalance = _is_rebalance_day(current_date, prev_date, self.settings.rebalance_frequency)

            if is_rebalance:
                self._downward_pass(t_idx)

            date_str = current_date.strftime("%Y-%m-%d")
            weights = self._flatten_weights()
            if "XCASHX" in weights:
                xcashx_seen = True

            row: dict = {"DATE": date_str}
            row.update(weights)
            rows.append(row)

        cols = ["DATE"] + self._leaf_order
        if xcashx_seen:
            cols.append("XCASHX")
        df = pd.DataFrame(rows, columns=cols).fillna(0.0)

        Path("output").mkdir(exist_ok=True)
        df.to_csv("output/allocations.csv", index=False)

        return df
