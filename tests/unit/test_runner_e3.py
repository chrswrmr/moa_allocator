"""Tests for Runner E3 — downward pass, AlgoStack execution, XCASHX fallback."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from moa_allocations.engine import Runner
from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, StrategyNode, WeightNode
from moa_allocations.engine.strategy import RootNode, Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRADING_DAYS = pd.bdate_range("2023-01-02", "2024-12-31")


def _settings(
    start: str = "2024-01-02",
    end: str = "2024-01-10",
    frequency: str = "daily",
) -> Settings:
    return Settings(
        id="test",
        name="test",
        starting_cash=100_000.0,
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
        slippage=0.0,
        fees=0.0,
        rebalance_frequency=frequency,
        rebalance_threshold=None,
    )


def _price_data(tickers: list[str], index=_TRADING_DAYS) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        rng.uniform(100, 200, size=(len(index), len(tickers))),
        index=index,
        columns=tickers,
    )


def _root(root_node, start: str = "2024-01-02", end: str = "2024-01-10", frequency: str = "daily") -> RootNode:
    return RootNode(settings=_settings(start, end, frequency), root=root_node, dsl_version="1.0.0")


# ---------------------------------------------------------------------------
# Custom algos for testing
# ---------------------------------------------------------------------------

class _RecordExecution(BaseAlgo):
    """Records (node.id, t_idx) each time called; sets equal weights over children."""

    def __init__(self, log: list) -> None:
        self.log = log

    def __call__(self, target: StrategyNode) -> bool:
        self.log.append((target.id, target.temp["t_idx"]))
        # Provide minimal valid weights so _flatten_weights works
        if hasattr(target, "children"):
            target.temp["selected"] = [c.id for c in target.children]
            n = len(target.children)
            target.temp["weights"] = {c.id: 1.0 / n for c in target.children}
        elif isinstance(target, IfElseNode):
            target.temp["selected"] = [target.true_branch.id]
            target.temp["weights"] = {target.true_branch.id: 1.0}
        return True


class _AlwaysFalse(BaseAlgo):
    """Returns False — triggers XCASHX fallback."""

    def __call__(self, target: StrategyNode) -> bool:
        return False


class _UnnormalisedWeights(BaseAlgo):
    """Sets weights that don't sum to 1.0 — for testing normalisation."""

    def __init__(self, raw_weights: dict[str, float]) -> None:
        self.raw_weights = raw_weights

    def __call__(self, target: StrategyNode) -> bool:
        target.temp["weights"] = dict(self.raw_weights)
        return True


# ---------------------------------------------------------------------------
# Test 5.1 — Temp reset
# ---------------------------------------------------------------------------

def test_temp_reset_sets_t_idx_each_day():
    """Algo sees t_idx = 0, 1, 2 on successive days (confirms temp is reset each day)."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    runner = Runner(_root(root_node, end="2024-01-04"), _price_data(["SPY", "BND"]))

    log: list = []
    runner._strategy_nodes["root"].algo_stack = [_RecordExecution(log)]

    runner.run()

    seen_t_idxs = [t for _, t in log]
    assert seen_t_idxs == [0, 1, 2], f"Expected [0, 1, 2], got {seen_t_idxs}"


def test_temp_reset_seeds_t_idx_and_restores_weights():
    """On day 0 temp has only t_idx (no prior weights). On day 1+ prior weights are restored."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    runner = Runner(_root(root_node, end="2024-01-03"), _price_data(["SPY", "BND"]))

    snapshots: list[dict] = []

    class _SnapshotTemp(BaseAlgo):
        def __call__(self, target: StrategyNode) -> bool:
            snapshots.append(dict(target.temp))
            target.temp["selected"] = [c.id for c in target.children]
            n = len(target.children)
            target.temp["weights"] = {c.id: 1.0 / n for c in target.children}
            return True

    runner._strategy_nodes["root"].algo_stack = [_SnapshotTemp()]
    runner.run()

    # Day 0: only t_idx is seeded (no prior weights exist yet)
    assert snapshots[0] == {"t_idx": 0}
    # Day 1+: prior weights are restored from _prev_weights before algo runs
    assert snapshots[1]["t_idx"] == 1
    assert "weights" in snapshots[1], "Prior weights must be restored before algo runs on day 1+"


# ---------------------------------------------------------------------------
# Test 5.2 — Top-down execution order
# ---------------------------------------------------------------------------

def test_downward_pass_top_down_order():
    """Root node's AlgoStack executes before child sub-strategy."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    child = WeightNode(id="child", method="equal", method_params={}, children=[a, b])
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[child])

    runner = Runner(_root(root_node, end="2024-01-02"), _price_data(["SPY", "BND"]))

    log: list = []
    runner._strategy_nodes["root"].algo_stack = [_RecordExecution(log)]
    runner._strategy_nodes["child"].algo_stack = [_RecordExecution(log)]

    runner.run()

    ids = [node_id for node_id, _ in log]
    assert ids.index("root") < ids.index("child"), "root must execute before child"


# ---------------------------------------------------------------------------
# Test 5.3 — Successful stack: WeightNode(equal) produces normalised equal weights
# ---------------------------------------------------------------------------

def test_successful_stack_weight_equal_three_children():
    """WeightNode(equal) with 3 assets → 3 equal weights summing to 1.0."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    c = AssetNode(id="c", ticker="GLD")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b, c])

    runner = Runner(_root(root_node), _price_data(["SPY", "BND", "GLD"]))
    df = runner.run()

    row = df.iloc[0]
    assert abs(row["SPY"] - 1 / 3) < 1e-9
    assert abs(row["BND"] - 1 / 3) < 1e-9
    assert abs(row["GLD"] - 1 / 3) < 1e-9
    assert abs(row[["SPY", "BND", "GLD"]].sum() - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Test 5.4 — XCASHX fallback when algo returns False
# ---------------------------------------------------------------------------

def test_xcashx_fallback_on_algo_false():
    """When an algo returns False, node gets XCASHX=1.0 and output column is present."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    runner = Runner(_root(root_node, end="2024-01-02"), _price_data(["SPY", "BND"]))
    runner._strategy_nodes["root"].algo_stack = [_AlwaysFalse()]

    df = runner.run()

    assert "XCASHX" in df.columns
    assert df.iloc[0]["XCASHX"] == pytest.approx(1.0)
    assert df.iloc[0]["SPY"] == pytest.approx(0.0)
    assert df.iloc[0]["BND"] == pytest.approx(0.0)


def test_xcashx_fallback_second_algo_not_executed():
    """When first algo returns False, subsequent algos must not run."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    runner = Runner(_root(root_node, end="2024-01-02"), _price_data(["SPY", "BND"]))

    second_ran = []

    class _ShouldNotRun(BaseAlgo):
        def __call__(self, target: StrategyNode) -> bool:
            second_ran.append(True)
            return True

    runner._strategy_nodes["root"].algo_stack = [_AlwaysFalse(), _ShouldNotRun()]
    runner.run()

    assert second_ran == [], "Second algo must not run after first returns False"


# ---------------------------------------------------------------------------
# Test 5.5 — Normalisation of weights
# ---------------------------------------------------------------------------

def test_normalisation_corrects_non_unit_weights():
    """Weights that sum to != 1.0 are normalised to 1.0 after the stack."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    runner = Runner(_root(root_node, end="2024-01-02"), _price_data(["SPY", "BND"]))
    # Raw weights sum to 0.6 — normalised each should be 0.5
    runner._strategy_nodes["root"].algo_stack = [
        _UnnormalisedWeights({"a": 0.3, "b": 0.3})
    ]

    df = runner.run()

    assert df.iloc[0]["SPY"] == pytest.approx(0.5)
    assert df.iloc[0]["BND"] == pytest.approx(0.5)


def test_zero_sum_weights_fall_back_to_xcashx():
    """Weights summing to 0.0 trigger XCASHX fallback."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    runner = Runner(_root(root_node, end="2024-01-02"), _price_data(["SPY", "BND"]))
    runner._strategy_nodes["root"].algo_stack = [
        _UnnormalisedWeights({"a": 0.0, "b": 0.0})
    ]

    df = runner.run()

    assert "XCASHX" in df.columns
    assert df.iloc[0]["XCASHX"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 5.6 — Weight carry-forward on non-rebalance days
# ---------------------------------------------------------------------------

def test_weight_carry_forward_monthly_rebalance():
    """On non-rebalance days, prior weights carry forward and output is consistent."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    # Jan 2024: day 0 rebalances; days 1–6 are all January so no rebalance
    runner = Runner(
        _root(root_node, start="2024-01-02", end="2024-01-10", frequency="monthly"),
        _price_data(["SPY", "BND"]),
    )
    df = runner.run()

    # All rows in the same month carry the same weights (0.5 / 0.5)
    assert np.allclose(df["SPY"].to_numpy(), 0.5)
    assert np.allclose(df["BND"].to_numpy(), 0.5)


def test_weight_carry_forward_does_not_prevent_nav_update():
    """Upward pass still updates NAV on non-rebalance days even though weights carry forward."""
    a = AssetNode(id="a", ticker="SPY")
    b = AssetNode(id="b", ticker="BND")
    root_node = WeightNode(id="root", method="equal", method_params={}, children=[a, b])

    runner = Runner(
        _root(root_node, start="2024-01-02", end="2024-01-05", frequency="monthly"),
        _price_data(["SPY", "BND"]),
    )
    runner.run()

    nav = runner._strategy_nodes["root"].perm["nav_array"]
    # NAV should diverge from 1.0 after day 0 as prices move
    assert not np.all(nav == 1.0), "NAV must update even on non-rebalance days"


# ---------------------------------------------------------------------------
# Test 5.7 — IfElseNode routing
# ---------------------------------------------------------------------------

def test_ifelsenode_routes_to_true_branch_when_condition_passes():
    """IfElseNode with always-true condition → weights only contain true_branch id."""
    true_node = AssetNode(id="true_asset", ticker="SPY")
    false_node = AssetNode(id="false_asset", ticker="BND")
    # condition: SPY current_price < 999999 — always true for any realistic price
    conditions = [
        {
            "lhs": {"asset": "SPY", "function": "current_price", "lookback": 1},
            "comparator": "less_than",
            "rhs": 999999,
            "duration": 1,
        }
    ]
    root_node = IfElseNode(
        id="root",
        logic_mode="all",
        conditions=conditions,
        true_branch=true_node,
        false_branch=false_node,
    )

    runner = Runner(_root(root_node, end="2024-01-02"), _price_data(["SPY", "BND"]))
    runner.run()

    weights = runner._strategy_nodes["root"].temp.get("weights", {})
    assert "true_asset" in weights
    assert weights["true_asset"] == pytest.approx(1.0)
    assert "false_asset" not in weights


def test_ifelsenode_routes_to_false_branch_when_condition_fails():
    """IfElseNode with always-false condition → weights only contain false_branch id."""
    true_node = AssetNode(id="true_asset", ticker="SPY")
    false_node = AssetNode(id="false_asset", ticker="BND")
    # condition: SPY current_price > 999999 — always false
    conditions = [
        {
            "lhs": {"asset": "SPY", "function": "current_price", "lookback": 1},
            "comparator": "greater_than",
            "rhs": 999999,
            "duration": 1,
        }
    ]
    root_node = IfElseNode(
        id="root",
        logic_mode="all",
        conditions=conditions,
        true_branch=true_node,
        false_branch=false_node,
    )

    runner = Runner(_root(root_node, end="2024-01-02"), _price_data(["SPY", "BND"]))
    runner.run()

    weights = runner._strategy_nodes["root"].temp.get("weights", {})
    assert "false_asset" in weights
    assert weights["false_asset"] == pytest.approx(1.0)
    assert "true_asset" not in weights
