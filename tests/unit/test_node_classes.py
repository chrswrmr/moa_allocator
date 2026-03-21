from datetime import date

import pytest

from moa_allocations.engine.node import (
    AssetNode,
    BaseNode,
    FilterNode,
    IfElseNode,
    StrategyNode,
    WeightNode,
)
from moa_allocations.engine.strategy import RootNode, Settings
from moa_allocations.exceptions import DSLValidationError, PriceDataError


# --- BaseNode ---

def test_base_node_id_and_name():
    node = BaseNode(id="abc", name="My Node")
    assert node.id == "abc"
    assert node.name == "My Node"


def test_base_node_name_defaults_to_none():
    node = BaseNode(id="abc")
    assert node.name is None


# --- StrategyNode ---

def test_strategy_node_initialises_with_empty_state():
    node = StrategyNode(id="s1")
    assert node.temp == {}
    assert node.perm == {}
    assert node.algo_stack == []


def test_strategy_node_state_not_shared():
    a = StrategyNode(id="a")
    b = StrategyNode(id="b")
    a.temp["x"] = 1
    assert "x" not in b.temp


# --- IfElseNode ---

def test_if_else_node_holds_branches():
    true_branch = AssetNode(id="t", ticker="SPY")
    false_branch = AssetNode(id="f", ticker="BND")
    node = IfElseNode(
        id="ie1",
        logic_mode="all",
        conditions=[{"lhs": {}, "comparator": "greater_than", "rhs": 0}],
        true_branch=true_branch,
        false_branch=false_branch,
    )
    assert node.logic_mode == "all"
    assert node.conditions is not None
    assert node.true_branch is true_branch
    assert node.false_branch is false_branch


# --- WeightNode ---

def test_weight_node_holds_method_and_children():
    child = AssetNode(id="c1", ticker="SPY")
    node = WeightNode(id="w1", method="equal", method_params={}, children=[child])
    assert node.method == "equal"
    assert node.method_params == {}
    assert node.children == [child]


# --- FilterNode ---

def test_filter_node_holds_sort_by_select_children():
    child = AssetNode(id="c1", ticker="SPY")
    node = FilterNode(
        id="f1",
        sort_by={"function": "rsi", "lookback": "14d"},
        select={"mode": "top", "count": 1},
        children=[child],
    )
    assert node.sort_by["function"] == "rsi"
    assert node.select["mode"] == "top"
    assert node.children == [child]


# --- AssetNode ---

def test_asset_node_holds_ticker():
    node = AssetNode(id="a1", ticker="SPY")
    assert node.ticker == "SPY"


def test_asset_node_has_no_algo_stack():
    node = AssetNode(id="a1", ticker="SPY")
    assert not hasattr(node, "algo_stack")
    assert not hasattr(node, "temp")
    assert not hasattr(node, "perm")


# --- Settings ---

def test_settings_holds_all_fields():
    s = Settings(
        id="s1",
        name="Test Strategy",
        starting_cash=100000.0,
        start_date=date(2020, 1, 1),
        end_date=date(2024, 1, 1),
        slippage=0.0005,
        fees=0.0,
        rebalance_frequency="monthly",
        rebalance_threshold=None,
    )
    assert s.id == "s1"
    assert s.name == "Test Strategy"
    assert s.starting_cash == 100000.0
    assert s.start_date == date(2020, 1, 1)
    assert s.end_date == date(2024, 1, 1)
    assert s.slippage == 0.0005
    assert s.fees == 0.0
    assert s.rebalance_frequency == "monthly"
    assert s.rebalance_threshold is None


# --- RootNode ---

def test_root_node_holds_settings_root_and_dsl_version():
    settings = Settings(
        id="s1", name="Test", starting_cash=100000.0,
        start_date=date(2020, 1, 1), end_date=date(2024, 1, 1),
        slippage=0.0, fees=0.0, rebalance_frequency="daily",
        rebalance_threshold=None,
    )
    root = AssetNode(id="a1", ticker="SPY")
    rn = RootNode(settings=settings, root=root, dsl_version="1.0.0")
    assert rn.settings is settings
    assert rn.root is root
    assert rn.dsl_version == "1.0.0"


def test_root_node_is_not_a_base_node_subclass():
    settings = Settings(
        id="s1", name="Test", starting_cash=100000.0,
        start_date=date(2020, 1, 1), end_date=date(2024, 1, 1),
        slippage=0.0, fees=0.0, rebalance_frequency="daily",
        rebalance_threshold=None,
    )
    root = AssetNode(id="a1", ticker="SPY")
    rn = RootNode(settings=settings, root=root, dsl_version="1.0.0")
    assert not isinstance(rn, BaseNode)


# --- DSLValidationError ---

def test_dsl_validation_error_stores_all_fields():
    with pytest.raises(DSLValidationError) as exc_info:
        raise DSLValidationError("abc123", "My Node", "weights do not sum to 1.0")
    err = exc_info.value
    assert err.node_id == "abc123"
    assert err.node_name == "My Node"
    assert err.message == "weights do not sum to 1.0"


# --- PriceDataError ---

def test_price_data_error_stores_message():
    with pytest.raises(PriceDataError) as exc_info:
        raise PriceDataError("ticker SPY missing from price_data")
    assert exc_info.value.message == "ticker SPY missing from price_data"
