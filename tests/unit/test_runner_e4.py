"""Tests for Runner E4 — global weight vector + output assembly."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from moa_allocations.engine import Runner
from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, StrategyNode, WeightNode
from moa_allocations.engine.strategy import RootNode, Settings


# ---------------------------------------------------------------------------
# Helpers (mirrors test_runner_e2.py)
# ---------------------------------------------------------------------------

_TRADING_DAYS = pd.bdate_range("2023-01-02", "2024-12-31")


def _settings(start: str = "2024-01-02", end: str = "2024-06-28", frequency: str = "daily") -> Settings:
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


def _root(root_node, start: str = "2024-01-02", end: str = "2024-06-28", frequency: str = "daily") -> RootNode:
    return RootNode(settings=_settings(start, end, frequency), root=root_node, dsl_version="1.0.0")


# ---------------------------------------------------------------------------
# 6.1  _flatten_weights — simple two-level equal-weight tree
# ---------------------------------------------------------------------------

class TestFlattenWeightsSimple:
    def test_two_leaves_equal_weight(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_equal("root", [spy, bnd])
        root = _root(node)
        runner = Runner(root, _price_data(["SPY", "BND"]))

        node.temp["weights"] = {"spy": 0.5, "bnd": 0.5}
        result = runner._flatten_weights()

        assert abs(result["SPY"] - 0.5) < 1e-12
        assert abs(result["BND"] - 0.5) < 1e-12
        assert "XCASHX" not in result

    def test_single_leaf_full_weight(self):
        spy = _asset("spy", "SPY")
        node = _weight_defined("root", [spy], {"spy": 1.0})
        root = _root(node)
        runner = Runner(root, _price_data(["SPY"]))

        node.temp["weights"] = {"spy": 1.0}
        result = runner._flatten_weights()

        assert abs(result["SPY"] - 1.0) < 1e-12


# ---------------------------------------------------------------------------
# 6.2  _flatten_weights — nested weight nodes (3 levels)
# ---------------------------------------------------------------------------

class TestFlattenWeightsNested:
    def test_three_level_tree(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        gld = _asset("gld", "GLD")
        inner = _weight_defined("inner", [spy, bnd], {"spy": 0.5, "bnd": 0.5})
        outer = _weight_defined("outer", [inner, gld], {"inner": 0.6, "gld": 0.4})
        root = _root(outer)
        runner = Runner(root, _price_data(["SPY", "BND", "GLD"]))

        inner.temp["weights"] = {"spy": 0.5, "bnd": 0.5}
        outer.temp["weights"] = {"inner": 0.6, "gld": 0.4}
        result = runner._flatten_weights()

        assert abs(result["SPY"] - 0.3) < 1e-12
        assert abs(result["BND"] - 0.3) < 1e-12
        assert abs(result["GLD"] - 0.4) < 1e-12
        assert abs(sum(result.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# 6.3  _flatten_weights — if_else node (only selected branch)
# ---------------------------------------------------------------------------

class TestFlattenWeightsIfElse:
    def _build(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        conditions = [{"lhs": {"asset": "SPY", "function": "cumulative_return", "lookback": 1},
                       "comparator": "greater_than", "rhs": 0.0, "duration": 1}]
        ie = IfElseNode(id="ie", logic_mode="all", conditions=conditions,
                        true_branch=spy, false_branch=bnd)
        # lookback=1 needs 1 day before start; start=Jan 2, end=Jan 4
        index = pd.bdate_range("2023-12-29", periods=5)
        prices = {"SPY": [100.0] * 5, "BND": [100.0] * 5}
        price_data = pd.DataFrame(prices, index=index)
        root = _root(ie, start="2024-01-02", end="2024-01-04")
        runner = Runner(root, price_data)
        return runner, ie, spy, bnd

    def test_true_branch_selected(self):
        runner, ie, spy, bnd = self._build()
        ie.temp["weights"] = {"spy": 1.0}
        result = runner._flatten_weights()

        assert abs(result["SPY"] - 1.0) < 1e-12
        assert result.get("BND", 0.0) == 0.0

    def test_false_branch_selected(self):
        runner, ie, spy, bnd = self._build()
        ie.temp["weights"] = {"bnd": 1.0}
        result = runner._flatten_weights()

        assert abs(result["BND"] - 1.0) < 1e-12
        assert result.get("SPY", 0.0) == 0.0


# ---------------------------------------------------------------------------
# 6.4  _flatten_weights — XCASHX from AlgoStack halt
# ---------------------------------------------------------------------------

class TestFlattenWeightsXCASHX:
    def test_full_xcashx(self):
        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        root = _root(node)
        runner = Runner(root, _price_data(["SPY"]))

        node.temp["weights"] = {"XCASHX": 1.0}
        result = runner._flatten_weights()

        assert abs(result["XCASHX"] - 1.0) < 1e-12
        assert "SPY" not in result

    def test_partial_xcashx(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        inner = _weight_defined("inner", [spy], {"spy": 1.0})
        outer = _weight_defined("outer", [inner, bnd], {"inner": 0.6, "bnd": 0.4})
        root = _root(outer)
        runner = Runner(root, _price_data(["SPY", "BND"]))

        # inner goes XCASHX, bnd gets 0.4
        inner.temp["weights"] = {"XCASHX": 1.0}
        outer.temp["weights"] = {"inner": 0.6, "bnd": 0.4}
        result = runner._flatten_weights()

        assert abs(result["XCASHX"] - 0.6) < 1e-12
        assert abs(result["BND"] - 0.4) < 1e-12
        assert abs(sum(result.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# 6.5  Sum-to-one assertion fires on invalid weights
# ---------------------------------------------------------------------------

class TestSumToOneAssertion:
    def test_assertion_fires_when_sum_wrong(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_equal("root", [spy, bnd])
        root = _root(node)
        runner = Runner(root, _price_data(["SPY", "BND"]))

        # Weights that don't sum to 1.0
        node.temp["weights"] = {"spy": 0.4, "bnd": 0.4}  # sum = 0.8
        with pytest.raises(AssertionError):
            runner._flatten_weights()


# ---------------------------------------------------------------------------
# 6.6  Carry-forward on non-rebalance day (weekly frequency)
# ---------------------------------------------------------------------------

class TestCarryForward:
    def test_weekly_carry_forward_rows(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_defined("root", [spy, bnd], {"spy": 0.6, "bnd": 0.4})

        # Mon Jan 8 – Fri Jan 12 (one ISO week): only day 0 is a rebalance day
        index = pd.bdate_range("2024-01-08", periods=5)
        price_data = pd.DataFrame(
            {"SPY": [100.0] * 5, "BND": [50.0] * 5}, index=index
        )
        root = _root(node, start="2024-01-08", end="2024-01-12", frequency="weekly")
        runner = Runner(root, price_data)

        node.temp["weights"] = {"spy": 0.6, "bnd": 0.4}
        df = runner.run()

        # All 5 rows should have the same SPY/BND weights (carried forward)
        assert len(df) == 5
        for _, row in df.iterrows():
            assert abs(row["SPY"] - 0.6) < 1e-12
            assert abs(row["BND"] - 0.4) < 1e-12


# ---------------------------------------------------------------------------
# 6.7  DataFrame column order
# ---------------------------------------------------------------------------

class TestDataFrameColumnOrder:
    def test_date_first_then_tickers_in_dsl_order(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        gld = _asset("gld", "GLD")
        node = _weight_equal("root", [spy, bnd, gld])
        root = _root(node)
        runner = Runner(root, _price_data(["SPY", "BND", "GLD"]))

        node.temp["weights"] = {"spy": 1 / 3, "bnd": 1 / 3, "gld": 1 / 3}
        df = runner.run()

        assert list(df.columns[:4]) == ["DATE", "SPY", "BND", "GLD"]

    def test_xcashx_last_when_present(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_equal("root", [spy, bnd])
        root = _root(node)
        runner = Runner(root, _price_data(["SPY", "BND"]))

        class _AlwaysFalse(BaseAlgo):
            def __call__(self, target: StrategyNode) -> bool:
                return False

        runner._strategy_nodes["root"].algo_stack = [_AlwaysFalse()]
        df = runner.run()

        assert df.columns[-1] == "XCASHX"
        assert list(df.columns) == ["DATE", "SPY", "BND", "XCASHX"]


# ---------------------------------------------------------------------------
# 6.8  XCASHX column absent when never triggered
# ---------------------------------------------------------------------------

class TestXCASHXAbsent:
    def test_xcashx_not_in_columns(self):
        spy = _asset("spy", "SPY")
        bnd = _asset("bnd", "BND")
        node = _weight_defined("root", [spy, bnd], {"spy": 0.7, "bnd": 0.3})

        index = pd.bdate_range("2024-01-02", periods=3)
        price_data = pd.DataFrame({"SPY": [100.0] * 3, "BND": [50.0] * 3}, index=index)
        root = _root(node, start="2024-01-02", end="2024-01-04")
        runner = Runner(root, price_data)

        node.temp["weights"] = {"spy": 0.7, "bnd": 0.3}
        df = runner.run()

        assert "XCASHX" not in df.columns


# ---------------------------------------------------------------------------
# 6.9  CSV written to output/allocations.csv
# ---------------------------------------------------------------------------

class TestCSVOutput:
    def test_csv_written(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        index = pd.bdate_range("2024-01-02", periods=3)
        price_data = pd.DataFrame({"SPY": [100.0, 101.0, 102.0]}, index=index)
        root = _root(node, start="2024-01-02", end="2024-01-04")
        runner = Runner(root, price_data)

        node.temp["weights"] = {"spy": 1.0}
        runner.run()

        csv_path = tmp_path / "output" / "allocations.csv"
        assert csv_path.exists()
        loaded = pd.read_csv(csv_path)
        assert list(loaded.columns) == ["DATE", "SPY"]
        assert len(loaded) == 3

    def test_csv_no_index_column(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        index = pd.bdate_range("2024-01-02", periods=2)
        price_data = pd.DataFrame({"SPY": [100.0, 101.0]}, index=index)
        root = _root(node, start="2024-01-02", end="2024-01-03")
        runner = Runner(root, price_data)

        node.temp["weights"] = {"spy": 1.0}
        runner.run()

        loaded = pd.read_csv(tmp_path / "output" / "allocations.csv")
        # If index=False, first column is DATE not Unnamed: 0
        assert loaded.columns[0] == "DATE"

    def test_output_dir_created_if_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / "output").exists()

        spy = _asset("spy", "SPY")
        node = _weight_equal("root", [spy])
        index = pd.bdate_range("2024-01-02", periods=2)
        price_data = pd.DataFrame({"SPY": [100.0, 101.0]}, index=index)
        root = _root(node, start="2024-01-02", end="2024-01-03")
        runner = Runner(root, price_data)

        node.temp["weights"] = {"spy": 1.0}
        runner.run()

        assert (tmp_path / "output").is_dir()
