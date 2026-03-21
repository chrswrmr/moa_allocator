"""Tests for C4: compile_strategy() steps 4-5 — tree instantiation and lookback conversion."""
import json
from datetime import date

import pytest

from moa_allocations.compiler import compile_strategy
from moa_allocations.compiler.compiler import _build_node, _build_settings, _convert_lookback
from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, WeightNode
from moa_allocations.engine.strategy import RootNode, Settings
from moa_allocations.exceptions import DSLValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(tmp_path, data):
    p = tmp_path / "strategy.moastrat.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


_BASE_SETTINGS = {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "name": "Test Strategy",
    "starting_cash": 100000,
    "start_date": "2020-01-01",
    "end_date": "2021-01-01",
    "rebalance_frequency": "daily",
}

_STRATEGY_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def _doc(root_node, settings=None):
    return {
        "id": _STRATEGY_ID,
        "version-dsl": "1.0.0",
        "settings": settings or _BASE_SETTINGS,
        "root_node": root_node,
    }


# ---------------------------------------------------------------------------
# Task 1.2 — _convert_lookback unit tests
# ---------------------------------------------------------------------------

class TestConvertLookback:
    def test_days(self):
        assert _convert_lookback("200d") == 200

    def test_days_small(self):
        assert _convert_lookback("1d") == 1

    def test_weeks(self):
        assert _convert_lookback("4w") == 20

    def test_months(self):
        assert _convert_lookback("3m") == 63

    def test_months_large(self):
        assert _convert_lookback("12m") == 252

    def test_invalid_format_raises(self):
        with pytest.raises(DSLValidationError) as exc_info:
            _convert_lookback("200x")
        assert "invalid time_offset" in exc_info.value.message

    def test_invalid_no_unit_raises(self):
        with pytest.raises(DSLValidationError):
            _convert_lookback("200")

    def test_invalid_empty_raises(self):
        with pytest.raises(DSLValidationError):
            _convert_lookback("")


# ---------------------------------------------------------------------------
# Task 3.3 — Unknown node type
# ---------------------------------------------------------------------------

class TestUnknownNodeType:
    def test_unknown_type_raises_dsl_validation_error(self):
        raw = {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "bogus"}
        with pytest.raises(DSLValidationError) as exc_info:
            _build_node(raw)
        assert "unknown node type" in exc_info.value.message
        assert exc_info.value.node_id == "aaaaaaaa-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Task 2.2 — _build_settings unit tests
# ---------------------------------------------------------------------------

class TestBuildSettings:
    def test_all_fields_provided(self):
        raw = {
            **_BASE_SETTINGS,
            "slippage": 0.001,
            "fees": 0.002,
            "rebalance_threshold": 0.05,
        }
        s = _build_settings(raw)
        assert isinstance(s, Settings)
        assert s.id == raw["id"]
        assert s.name == "Test Strategy"
        assert s.starting_cash == 100000.0
        assert s.start_date == date(2020, 1, 1)
        assert s.end_date == date(2021, 1, 1)
        assert s.slippage == 0.001
        assert s.fees == 0.002
        assert s.rebalance_frequency == "daily"
        assert s.rebalance_threshold == 0.05

    def test_optional_fields_use_defaults(self):
        s = _build_settings(_BASE_SETTINGS)
        assert s.slippage == 0.0005
        assert s.fees == 0.0
        assert s.rebalance_threshold is None

    def test_dates_converted_to_date_objects(self):
        s = _build_settings(_BASE_SETTINGS)
        assert isinstance(s.start_date, date)
        assert isinstance(s.end_date, date)


# ---------------------------------------------------------------------------
# Task 5.1 — Full compile_strategy integration tests
# ---------------------------------------------------------------------------

class TestCompileStrategyIntegration:
    def test_asset_root_returns_root_node(self, tmp_path):
        doc = _doc({"id": "c3d4e5f6-a7b8-9012-cdef-123456789012", "type": "asset", "ticker": "SPY"})
        result = compile_strategy(_write_json(tmp_path, doc))
        assert isinstance(result, RootNode)
        assert result.dsl_version == "1.0.0"
        assert isinstance(result.settings, Settings)
        assert isinstance(result.root, AssetNode)
        assert result.root.ticker == "SPY"

    def test_weight_with_asset_children(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "weight",
            "method": "equal",
            "children": [
                {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "asset", "ticker": "SPY"},
                {"id": "bbbbbbbb-0000-0000-0000-000000000000", "type": "asset", "ticker": "AGG"},
            ],
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert isinstance(result.root, WeightNode)
        assert result.root.method == "equal"
        assert len(result.root.children) == 2
        assert isinstance(result.root.children[0], AssetNode)
        assert result.root.children[0].ticker == "SPY"
        assert isinstance(result.root.children[1], AssetNode)
        assert result.root.children[1].ticker == "AGG"

    def test_weight_with_mixed_children(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "weight",
            "method": "equal",
            "children": [
                {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "asset", "ticker": "SPY"},
                {
                    "id": "bbbbbbbb-0000-0000-0000-000000000000",
                    "type": "weight",
                    "method": "equal",
                    "children": [
                        {"id": "cccccccc-0000-0000-0000-000000000000", "type": "asset", "ticker": "AGG"},
                    ],
                },
            ],
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert isinstance(result.root, WeightNode)
        assert len(result.root.children) == 2
        assert isinstance(result.root.children[0], AssetNode)
        assert isinstance(result.root.children[1], WeightNode)
        assert isinstance(result.root.children[1].children[0], AssetNode)

    def test_if_else_with_branches(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "if_else",
            "logic_mode": "all",
            "conditions": [{
                "lhs": {"asset": "SPY", "function": "current_price"},
                "comparator": "greater_than",
                "rhs": 100,
            }],
            "true_branch": {"id": "22222222-2222-2222-2222-222222222222", "type": "asset", "ticker": "SPY"},
            "false_branch": {"id": "33333333-3333-3333-3333-333333333333", "type": "asset", "ticker": "AGG"},
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert isinstance(result.root, IfElseNode)
        assert result.root.logic_mode == "all"
        assert isinstance(result.root.true_branch, AssetNode)
        assert isinstance(result.root.false_branch, AssetNode)

    def test_filter_with_children(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "filter",
            "sort_by": {"function": "current_price"},
            "select": {"mode": "top", "count": 1},
            "children": [
                {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "asset", "ticker": "SPY"},
                {"id": "bbbbbbbb-0000-0000-0000-000000000000", "type": "asset", "ticker": "AGG"},
            ],
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert isinstance(result.root, FilterNode)
        assert len(result.root.children) == 2

    def test_deeply_nested_filter_weight_asset(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "filter",
            "sort_by": {"function": "current_price"},
            "select": {"mode": "top", "count": 1},
            "children": [{
                "id": "22222222-2222-2222-2222-222222222222",
                "type": "weight",
                "method": "equal",
                "children": [
                    {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "asset", "ticker": "SPY"},
                ],
            }],
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert isinstance(result.root, FilterNode)
        assert isinstance(result.root.children[0], WeightNode)
        assert isinstance(result.root.children[0].children[0], AssetNode)

    def test_settings_attached_to_root_node(self, tmp_path):
        doc = _doc({"id": "c3d4e5f6-a7b8-9012-cdef-123456789012", "type": "asset", "ticker": "SPY"})
        result = compile_strategy(_write_json(tmp_path, doc))
        assert result.settings.name == "Test Strategy"
        assert result.settings.start_date == date(2020, 1, 1)
        assert result.settings.end_date == date(2021, 1, 1)
        assert result.settings.starting_cash == 100000.0


# ---------------------------------------------------------------------------
# Task 5.2 — Lookback conversion end-to-end
# ---------------------------------------------------------------------------

class TestLookbackConversionEndToEnd:
    def test_condition_metric_lookback_converted(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "if_else",
            "logic_mode": "all",
            "conditions": [{
                "lhs": {"asset": "SPY", "function": "sma_price", "lookback": "200d"},
                "comparator": "greater_than",
                "rhs": {"asset": "SPY", "function": "sma_price", "lookback": "4w"},
            }],
            "true_branch": {"id": "22222222-2222-2222-2222-222222222222", "type": "asset", "ticker": "SPY"},
            "false_branch": {"id": "33333333-3333-3333-3333-333333333333", "type": "asset", "ticker": "AGG"},
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        cond = result.root.conditions[0]
        assert cond["lhs"]["lookback"] == 200
        assert cond["rhs"]["lookback"] == 20

    def test_condition_duration_converted(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "if_else",
            "logic_mode": "all",
            "conditions": [{
                "lhs": {"asset": "SPY", "function": "current_price"},
                "comparator": "greater_than",
                "rhs": 100,
                "duration": "3m",
            }],
            "true_branch": {"id": "22222222-2222-2222-2222-222222222222", "type": "asset", "ticker": "SPY"},
            "false_branch": {"id": "33333333-3333-3333-3333-333333333333", "type": "asset", "ticker": "AGG"},
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert result.root.conditions[0]["duration"] == 63

    def test_default_duration_applied(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "if_else",
            "logic_mode": "all",
            "conditions": [{
                "lhs": {"asset": "SPY", "function": "current_price"},
                "comparator": "greater_than",
                "rhs": 100,
            }],
            "true_branch": {"id": "22222222-2222-2222-2222-222222222222", "type": "asset", "ticker": "SPY"},
            "false_branch": {"id": "33333333-3333-3333-3333-333333333333", "type": "asset", "ticker": "AGG"},
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert result.root.conditions[0]["duration"] == 1

    def test_filter_sort_by_lookback_converted(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "filter",
            "sort_by": {"function": "rsi", "lookback": "14d"},
            "select": {"mode": "top", "count": 1},
            "children": [
                {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "asset", "ticker": "SPY"},
                {"id": "bbbbbbbb-0000-0000-0000-000000000000", "type": "asset", "ticker": "AGG"},
            ],
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert result.root.sort_by["lookback"] == 14

    def test_inverse_volatility_lookback_converted(self, tmp_path):
        doc = _doc({
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "weight",
            "method": "inverse_volatility",
            "method_params": {"lookback": "6m"},
            "children": [
                {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "asset", "ticker": "SPY"},
            ],
        })
        result = compile_strategy(_write_json(tmp_path, doc))
        assert result.root.method_params["lookback"] == 126


# ---------------------------------------------------------------------------
# Task 5.3 — No partial tree / NotImplementedError
# ---------------------------------------------------------------------------

class TestNoPartialTree:
    def test_valid_strategy_does_not_raise(self, tmp_path):
        doc = _doc({"id": "c3d4e5f6-a7b8-9012-cdef-123456789012", "type": "asset", "ticker": "SPY"})
        # Must not raise any exception
        result = compile_strategy(_write_json(tmp_path, doc))
        assert result is not None

    def test_not_implemented_error_gone(self, tmp_path):
        doc = _doc({"id": "c3d4e5f6-a7b8-9012-cdef-123456789012", "type": "asset", "ticker": "SPY"})
        # Must return a value, not raise NotImplementedError
        from moa_allocations.engine.strategy import RootNode
        result = compile_strategy(_write_json(tmp_path, doc))
        assert isinstance(result, RootNode)
