"""Tests for public API functions: validate, get_tickers, check_prices, list_indicators."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from moa_allocations import validate, get_tickers, list_indicators
from moa_allocations.exceptions import DSLValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STRATEGIES_DIR = Path(__file__).resolve().parent.parent.parent / "strategies"


def _find_strategy() -> str | None:
    """Return path to a valid .moastrat.json file if one exists."""
    if _STRATEGIES_DIR.exists():
        for f in _STRATEGIES_DIR.rglob("*.moastrat.json"):
            return str(f)
    return None


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_strategy(self):
        path = _find_strategy()
        if path is None:
            pytest.skip("No strategy files found in strategies/")
        assert validate(path) is True

    def test_invalid_strategy_raises(self, tmp_path):
        bad_file = tmp_path / "bad.moastrat.json"
        bad_file.write_text("{}")
        with pytest.raises(DSLValidationError):
            validate(str(bad_file))

    def test_nonexistent_file_raises(self):
        with pytest.raises(DSLValidationError):
            validate("nonexistent_file.moastrat.json")


# ---------------------------------------------------------------------------
# get_tickers()
# ---------------------------------------------------------------------------

class TestGetTickers:
    def test_returns_dict_with_both_keys(self):
        path = _find_strategy()
        if path is None:
            pytest.skip("No strategy files found in strategies/")
        result = get_tickers(path)
        assert "traded_tickers" in result
        assert "signal_tickers" in result
        assert isinstance(result["traded_tickers"], list)
        assert isinstance(result["signal_tickers"], list)

    def test_traded_tickers_are_sorted(self):
        path = _find_strategy()
        if path is None:
            pytest.skip("No strategy files found in strategies/")
        result = get_tickers(path)
        assert result["traded_tickers"] == sorted(result["traded_tickers"])

    def test_invalid_strategy_raises(self, tmp_path):
        bad_file = tmp_path / "bad.moastrat.json"
        bad_file.write_text("{}")
        with pytest.raises(DSLValidationError):
            get_tickers(str(bad_file))


# ---------------------------------------------------------------------------
# list_indicators()
# ---------------------------------------------------------------------------

class TestListIndicators:
    def test_returns_list_of_dicts(self):
        result = list_indicators()
        assert isinstance(result, list)
        assert len(result) > 0
        for entry in result:
            assert "name" in entry
            assert "requires_lookback" in entry
            assert isinstance(entry["name"], str)
            assert isinstance(entry["requires_lookback"], bool)

    def test_current_price_no_lookback(self):
        result = list_indicators()
        cp = [e for e in result if e["name"] == "current_price"]
        assert len(cp) == 1
        assert cp[0]["requires_lookback"] is False

    def test_sma_price_requires_lookback(self):
        result = list_indicators()
        sma = [e for e in result if e["name"] == "sma_price"]
        assert len(sma) == 1
        assert sma[0]["requires_lookback"] is True

    def test_sorted_by_name(self):
        result = list_indicators()
        names = [e["name"] for e in result]
        assert names == sorted(names)

    def test_matches_dispatch_table(self):
        from moa_allocations.engine.algos.metrics import _DISPATCH
        result = list_indicators()
        result_names = {e["name"] for e in result}
        assert result_names == set(_DISPATCH.keys())
