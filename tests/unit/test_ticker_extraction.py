"""Tests for collect_traded_tickers and collect_signal_tickers."""
from __future__ import annotations

from datetime import date

import pytest

from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, WeightNode
from moa_allocations.engine.runner import collect_signal_tickers, collect_traded_tickers
from moa_allocations.engine.strategy import RootNode, Settings


def _settings() -> Settings:
    return Settings(
        id="test",
        name="test",
        starting_cash=100_000.0,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 6, 28),
        slippage=0.0,
        fees=0.0,
        rebalance_frequency="daily",
        rebalance_threshold=None,
    )


def _root(node) -> RootNode:
    return RootNode(settings=_settings(), root=node, dsl_version="1.0.0")


def _asset(id: str, ticker: str) -> AssetNode:
    return AssetNode(id=id, ticker=ticker)


def _weight_equal(id: str, children: list) -> WeightNode:
    return WeightNode(id=id, method="equal", method_params={}, children=children)


class TestCollectTradedTickers:
    def test_simple_weight_tree(self):
        root = _root(
            _weight_equal("w1", [_asset("a1", "SPY"), _asset("a2", "TLT")])
        )
        assert collect_traded_tickers(root) == {"SPY", "TLT"}

    def test_excludes_xcashx(self):
        root = _root(
            _weight_equal("w1", [_asset("a1", "SPY"), _asset("a2", "XCASHX")])
        )
        assert collect_traded_tickers(root) == {"SPY"}

    def test_does_not_include_condition_tickers(self):
        root = _root(
            IfElseNode(
                id="ie1",
                logic_mode="all",
                conditions=[{"lhs": {"asset": "VIXY"}, "comparator": "greater_than", "rhs": 0}],
                true_branch=_asset("a1", "SPY"),
                false_branch=_asset("a2", "TLT"),
            )
        )
        assert collect_traded_tickers(root) == {"SPY", "TLT"}
        assert "VIXY" not in collect_traded_tickers(root)

    def test_nested_tree(self):
        root = _root(
            _weight_equal("w1", [
                _asset("a1", "SPY"),
                _weight_equal("w2", [_asset("a2", "TLT"), _asset("a3", "GLD")]),
            ])
        )
        assert collect_traded_tickers(root) == {"SPY", "TLT", "GLD"}


class TestCollectSignalTickers:
    def test_no_conditions(self):
        root = _root(
            _weight_equal("w1", [_asset("a1", "SPY"), _asset("a2", "TLT")])
        )
        assert collect_signal_tickers(root) == set()

    def test_signal_ticker_not_traded(self):
        root = _root(
            IfElseNode(
                id="ie1",
                logic_mode="all",
                conditions=[{"lhs": {"asset": "VIXY"}, "comparator": "greater_than", "rhs": 0}],
                true_branch=_asset("a1", "SPY"),
                false_branch=_asset("a2", "TLT"),
            )
        )
        assert collect_signal_tickers(root) == {"VIXY"}

    def test_condition_ticker_also_traded(self):
        root = _root(
            IfElseNode(
                id="ie1",
                logic_mode="all",
                conditions=[{"lhs": {"asset": "SPY"}, "comparator": "greater_than", "rhs": 0}],
                true_branch=_asset("a1", "SPY"),
                false_branch=_asset("a2", "TLT"),
            )
        )
        assert collect_signal_tickers(root) == set()

    def test_rhs_signal_ticker(self):
        root = _root(
            IfElseNode(
                id="ie1",
                logic_mode="all",
                conditions=[{
                    "lhs": {"asset": "SPY"},
                    "comparator": "greater_than",
                    "rhs": {"asset": "QQQ"},
                }],
                true_branch=_asset("a1", "SPY"),
                false_branch=_asset("a2", "TLT"),
            )
        )
        assert collect_signal_tickers(root) == {"QQQ"}

    def test_excludes_xcashx_from_signal(self):
        root = _root(
            IfElseNode(
                id="ie1",
                logic_mode="all",
                conditions=[{"lhs": {"asset": "XCASHX"}, "comparator": "greater_than", "rhs": 0}],
                true_branch=_asset("a1", "SPY"),
                false_branch=_asset("a2", "TLT"),
            )
        )
        assert collect_signal_tickers(root) == set()
