"""Tests for Runner.__init__ (E1) — AlgoStack attachment, child_series, validation."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from moa_allocations.engine import PriceDataError, Runner
from moa_allocations.engine.algos import (
    SelectAll,
    SelectBottomN,
    SelectIfCondition,
    SelectTopN,
    WeightEqually,
    WeightInvVol,
    WeightSpecified,
)
from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, WeightNode
from moa_allocations.engine.runner import compute_max_lookback
from moa_allocations.engine.strategy import RootNode, Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRADING_DAYS = pd.bdate_range("2023-01-02", "2024-12-31")  # ~521 trading days


def _settings(start: str = "2024-01-02", end: str = "2024-06-28") -> Settings:
    return Settings(
        id="test",
        name="test",
        starting_cash=100_000.0,
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
        slippage=0.0,
        fees=0.0,
        rebalance_frequency="daily",
        rebalance_threshold=None,
    )


def _price_data(tickers: list[str], index=_TRADING_DAYS) -> pd.DataFrame:
    rng = np.random.default_rng(0)
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


def _weight_invvol(id: str, children: list, lookback: int) -> WeightNode:
    return WeightNode(id=id, method="inverse_volatility", method_params={"lookback": lookback}, children=children)


def _filter_top(id: str, children: list, n: int, metric: str, lookback: int) -> FilterNode:
    return FilterNode(
        id=id,
        sort_by={"function": metric, "lookback": lookback},
        select={"mode": "top", "count": n},
        children=children,
    )


def _filter_bottom(id: str, children: list, n: int, metric: str, lookback: int) -> FilterNode:
    return FilterNode(
        id=id,
        sort_by={"function": metric, "lookback": lookback},
        select={"mode": "bottom", "count": n},
        children=children,
    )


def _if_else(id: str, conditions: list, logic_mode: str, true_branch, false_branch) -> IfElseNode:
    return IfElseNode(
        id=id,
        logic_mode=logic_mode,
        conditions=conditions,
        true_branch=true_branch,
        false_branch=false_branch,
    )


def _root(root_node, start: str = "2024-01-02", end: str = "2024-06-28") -> RootNode:
    return RootNode(settings=_settings(start, end), root=root_node, dsl_version="1.0.0")


# ---------------------------------------------------------------------------
# 7.1  PriceDataError — missing tickers
# ---------------------------------------------------------------------------

class TestMissingTickers:
    def test_single_missing_ticker(self):
        spy = _asset("spy", "SPY")
        gld = _asset("gld", "GLD")
        node = _weight_equal("root", [spy, gld])
        root = _root(node)
        price_data = _price_data(["SPY"])  # GLD missing
        with pytest.raises(PriceDataError, match="GLD"):
            Runner(root, price_data)

    def test_multiple_missing_tickers(self):
        spy = _asset("spy", "SPY")
        gld = _asset("gld", "GLD")
        tlt = _asset("tlt", "TLT")
        node = _weight_equal("root", [spy, gld, tlt])
        root = _root(node)
        price_data = _price_data(["SPY"])  # GLD and TLT missing
        with pytest.raises(PriceDataError) as exc_info:
            Runner(root, price_data)
        msg = str(exc_info.value)
        assert "GLD" in msg
        assert "TLT" in msg

    def test_all_tickers_present_no_error(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_equal("root", [spy, bnd])
        root = _root(node)
        Runner(root, _price_data(["SPY", "BND"]))  # no exception


# ---------------------------------------------------------------------------
# 7.2  PriceDataError — insufficient lookback history
# ---------------------------------------------------------------------------

class TestInsufficientHistory:
    def test_zero_lookback_price_data_starts_after_start_date(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])  # no lookback — max_lookback == 0
        root = _root(node, start="2024-01-02", end="2024-06-28")
        late_index = pd.bdate_range("2024-02-01", "2024-12-31")
        with pytest.raises(PriceDataError, match="start_date"):
            Runner(root, _price_data(["SPY"], index=late_index))

    def test_price_data_starts_too_late(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _filter_top("root", [spy, bnd], n=1, metric="cumulative_return", lookback=200)
        root = _root(node, start="2024-01-02", end="2024-06-28")
        # Only ~65 trading days before 2024-01-02 in this range — not enough for lookback=200
        short_index = pd.bdate_range("2023-10-01", "2024-06-28")
        price_data = _price_data(["SPY", "BND"], index=short_index)
        with pytest.raises(PriceDataError, match="Insufficient price history"):
            Runner(root, price_data)

    def test_sufficient_history_no_error(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _filter_top("root", [spy, bnd], n=1, metric="cumulative_return", lookback=50)
        root = _root(node, start="2024-01-02", end="2024-06-28")
        # _TRADING_DAYS starts 2023-01-02 — plenty of history before 2024-01-02
        Runner(root, _price_data(["SPY", "BND"]))  # no exception


# ---------------------------------------------------------------------------
# 7.3  PriceDataError — price data ends before end_date
# ---------------------------------------------------------------------------

class TestEndDateCoverage:
    def test_price_data_ends_too_early(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node, start="2024-01-02", end="2024-12-31")
        # _TRADING_DAYS ends 2024-12-31 — but we'll trim it
        short_index = pd.bdate_range("2023-01-02", "2024-11-30")
        with pytest.raises(PriceDataError, match="end_date"):
            Runner(root, _price_data(["SPY"], index=short_index))

    def test_price_data_covers_end_date_no_error(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node, start="2024-01-02", end="2024-06-28")
        Runner(root, _price_data(["SPY"]))  # _TRADING_DAYS ends 2024-12-31 — fine


# ---------------------------------------------------------------------------
# 7.4  AlgoStack attachment — correct types per node class/method
# ---------------------------------------------------------------------------

class TestAlgoStackAttachment:
    def _build_and_run(self, root_node, tickers):
        root = _root(root_node)
        runner = Runner(root, _price_data(tickers))
        return root_node

    def test_weight_equal(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        self._build_and_run(node, ["SPY"])
        assert isinstance(node.algo_stack[0], SelectAll)
        assert isinstance(node.algo_stack[1], WeightEqually)
        assert len(node.algo_stack) == 2

    def test_weight_defined(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_defined("root", [spy, bnd], {"spy": 0.6, "bnd": 0.4})
        self._build_and_run(node, ["SPY", "BND"])
        assert isinstance(node.algo_stack[0], SelectAll)
        assert isinstance(node.algo_stack[1], WeightSpecified)

    def test_weight_invvol(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_invvol("root", [spy, bnd], lookback=60)
        self._build_and_run(node, ["SPY", "BND"])
        assert isinstance(node.algo_stack[0], SelectAll)
        assert isinstance(node.algo_stack[1], WeightInvVol)

    def test_filter_top(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _filter_top("root", [spy, bnd], n=1, metric="cumulative_return", lookback=20)
        self._build_and_run(node, ["SPY", "BND"])
        assert isinstance(node.algo_stack[0], SelectTopN)
        assert isinstance(node.algo_stack[1], WeightEqually)

    def test_filter_bottom(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _filter_bottom("root", [spy, bnd], n=1, metric="std_dev_return", lookback=60)
        self._build_and_run(node, ["SPY", "BND"])
        assert isinstance(node.algo_stack[0], SelectBottomN)
        assert isinstance(node.algo_stack[1], WeightEqually)

    def test_if_else(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        conditions = [{"lhs": {"asset": "SPY", "function": "cumulative_return", "lookback": 20},
                       "comparator": "greater_than", "rhs": 0.0, "duration": 1}]
        node = _if_else("root", conditions, "all", spy, bnd)
        root = _root(node)
        Runner(root, _price_data(["SPY", "BND"]))
        assert isinstance(node.algo_stack[0], SelectIfCondition)
        assert isinstance(node.algo_stack[1], WeightEqually)


# ---------------------------------------------------------------------------
# 7.5  AssetNode leaves — no algo_stack set by Runner
# ---------------------------------------------------------------------------

class TestAssetNodeNoAlgoStack:
    def test_asset_node_algo_stack_unchanged(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node)
        Runner(root, _price_data(["SPY"]))
        # AssetNode should not have algo_stack set
        assert not hasattr(spy, "algo_stack") or spy.algo_stack == []


# ---------------------------------------------------------------------------
# 7.6  child_series — AssetNode child gets correct numpy array
# ---------------------------------------------------------------------------

class TestChildSeriesAsset:
    def test_asset_child_series_matches_price_data(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_equal("root", [spy, bnd])
        root = _root(node)
        price_data = _price_data(["SPY", "BND"])
        Runner(root, price_data)
        np.testing.assert_array_equal(
            node.perm["child_series"]["spy"], price_data["SPY"].to_numpy()
        )
        np.testing.assert_array_equal(
            node.perm["child_series"]["bnd"], price_data["BND"].to_numpy()
        )


# ---------------------------------------------------------------------------
# child_series — IfElseNode condition-referenced ticker arrays
# ---------------------------------------------------------------------------

class TestChildSeriesIfElseConditionAssets:
    def test_condition_lhs_asset_series_populated(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        conditions = [{"lhs": {"asset": "SPY", "function": "cumulative_return", "lookback": 20},
                       "comparator": "greater_than", "rhs": 0.0, "duration": 1}]
        node = _if_else("root", conditions, "all", spy, bnd)
        root = _root(node)
        price_data = _price_data(["SPY", "BND"])
        Runner(root, price_data)
        arr = node.perm["child_series"]["SPY"]
        assert isinstance(arr, np.ndarray)
        np.testing.assert_array_equal(arr, price_data["SPY"].to_numpy())

    def test_condition_rhs_asset_series_populated(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        conditions = [{"lhs": {"asset": "SPY", "function": "sma_price", "lookback": 50},
                       "comparator": "greater_than",
                       "rhs": {"asset": "BND", "function": "sma_price", "lookback": 50},
                       "duration": 1}]
        node = _if_else("root", conditions, "all", spy, bnd)
        root = _root(node)
        price_data = _price_data(["SPY", "BND"])
        Runner(root, price_data)
        np.testing.assert_array_equal(
            node.perm["child_series"]["SPY"], price_data["SPY"].to_numpy()
        )
        np.testing.assert_array_equal(
            node.perm["child_series"]["BND"], price_data["BND"].to_numpy()
        )


# ---------------------------------------------------------------------------
# 7.7  child_series — StrategyNode child gets nav_array[:1] view (E2)
# ---------------------------------------------------------------------------

class TestChildSeriesStrategyPlaceholder:
    def test_strategy_child_series_is_nav_array_view(self):
        spy = _asset("spy", "SPY")
        inner = _weight_equal("inner", [spy])
        outer = _weight_equal("outer", [inner])
        root = _root(outer)
        Runner(root, _price_data(["SPY"]))
        placeholder = outer.perm["child_series"]["inner"]
        assert isinstance(placeholder, np.ndarray)
        assert len(placeholder) == 1
        assert placeholder[0] == 1.0
        # Must share memory with inner's nav_array (is a view, not a copy)
        assert np.shares_memory(placeholder, inner.perm["nav_array"])


# ---------------------------------------------------------------------------
# 7.8  compute_max_lookback — maximum across mixed node types
# ---------------------------------------------------------------------------

class TestComputeMaxLookback:
    def test_max_from_filter_node(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _filter_top("root", [spy, bnd], n=1, metric="cumulative_return", lookback=20)
        assert compute_max_lookback(_root(node)) == 20

    def test_max_from_invvol_node(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_invvol("root", [spy, bnd], lookback=60)
        assert compute_max_lookback(_root(node)) == 60

    def test_max_from_if_else_condition(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        conditions = [{"lhs": {"asset": "SPY", "function": "sma_price", "lookback": 200},
                       "comparator": "greater_than", "rhs": 0.0, "duration": 1}]
        node = _if_else("root", conditions, "all", spy, bnd)
        assert compute_max_lookback(_root(node)) == 200

    def test_max_across_mixed_nodes(self):
        # FilterNode=20, WeightNode(invvol)=60, IfElseNode condition=200 → max is 200
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        gld = _asset("gld", "GLD")
        tlt = _asset("tlt", "TLT")
        filter_node = _filter_top("filter", [spy, bnd], n=1, metric="cumulative_return", lookback=20)
        conditions = [{"lhs": {"asset": "SPY", "function": "sma_price", "lookback": 200},
                       "comparator": "greater_than", "rhs": 0.0, "duration": 1}]
        if_node = _if_else("if", conditions, "all", gld, tlt)
        outer = _weight_invvol("outer", [filter_node, if_node], lookback=60)
        assert compute_max_lookback(_root(outer)) == 200

    def test_no_lookback_returns_zero(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        assert compute_max_lookback(_root(node)) == 0
