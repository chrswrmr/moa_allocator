"""Tests for Runner E2 — upward pass, rebalance schedule, sim loop."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from moa_allocations.engine import Runner
from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, WeightNode
from moa_allocations.engine.runner import _is_rebalance_day
from moa_allocations.engine.strategy import RootNode, Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRADING_DAYS = pd.bdate_range("2023-01-02", "2024-12-31")


def _settings(
    start: str = "2024-01-02",
    end: str = "2024-06-28",
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


def _asset(id: str, ticker: str) -> AssetNode:
    return AssetNode(id=id, ticker=ticker)


def _weight_equal(id: str, children: list) -> WeightNode:
    return WeightNode(id=id, method="equal", method_params={}, children=children)


def _weight_defined(id: str, children: list, weights: dict) -> WeightNode:
    return WeightNode(id=id, method="defined", method_params={"weights": weights}, children=children)


def _if_else(id: str, conditions: list, logic_mode: str, true_branch, false_branch) -> IfElseNode:
    return IfElseNode(
        id=id,
        logic_mode=logic_mode,
        conditions=conditions,
        true_branch=true_branch,
        false_branch=false_branch,
    )


def _root(root_node, start: str = "2024-01-02", end: str = "2024-06-28", frequency: str = "daily") -> RootNode:
    return RootNode(settings=_settings(start, end, frequency), root=root_node, dsl_version="1.0.0")


# ---------------------------------------------------------------------------
# 5.1  _is_rebalance_day
# ---------------------------------------------------------------------------

class TestIsRebalanceDay:
    def test_daily_always_true(self):
        d1 = date(2024, 1, 8)
        d2 = date(2024, 1, 9)
        assert _is_rebalance_day(d2, d1, "daily") is True

    def test_weekly_new_week_triggers(self):
        # Friday Jan 5 (week 1) → Monday Jan 8 (week 2)
        prev = date(2024, 1, 5)
        curr = date(2024, 1, 8)
        assert _is_rebalance_day(curr, prev, "weekly") is True

    def test_weekly_mid_week_no_trigger(self):
        # Monday Jan 8 → Tuesday Jan 9 (same week 2)
        prev = date(2024, 1, 8)
        curr = date(2024, 1, 9)
        assert _is_rebalance_day(curr, prev, "weekly") is False

    def test_monthly_new_month_triggers(self):
        prev = date(2024, 1, 31)
        curr = date(2024, 2, 1)
        assert _is_rebalance_day(curr, prev, "monthly") is True

    def test_monthly_same_month_no_trigger(self):
        prev = date(2024, 2, 1)
        curr = date(2024, 2, 5)
        assert _is_rebalance_day(curr, prev, "monthly") is False

    def test_weekly_year_boundary_same_iso_week(self):
        # 2024-12-31 is ISO week 1 of 2025; 2025-01-02 is also ISO week 1 of 2025
        prev = date(2024, 12, 31)
        curr = date(2025, 1, 2)
        assert _is_rebalance_day(curr, prev, "weekly") is False


# ---------------------------------------------------------------------------
# 5.2  _sim_dates and _price_offset
# ---------------------------------------------------------------------------

class TestSimDatesAndOffset:
    def test_sim_dates_filtered_to_range(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node, start="2024-01-02", end="2024-03-29")
        runner = Runner(root, _price_data(["SPY"]))
        assert runner._sim_dates[0] == pd.Timestamp("2024-01-02")
        assert runner._sim_dates[-1] == pd.Timestamp("2024-03-29")
        assert all(runner._sim_dates >= pd.Timestamp("2024-01-02"))
        assert all(runner._sim_dates <= pd.Timestamp("2024-03-29"))

    def test_price_offset_with_lookback_period(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node, start="2024-01-02", end="2024-06-28")
        price_data = _price_data(["SPY"])  # starts 2023-01-02
        runner = Runner(root, price_data)
        # price_data.index[_price_offset] must be start_date
        assert price_data.index[runner._price_offset] == pd.Timestamp("2024-01-02")
        # Offset should be > 0 because price data starts in 2023
        assert runner._price_offset > 0

    def test_price_offset_zero_when_no_lookback(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node, start="2023-01-02", end="2023-06-30")
        # price_data starts exactly on start_date
        index = pd.bdate_range("2023-01-02", "2023-12-31")
        price_data = _price_data(["SPY"], index=index)
        runner = Runner(root, price_data)
        assert runner._price_offset == 0


# ---------------------------------------------------------------------------
# 5.3  _upward_order
# ---------------------------------------------------------------------------

class TestUpwardOrder:
    def test_two_level_tree_only_root(self):
        # WeightNode (depth 0) with 3 AssetNode children — only root in order
        a1 = _asset("a1", "SPY")
        a2 = _asset("a2", "BND")
        a3 = _asset("a3", "GLD")
        root_node = _weight_equal("root", [a1, a2, a3])
        root = _root(root_node)
        runner = Runner(root, _price_data(["SPY", "BND", "GLD"]))
        assert len(runner._upward_order) == 1
        assert runner._upward_order[0] is root_node

    def test_nested_tree_deepest_first(self):
        # W1 (depth 0) has children W2 (depth 1) and A1 (depth 1)
        # W2 has children A2, A3
        a1 = _asset("a1", "SPY")
        a2 = _asset("a2", "BND")
        a3 = _asset("a3", "GLD")
        w2 = _weight_equal("w2", [a2, a3])
        w1 = _weight_equal("w1", [w2, a1])
        root = _root(w1)
        runner = Runner(root, _price_data(["SPY", "BND", "GLD"]))
        assert len(runner._upward_order) == 2
        assert runner._upward_order[0] is w2  # deeper first
        assert runner._upward_order[1] is w1

    def test_if_else_nested_branches(self):
        # IfElseNode IE (depth 0) has true_branch=WeightNode W1 (depth 1), false_branch=AssetNode A1
        a1 = _asset("a1", "SPY")
        a2 = _asset("a2", "BND")
        a3 = _asset("a3", "GLD")
        w1 = _weight_equal("w1", [a2, a3])
        conditions = [{"lhs": {"asset": "SPY", "function": "cumulative_return", "lookback": 1},
                       "comparator": "greater_than", "rhs": 0.0, "duration": 1}]
        ie = _if_else("ie", conditions, "all", w1, a1)
        root = _root(ie)
        runner = Runner(root, _price_data(["SPY", "BND", "GLD"]))
        order_ids = [n.id for n in runner._upward_order]
        assert order_ids.index("w1") < order_ids.index("ie")
        assert "a1" not in order_ids

    def test_asset_nodes_excluded(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_equal("root", [spy, bnd])
        root = _root(node)
        runner = Runner(root, _price_data(["SPY", "BND"]))
        for n in runner._upward_order:
            assert not isinstance(n, AssetNode)


# ---------------------------------------------------------------------------
# 5.4  NAV pre-allocation
# ---------------------------------------------------------------------------

class TestNavPreAllocation:
    def test_nav_array_shape_and_values(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node, start="2024-01-02", end="2024-12-31")
        runner = Runner(root, _price_data(["SPY"]))
        nav = node.perm["nav_array"]
        assert isinstance(nav, np.ndarray)
        assert nav.shape == (len(runner._sim_dates),)
        assert np.all(nav == 1.0)

    def test_nested_strategy_nav_array_allocated(self):
        spy = _asset("spy", "SPY")
        inner = _weight_equal("inner", [spy])
        outer = _weight_equal("outer", [inner])
        root = _root(outer, start="2024-01-02", end="2024-03-29")
        runner = Runner(root, _price_data(["SPY"]))
        T = len(runner._sim_dates)
        assert inner.perm["nav_array"].shape == (T,)
        assert outer.perm["nav_array"].shape == (T,)

    def test_child_series_strategy_node_is_nav_view(self):
        spy = _asset("spy", "SPY")
        inner = _weight_equal("inner", [spy])
        outer = _weight_equal("outer", [inner])
        root = _root(outer)
        Runner(root, _price_data(["SPY"]))
        view = outer.perm["child_series"]["inner"]
        assert len(view) == 1
        assert view[0] == 1.0
        assert np.shares_memory(view, inner.perm["nav_array"])


# ---------------------------------------------------------------------------
# 5.5  Upward pass — WeightNode with two AssetNode children
# ---------------------------------------------------------------------------

class TestUpwardPassAssetChildren:
    def _build_runner(self, prices_a, prices_b, weights: dict):
        """Build a runner with known prices starting on start_date (no lookback)."""
        a = _asset("a", "A")
        b = _asset("b", "B")
        node = _weight_defined("root", [a, b], weights)
        start = "2024-01-02"
        n_days = len(prices_a)
        index = pd.bdate_range(start, periods=n_days)
        end = index[-1].strftime("%Y-%m-%d")
        price_data = pd.DataFrame({"A": prices_a, "B": prices_b}, index=index)
        root = _root(node, start=start, end=end)
        runner = Runner(root, price_data)
        return runner, node

    def test_nav_computation_day1(self):
        prices_a = [100.0, 102.0, 101.0]
        prices_b = [200.0, 198.0, 202.0]
        runner, node = self._build_runner(prices_a, prices_b, {"a": 0.6, "b": 0.4})

        node.temp["weights"] = {"a": 0.6, "b": 0.4}
        runner._upward_pass(1)

        ret_a = 102.0 / 100.0 - 1.0  # 0.02
        ret_b = 198.0 / 200.0 - 1.0  # -0.01
        expected = 1.0 * (1.0 + 0.6 * ret_a + 0.4 * ret_b)
        np.testing.assert_allclose(node.perm["nav_array"][1], expected)

    def test_nav_computation_day2(self):
        prices_a = [100.0, 102.0, 101.0]
        prices_b = [200.0, 198.0, 202.0]
        runner, node = self._build_runner(prices_a, prices_b, {"a": 0.6, "b": 0.4})

        node.temp["weights"] = {"a": 0.6, "b": 0.4}
        runner._upward_pass(1)
        runner._upward_pass(2)

        ret_a1 = 102.0 / 100.0 - 1.0
        ret_b1 = 198.0 / 200.0 - 1.0
        nav1 = 1.0 * (1.0 + 0.6 * ret_a1 + 0.4 * ret_b1)

        ret_a2 = 101.0 / 102.0 - 1.0
        ret_b2 = 202.0 / 198.0 - 1.0
        nav2 = nav1 * (1.0 + 0.6 * ret_a2 + 0.4 * ret_b2)
        np.testing.assert_allclose(node.perm["nav_array"][2], nav2)

    def test_single_child_full_weight(self):
        prices_a = [100.0, 102.0]
        prices_b = [200.0, 200.0]
        runner, node = self._build_runner(prices_a, prices_b, {"a": 1.0, "b": 0.0})

        node.temp["weights"] = {"a": 1.0}
        runner._upward_pass(1)

        expected = 1.0 * (1.0 + 0.02)
        np.testing.assert_allclose(node.perm["nav_array"][1], expected)


# ---------------------------------------------------------------------------
# 5.6  Upward pass — nested WeightNodes (StrategyNode child)
# ---------------------------------------------------------------------------

class TestUpwardPassStrategyChild:
    def test_child_nav_computed_before_parent(self):
        a = _asset("a", "A")
        b = _asset("b", "B")
        inner = _weight_defined("inner", [a], {"a": 1.0})
        outer = _weight_defined("outer", [inner, b], {"inner": 0.5, "b": 0.5})

        prices_a = [100.0, 110.0]
        prices_b = [50.0, 48.0]
        index = pd.bdate_range("2024-01-02", periods=2)
        price_data = pd.DataFrame({"A": prices_a, "B": prices_b}, index=index)
        root = _root(outer, start="2024-01-02", end="2024-01-03")
        runner = Runner(root, price_data)

        inner.temp["weights"] = {"a": 1.0}
        outer.temp["weights"] = {"inner": 0.5, "b": 0.5}
        runner._upward_pass(1)

        inner_ret = 110.0 / 100.0 - 1.0  # 0.1
        b_ret = 48.0 / 50.0 - 1.0        # -0.04
        inner_nav1 = 1.0 * (1.0 + inner_ret)
        np.testing.assert_allclose(inner.perm["nav_array"][1], inner_nav1)

        outer_ret = 0.5 * inner_ret + 0.5 * b_ret
        outer_nav1 = 1.0 * (1.0 + outer_ret)
        np.testing.assert_allclose(outer.perm["nav_array"][1], outer_nav1)


# ---------------------------------------------------------------------------
# 5.7  Upward pass — IfElseNode
# ---------------------------------------------------------------------------

class TestUpwardPassIfElse:
    def _build_runner_if_else(self):
        a_true = _asset("at", "SPY")
        a_false = _asset("af", "BND")
        conditions = [{"lhs": {"asset": "SPY", "function": "cumulative_return", "lookback": 1},
                       "comparator": "greater_than", "rhs": 0.0, "duration": 1}]
        true_branch = _weight_defined("tb", [a_true], {"at": 1.0})
        false_branch = _weight_defined("fb", [a_false], {"af": 1.0})
        ie = _if_else("ie", conditions, "all", true_branch, false_branch)

        # lookback=1 requires 1 trading day before start_date 2024-01-02.
        # bdate_range("2023-12-29", periods=5) = [Dec 29, Jan 1, Jan 2, Jan 3, Jan 4]
        # _price_offset = 2 (index of 2024-01-02), so:
        #   t_idx=1 returns: price[3]/price[2]-1 → SPY 103/100=0.03, BND 49/50=-0.02
        index = pd.bdate_range("2023-12-29", periods=5)
        prices = {
            "SPY": [99.0, 99.0, 100.0, 103.0, 102.0],
            "BND": [49.0, 49.0, 50.0, 49.0, 51.0],
        }
        price_data = pd.DataFrame(prices, index=index)
        root = _root(ie, start="2024-01-02", end="2024-01-04")
        runner = Runner(root, price_data)
        return runner, ie, true_branch, false_branch

    def test_both_branches_update_nav(self):
        runner, ie, tb, fb = self._build_runner_if_else()

        # Manually set weights as if Downward Pass ran
        tb.temp["weights"] = {"at": 1.0}
        fb.temp["weights"] = {"af": 1.0}
        ie.temp["weights"] = {"tb": 1.0}  # true branch is active

        runner._upward_pass(1)

        # Both branches should have updated NAV (not still 1.0)
        assert tb.perm["nav_array"][1] != 1.0
        assert fb.perm["nav_array"][1] != 1.0

    def test_if_else_uses_active_branch_return(self):
        runner, ie, tb, fb = self._build_runner_if_else()

        tb.temp["weights"] = {"at": 1.0}
        fb.temp["weights"] = {"af": 1.0}
        ie.temp["weights"] = {"tb": 1.0}  # true branch is active

        runner._upward_pass(1)

        # ie NAV should reflect true branch return (SPY: 103/100 - 1 = 0.03)
        expected_ie_nav = 1.0 * (1.0 + (103.0 / 100.0 - 1.0))
        np.testing.assert_allclose(ie.perm["nav_array"][1], expected_ie_nav)

    def test_if_else_false_branch_active(self):
        runner, ie, tb, fb = self._build_runner_if_else()

        tb.temp["weights"] = {"at": 1.0}
        fb.temp["weights"] = {"af": 1.0}
        ie.temp["weights"] = {"fb": 1.0}  # false branch is active

        runner._upward_pass(1)

        # ie NAV should reflect false branch return (BND: 49/50 - 1 = -0.02)
        expected_ie_nav = 1.0 * (1.0 + (49.0 / 50.0 - 1.0))
        np.testing.assert_allclose(ie.perm["nav_array"][1], expected_ie_nav)


# ---------------------------------------------------------------------------
# 5.8  XCASHX handling
# ---------------------------------------------------------------------------

class TestXCASHX:
    def _build_simple_runner(self, n_days: int = 3):
        spy = _asset("spy", "SPY")
        node = _weight_defined("root", [spy], {"spy": 1.0})
        index = pd.bdate_range("2024-01-02", periods=n_days)
        price_data = pd.DataFrame({"SPY": [100.0] * n_days}, index=index)
        end = index[-1].strftime("%Y-%m-%d")
        root = _root(node, start="2024-01-02", end=end)
        runner = Runner(root, price_data)
        return runner, node

    def test_full_xcashx_nav_unchanged(self):
        runner, node = self._build_simple_runner()
        node.temp["weights"] = {"XCASHX": 1.0}
        runner._upward_pass(1)
        assert node.perm["nav_array"][1] == 1.0

    def test_partial_xcashx_weighted_correctly(self):
        spy = _asset("spy", "SPY")
        node = _weight_defined("root", [spy], {"spy": 0.5})
        prices = [100.0, 102.0, 104.0]
        index = pd.bdate_range("2024-01-02", periods=3)
        price_data = pd.DataFrame({"SPY": prices}, index=index)
        root = _root(node, start="2024-01-02", end="2024-01-04")
        runner = Runner(root, price_data)

        node.temp["weights"] = {"spy": 0.5, "XCASHX": 0.5}
        runner._upward_pass(1)

        # SPY return = 102/100 - 1 = 0.02; XCASHX return = 0.0
        expected = 1.0 * (1.0 + 0.5 * 0.02 + 0.5 * 0.0)
        np.testing.assert_allclose(node.perm["nav_array"][1], expected)


# ---------------------------------------------------------------------------
# 5.9  child_series view update
# ---------------------------------------------------------------------------

class TestUpdateChildSeriesViews:
    def test_view_grows_after_upward_pass(self):
        spy = _asset("spy", "SPY")
        inner = _weight_defined("inner", [spy], {"spy": 1.0})
        outer = _weight_defined("outer", [inner], {"inner": 1.0})

        prices = [100.0 + i for i in range(8)]
        index = pd.bdate_range("2024-01-02", periods=8)
        price_data = pd.DataFrame({"SPY": prices}, index=index)
        root = _root(outer, start="2024-01-02", end="2024-01-11")
        runner = Runner(root, price_data)

        inner.temp["weights"] = {"spy": 1.0}
        outer.temp["weights"] = {"inner": 1.0}

        # Run upward pass for days 1–5
        for t in range(1, 6):
            runner._upward_pass(t)
            runner._update_child_series_views(t)

        view = outer.perm["child_series"]["inner"]
        assert len(view) == 6  # days 0–5

    def test_view_shares_memory_with_nav_array(self):
        spy = _asset("spy", "SPY")
        inner = _weight_defined("inner", [spy], {"spy": 1.0})
        outer = _weight_defined("outer", [inner], {"inner": 1.0})

        prices = [100.0 + i for i in range(5)]
        index = pd.bdate_range("2024-01-02", periods=5)
        price_data = pd.DataFrame({"SPY": prices}, index=index)
        root = _root(outer, start="2024-01-02", end="2024-01-08")
        runner = Runner(root, price_data)

        inner.temp["weights"] = {"spy": 1.0}
        outer.temp["weights"] = {"inner": 1.0}

        runner._upward_pass(1)
        runner._update_child_series_views(1)

        view = outer.perm["child_series"]["inner"]
        assert np.shares_memory(view, inner.perm["nav_array"])


# ---------------------------------------------------------------------------
# 5.10  Integration — Runner.run() with daily rebalance
# ---------------------------------------------------------------------------

class TestRunIntegration:
    def test_run_5_days_correct_nav(self):
        a = _asset("a", "A")
        b = _asset("b", "B")
        node = _weight_defined("root", [a, b], {"a": 0.6, "b": 0.4})

        prices_a = [100.0, 101.0, 103.0, 102.0, 104.0, 105.0]
        prices_b = [50.0, 51.0, 50.5, 51.5, 52.0, 51.0]
        index = pd.bdate_range("2024-01-02", periods=6)
        end = index[-1].strftime("%Y-%m-%d")
        price_data = pd.DataFrame({"A": prices_a, "B": prices_b}, index=index)
        root = _root(node, start="2024-01-02", end=end)
        runner = Runner(root, price_data)

        # Simulate Downward Pass on day 0 by manually setting weights
        node.temp["weights"] = {"a": 0.6, "b": 0.4}
        runner.run()

        # Verify NAV compounded correctly each day
        nav = node.perm["nav_array"]
        assert nav[0] == 1.0  # day 0 unchanged
        expected = 1.0
        for t in range(1, 6):
            ret_a = prices_a[t] / prices_a[t - 1] - 1.0
            ret_b = prices_b[t] / prices_b[t - 1] - 1.0
            expected *= 1.0 + 0.6 * ret_a + 0.4 * ret_b
            np.testing.assert_allclose(nav[t], expected, rtol=1e-10)

    def test_run_returns_none(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        prices = [100.0 + i for i in range(3)]
        index = pd.bdate_range("2024-01-02", periods=3)
        price_data = pd.DataFrame({"SPY": prices}, index=index)
        root = _root(node, start="2024-01-02", end="2024-01-04")
        runner = Runner(root, price_data)
        node.temp["weights"] = {"spy": 1.0}
        assert runner.run() is None


# ---------------------------------------------------------------------------
# 5.11  Integration — rebalance gating (weekly)
# ---------------------------------------------------------------------------

class TestRebalanceGating:
    def test_nav_correct_with_weekly_carry_forward(self):
        """NAV must be correct on all days, including non-rebalance days where weights carry forward."""
        a = _asset("a", "A")
        b = _asset("b", "B")
        node = _weight_defined("root", [a, b], {"a": 0.5, "b": 0.5})

        # 7 trading days: Mon Jan 8 – Tue Jan 16 (spans 2 ISO weeks)
        # Week 2: Jan 8–12; Week 3: Jan 15, 16
        index = pd.bdate_range("2024-01-08", periods=7)
        prices_a = [100.0, 101.0, 99.0, 102.0, 103.0, 104.0, 105.0]
        prices_b = [50.0, 50.5, 51.0, 50.0, 49.5, 51.0, 52.0]
        price_data = pd.DataFrame({"A": prices_a, "B": prices_b}, index=index)
        end = index[-1].strftime("%Y-%m-%d")
        root = _root(node, start="2024-01-08", end=end, frequency="weekly")
        runner = Runner(root, price_data)

        # Simulate Downward Pass on day 0 (always a rebalance day)
        node.temp["weights"] = {"a": 0.5, "b": 0.5}
        runner.run()

        # Weights carry forward — NAV should compound with 50/50 allocation every day
        nav = node.perm["nav_array"]
        assert nav[0] == 1.0
        expected = 1.0
        for t in range(1, 7):
            ret_a = prices_a[t] / prices_a[t - 1] - 1.0
            ret_b = prices_b[t] / prices_b[t - 1] - 1.0
            expected *= 1.0 + 0.5 * ret_a + 0.5 * ret_b
            np.testing.assert_allclose(nav[t], expected, rtol=1e-10)

    def test_non_rebalance_days_weights_not_cleared(self):
        """Weights from day 0 persist through non-rebalance days."""
        spy = _asset("spy", "SPY")
        node = _weight_defined("root", [spy], {"spy": 1.0})

        index = pd.bdate_range("2024-01-08", periods=5)  # Mon–Fri week 2
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        price_data = pd.DataFrame({"SPY": prices}, index=index)
        end = index[-1].strftime("%Y-%m-%d")
        root = _root(node, start="2024-01-08", end=end, frequency="weekly")
        runner = Runner(root, price_data)

        node.temp["weights"] = {"spy": 1.0}
        runner.run()

        # After run, weights should still be intact (not cleared)
        assert node.temp["weights"] == {"spy": 1.0}
