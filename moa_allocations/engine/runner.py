from __future__ import annotations

import collections
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _node_label(node) -> str:
    return node.name or node.id


_NODE_TYPE_MAP = {"IfElseNode": "if_else", "WeightNode": "weight", "FilterNode": "filter"}


def _node_type(node) -> str:
    return _NODE_TYPE_MAP.get(type(node).__name__, type(node).__name__)

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


def _resolve_child_nav(child_id: str, parent_node, runner: Runner, t_idx: int) -> float:
    """Return the NAV/price value for a child at t_idx."""
    if child_id in runner._strategy_nodes:
        return float(runner._strategy_nodes[child_id].perm["nav_array"][t_idx])
    price_arr = parent_node.perm["child_series"].get(child_id)
    if price_arr is not None:
        return float(price_arr[runner._price_offset + t_idx])
    return float("nan")


def _child_label(child_id: str, runner: Runner) -> str:
    """Return a display name for a child node."""
    if child_id in runner._strategy_nodes:
        return _node_label(runner._strategy_nodes[child_id])
    if child_id in runner._asset_nodes:
        return runner._asset_nodes[child_id].ticker
    return child_id


def _nav_label(child_id: str, runner: Runner) -> str:
    """Return 'price' for asset children, 'nav' for strategy node children."""
    return "price" if child_id in runner._asset_nodes else "nav"


_COMPARATOR_SYMBOLS = {
    "greater_than": ">",
    "less_than": "<",
    "greater_than_or_equal_to": ">=",
    "less_than_or_equal_to": "<=",
    "equal_to": "==",
    "not_equal_to": "!=",
}

_LOGIC_MODE_LABELS = {"all": "AND", "any": "OR"}


def _format_side(side: dict) -> str:
    fn = side["function"]
    asset = side["asset"]
    lookback = side.get("lookback", 1)
    if fn == "current_price":
        return f"{asset} {fn}"
    return f"{asset} {lookback}d {fn}"


def _format_condition(cond: dict) -> str:
    """Format a condition dict as a compact expression string."""
    lhs_str = _format_side(cond["lhs"])
    cmp = _COMPARATOR_SYMBOLS.get(cond["comparator"], cond["comparator"])
    rhs = cond["rhs"]
    rhs_str = _format_side(rhs) if isinstance(rhs, dict) else str(rhs)
    return f"{lhs_str} {cmp} {rhs_str}"


def _log_upward_weight(node: WeightNode, weights: dict, t_idx: int, nav_val: float, runner: Runner) -> None:
    node_lbl = _node_label(node)
    lines = [f"┌─ type=weight-{node.method}  NodeName = {node_lbl}  id={node.id}"]
    for child_id in weights:
        if child_id == "XCASHX":
            lines.append("│  NAV XCASHX nav= 1.000000  id=XCASHX")
        else:
            child_val = _resolve_child_nav(child_id, node, runner, t_idx)
            child_lbl = _child_label(child_id, runner)
            val_lbl = _nav_label(child_id, runner)
            lines.append(f"│  NAV {child_lbl} {val_lbl}= {child_val:.6f}  id={child_id}")
    lines.append(f"│  NAV node  t={t_idx}  nav={nav_val:.6f}")
    lines.append("└─")
    logger.debug("\n" + "\n".join(lines))


def _log_upward_filter(node: FilterNode, weights: dict, t_idx: int, nav_val: float, runner: Runner) -> None:
    node_lbl = _node_label(node)
    mode = node.select["mode"]
    count = node.select["count"]
    lines = [f"┌─ type=filter-{mode}{count}  NodeName = {node_lbl}  id={node.id}"]
    for child in node.children:
        child_id = child.id
        child_val = _resolve_child_nav(child_id, node, runner, t_idx)
        child_lbl = _child_label(child_id, runner)
        val_lbl = _nav_label(child_id, runner)
        lines.append(f"│  NAV {child_lbl} {val_lbl}= {child_val:.6f}  id={child_id}")
    lines.append(f"│  NAV node  t={t_idx}  nav={nav_val:.6f}")
    lines.append("└─")
    logger.debug("\n" + "\n".join(lines))


def _log_upward_ifelse(node: IfElseNode, weights: dict, t_idx: int, nav_val: float, runner: Runner) -> None:
    node_lbl = _node_label(node)
    logic_label = _LOGIC_MODE_LABELS.get(node.logic_mode, node.logic_mode.upper())
    lines = [f"┌─ type=if_else  logic_mode={logic_label}  NodeName = {node_lbl}  id={node.id}"]
    for branch in (node.true_branch, node.false_branch):
        branch_val = _resolve_child_nav(branch.id, node, runner, t_idx)
        branch_lbl = _child_label(branch.id, runner)
        val_lbl = _nav_label(branch.id, runner)
        lines.append(f"│  NAV {branch_lbl} {val_lbl}= {branch_val:.6f}  id={branch.id}")
    lines.append(f"│  NAV node  t={t_idx}  nav={nav_val:.6f}")
    lines.append("└─")
    logger.debug("\n" + "\n".join(lines))


def _log_downward_weight(node: WeightNode, t_idx: int, runner: Runner) -> None:
    node_lbl = _node_label(node)
    weights = node.temp.get("weights", {})
    lines = [f"┌─ type=weight-{node.method}  NodeName = {node_lbl}  id={node.id}"]
    for child_id, weight in weights.items():
        if child_id == "XCASHX":
            lines.append(f"│  ← NAV XCASHX nav= 1.000000  w={weight:.6f}  id=XCASHX")
        else:
            child_val = _resolve_child_nav(child_id, node, runner, t_idx)
            child_lbl = _child_label(child_id, runner)
            val_lbl = _nav_label(child_id, runner)
            lines.append(f"│  ← NAV {child_lbl} {val_lbl}= {child_val:.6f}  w={weight:.6f}  id={child_id}")
    nav_val = node.perm["nav_array"][t_idx]
    lines.append(f"│  NAV node  t={t_idx}  nav={nav_val:.6f}")
    lines.append("└─")
    logger.debug("\n" + "\n".join(lines))


def _log_downward_filter(node: FilterNode, t_idx: int, runner: Runner) -> None:
    node_lbl = _node_label(node)
    mode = node.select["mode"]
    count = node.select["count"]
    metric = node.sort_by["function"]
    lookback = node.sort_by["lookback"]
    weights = node.temp.get("weights", {})
    child_metrics = node.temp.get("child_metrics", {})
    lines = [
        f"┌─ type=filter-{mode}{count}  NodeName = {node_lbl}  id={node.id}",
        f"│  Config: metric={metric}  lookback={lookback}",
    ]
    for child in node.children:
        child_id = child.id
        child_nav = _resolve_child_nav(child_id, node, runner, t_idx)
        child_lbl = _child_label(child_id, runner)
        val_lbl = _nav_label(child_id, runner)
        metric_val = child_metrics.get(child_id, float("nan"))
        metric_str = f"  metric={metric_val:.6f}"
        if child_id in weights:
            w = weights[child_id]
            lines.append(f"│  ↓ NAV {child_lbl} {val_lbl}= {child_nav:.6f}{metric_str}  w={w:.6f}  id={child_id}")
        else:
            lines.append(f"│  ✗ NAV {child_lbl} {val_lbl}= {child_nav:.6f}{metric_str}  id={child_id}  [dropped]")
    nav_val = node.perm["nav_array"][t_idx]
    lines.append(f"│  NAV node  t={t_idx}  nav={nav_val:.6f}")
    lines.append("└─")
    logger.debug("\n" + "\n".join(lines))


def _log_downward_ifelse(node: IfElseNode, t_idx: int, runner: Runner) -> None:
    node_lbl = _node_label(node)
    logic_label = _LOGIC_MODE_LABELS.get(node.logic_mode, node.logic_mode.upper())
    weights = node.temp.get("weights", {})
    condition_metrics = node.temp.get("condition_metrics", [])
    lines = [f"┌─ type=if_else  logic_mode={logic_label}  NodeName = {node_lbl}  id={node.id}"]
    for i, cond in enumerate(node.conditions, 1):
        lhs_str = _format_side(cond["lhs"])
        cmp = _COMPARATOR_SYMBOLS.get(cond["comparator"], cond["comparator"])
        rhs = cond["rhs"]
        rhs_str = _format_side(rhs) if isinstance(rhs, dict) else str(rhs)
        metrics = condition_metrics[i - 1] if i - 1 < len(condition_metrics) else {}
        if metrics:
            lhs_val = metrics["lhs_value"]
            rhs_val = metrics["rhs_value"]
            lhs_part = f"{lhs_str} ({lhs_val:.6f})"
            rhs_part = f"{rhs_str} ({rhs_val:.6f})" if isinstance(rhs, dict) else f"{rhs_val:.6f}"
            result_tag = "[true]" if metrics.get("result") else "[false]"
            lines.append(f"│  Condition{i} {result_tag}: {lhs_part} {cmp} {rhs_part}")
        else:
            lines.append(f"│  Condition{i}: {lhs_str} {cmp} {rhs_str}")
    true_id = node.true_branch.id
    false_id = node.false_branch.id
    decision = "true" if true_id in weights else ("false" if false_id in weights else "n/a")
    lines.append(f"│  Decision: {decision}")
    for branch_key, branch in (("true", node.true_branch), ("false", node.false_branch)):
        branch_val = _resolve_child_nav(branch.id, node, runner, t_idx)
        branch_lbl = _child_label(branch.id, runner)
        val_lbl = _nav_label(branch.id, runner)
        w = weights.get(branch.id, 0.0)
        selected = "  [SELECTED]" if branch.id in weights else ""
        lines.append(
            f"│   - {branch_key}: NAV {branch_lbl} w={w:.6f}  {val_lbl}= {branch_val:.6f}  id={branch.id}{selected}"
        )
    nav_val = node.perm["nav_array"][t_idx]
    lines.append(f"│  NAV node  t={t_idx}  nav={nav_val:.6f}")
    lines.append("└─")
    logger.debug("\n" + "\n".join(lines))


class PriceDataError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def collect_tickers(root: RootNode) -> set[str]:
    """BFS walk — collect all tickers referenced in AssetNode leaves and IfElseNode conditions.
    Also includes netting.cash_ticker when configured and non-null."""
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
    netting = root.settings.netting
    if netting is not None:
        cash_ticker = netting.get("cash_ticker")
        if cash_ticker and cash_ticker.upper() != "XCASHX":
            tickers.add(cash_ticker)
    return tickers


def collect_traded_tickers(root: RootNode) -> set[str]:
    """BFS walk — collect tickers from AssetNode leaves only, excluding XCASHX."""
    tickers: set[str] = set()
    queue: collections.deque = collections.deque([root.root])
    while queue:
        node = queue.popleft()
        if isinstance(node, AssetNode):
            if node.ticker != "XCASHX":
                tickers.add(node.ticker)
        elif isinstance(node, IfElseNode):
            queue.append(node.true_branch)
            queue.append(node.false_branch)
        elif isinstance(node, (WeightNode, FilterNode)):
            for child in node.children:
                queue.append(child)
    return tickers


def collect_signal_tickers(root: RootNode) -> set[str]:
    """BFS walk — collect tickers from if_else conditions that are NOT traded (not AssetNode leaves).
    Excludes XCASHX."""
    traded = collect_traded_tickers(root)
    condition_tickers: set[str] = set()
    queue: collections.deque = collections.deque([root.root])
    while queue:
        node = queue.popleft()
        if isinstance(node, IfElseNode):
            for cond in node.conditions:
                lhs = cond.get("lhs", {})
                if "asset" in lhs:
                    condition_tickers.add(lhs["asset"])
                rhs = cond.get("rhs")
                if isinstance(rhs, dict) and "asset" in rhs:
                    condition_tickers.add(rhs["asset"])
            queue.append(node.true_branch)
            queue.append(node.false_branch)
        elif isinstance(node, (WeightNode, FilterNode)):
            for child in node.children:
                queue.append(child)
    signal = condition_tickers - traded
    signal.discard("XCASHX")
    return signal


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


def _build_algo_stack(node: StrategyNode, price_offset: int = 0) -> list:
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
        return [SelectIfCondition(node.conditions, node.logic_mode, price_offset), WeightEqually()]
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
        self._netting = root.settings.netting

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
        # start_date may be a non-trading day; _price_offset points to the first
        # trading day >= start_date, which must equal _sim_dates[0].
        assert len(self._sim_dates) > 0 and price_data.index[self._price_offset] == self._sim_dates[0]

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
            node.algo_stack = _build_algo_stack(node, self._price_offset)
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

    def _apply_netting(self, weights: dict[str, float]) -> dict[str, float]:
        """Apply netting pairs transformation to the global weight dict.

        For each pair, computes net exposure, collapses to a single-leg position,
        and routes freed weight to cash_ticker (or XCASHX if cash_ticker is null).
        Returns a new dict; input is not modified.
        """
        if not self._netting:
            return weights
        pairs = self._netting.get("pairs", [])
        if not pairs:
            return weights

        cash_ticker = self._netting.get("cash_ticker") or None
        result = dict(weights)
        freed = 0.0

        for pair in pairs:
            long_ticker = pair["long_ticker"]
            short_ticker = pair["short_ticker"]
            L = pair["long_leverage"]   # > 0
            S = pair["short_leverage"]  # < 0

            w_long = result.pop(long_ticker, 0.0)
            w_short = result.pop(short_ticker, 0.0)

            net_exposure = w_long * L + w_short * S

            if net_exposure > 0.0:
                new_w_long = net_exposure / L
                new_w_short = 0.0
            elif net_exposure < 0.0:
                new_w_long = 0.0
                new_w_short = net_exposure / S
            else:
                new_w_long = 0.0
                new_w_short = 0.0

            freed += (w_long + w_short) - (new_w_long + new_w_short)

            if new_w_long > 0.0:
                result[long_ticker] = new_w_long
            if new_w_short > 0.0:
                result[short_ticker] = new_w_short

        if freed > 0.0:
            dest = cash_ticker if cash_ticker else "XCASHX"
            result[dest] = result.get(dest, 0.0) + freed

        return result

    def _upward_pass(self, t_idx: int, date_str: str = "") -> None:
        """Bottom-up NAV update: iterate _upward_order and compute each node's nav_array[t_idx]."""
        logger.debug(
            "UPWARD  start  date=%s  t=%d",
            date_str, t_idx,
            extra={"keyword": "UPWARD", "text": "start", "date": date_str, "t_idx": t_idx},
        )
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
            nav_val = node.perm["nav_array"][t_idx]
            if isinstance(node, WeightNode):
                _log_upward_weight(node, weights, t_idx, nav_val, self)
            elif isinstance(node, FilterNode):
                _log_upward_filter(node, weights, t_idx, nav_val, self)
            elif isinstance(node, IfElseNode):
                _log_upward_ifelse(node, weights, t_idx, nav_val, self)

    def _update_child_series_views(self, t_idx: int) -> None:
        """Update child_series views for StrategyNode children to include day t_idx."""
        for node in self._upward_order:
            child_series = node.perm["child_series"]
            for child_id in child_series:
                if child_id in self._strategy_nodes:
                    child_series[child_id] = self._strategy_nodes[child_id].perm["nav_array"][: t_idx + 1]

    def _downward_pass(self, t_idx: int, date_str: str = "") -> None:
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

            if isinstance(node, WeightNode):
                _log_downward_weight(node, t_idx, self)
            elif isinstance(node, FilterNode):
                _log_downward_filter(node, t_idx, self)
            elif isinstance(node, IfElseNode):
                _log_downward_ifelse(node, t_idx, self)

    def run(self) -> pd.DataFrame:
        """Simulate over _sim_dates. Upward Pass every day (t_idx > 0); Downward Pass on rebalance days."""
        rows: list[dict] = []
        xcashx_seen = False
        netting_cash_seen = False
        _raw_cash_ticker = (self._netting or {}).get("cash_ticker") or None
        # XCASHX is a sentinel — treat as no real cash ticker for column purposes
        netting_cash_ticker = (
            None if (_raw_cash_ticker and _raw_cash_ticker.upper() == "XCASHX")
            else _raw_cash_ticker
        )

        for t_idx, current_date in enumerate(self._sim_dates):
            # Reset temp for all strategy nodes, then restore prior-day weights
            for node in self._strategy_nodes.values():
                node.temp = {"t_idx": t_idx}
            for node_id, w in self._prev_weights.items():
                self._strategy_nodes[node_id].temp["weights"] = w

            date_str = current_date.strftime("%Y-%m-%d")

            if t_idx > 0:
                self._upward_pass(t_idx, date_str)
                self._update_child_series_views(t_idx)

            if t_idx == 0:
                is_rebalance = True
            else:
                prev_date = self._sim_dates[t_idx - 1]
                is_rebalance = _is_rebalance_day(current_date, prev_date, self.settings.rebalance_frequency)

            if is_rebalance:
                logger.debug(
                    "DOWNWARD  t=%s  t_idx=%d",
                    date_str, t_idx,
                    extra={"keyword": "DOWNWARD", "date": date_str, "t_idx": t_idx},
                )
                self._downward_pass(t_idx, date_str)
            else:
                logger.debug("t=%s  (no rebalance)", date_str)

            weights = self._flatten_weights()
            weights = self._apply_netting(weights)
            total = sum(weights.values())
            assert abs(total - 1.0) < 1e-9, f"Global weights sum to {total}, expected 1.0"
            logger.debug(
                "ALLOC  t=%s  weights=%s",
                date_str, {k: f"{v:.6f}" for k, v in weights.items()},
                extra={"keyword": "ALLOC", "date": date_str, "weights": weights},
            )
            logger.debug("-" * 50)
            if "XCASHX" in weights:
                xcashx_seen = True
            if netting_cash_ticker and netting_cash_ticker in weights:
                netting_cash_seen = True

            row: dict = {"DATE": date_str}
            row.update(weights)
            rows.append(row)

        cols = ["DATE"] + self._leaf_order
        if netting_cash_ticker and netting_cash_seen and netting_cash_ticker not in self._leaf_order:
            cols.append(netting_cash_ticker)
        if xcashx_seen:
            cols.append("XCASHX")
        df = pd.DataFrame(rows, columns=cols).fillna(0.0)

        return df
