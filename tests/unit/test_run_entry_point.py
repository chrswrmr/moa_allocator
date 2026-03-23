"""Tests for moa_allocations.run() — I1 public entry point."""
from __future__ import annotations

import json
import os
from datetime import date

import numpy as np
import pandas as pd
import pytest

from moa_allocations import run
from moa_allocations.engine import PriceDataError
from moa_allocations.exceptions import DSLValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_DOC = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "version-dsl": "1.0.0",
    "settings": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "name": "Test Strategy",
        "starting_cash": 100_000,
        "start_date": "2024-01-02",
        "end_date": "2024-03-29",
        "rebalance_frequency": "daily",
    },
    "root_node": {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "type": "weight",
        "method": "equal",
        "children": [
            {"id": "d1", "type": "asset", "ticker": "SPY"},
            {"id": "d2", "type": "asset", "ticker": "IWM"},
        ],
    },
}

_INVVOL_DOC = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567891",
    "version-dsl": "1.0.0",
    "settings": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678902",
        "name": "InvVol Strategy",
        "starting_cash": 100_000,
        "start_date": "2024-01-02",
        "end_date": "2024-03-29",
        "rebalance_frequency": "daily",
    },
    "root_node": {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789013",
        "type": "weight",
        "method": "inverse_volatility",
        "method_params": {"lookback": "200d"},
        "children": [
            {"id": "d1", "type": "asset", "ticker": "SPY"},
            {"id": "d2", "type": "asset", "ticker": "IWM"},
        ],
    },
}


def _write_strategy(tmp_path, doc):
    p = tmp_path / "strategy.moastrat.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def _make_price_data(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        rng.uniform(100, 200, size=(len(idx), len(tickers))),
        index=idx,
        columns=tickers,
    ).astype("float64")


# ---------------------------------------------------------------------------
# 4.1 End-to-end with custom price_fetcher
# ---------------------------------------------------------------------------

def test_run_end_to_end_custom_fetcher(tmp_path):
    path = _write_strategy(tmp_path, _SIMPLE_DOC)

    fetcher_calls = []

    def mock_fetcher(tickers, start_date, end_date):
        fetcher_calls.append((tickers, start_date, end_date))
        return _make_price_data(tickers, "2023-12-01", "2024-03-29")

    result = run(path, price_fetcher=mock_fetcher)

    assert isinstance(result, pd.DataFrame)
    assert "DATE" in result.columns
    assert "SPY" in result.columns
    assert "IWM" in result.columns
    assert len(result) > 0
    assert len(fetcher_calls) == 1


# ---------------------------------------------------------------------------
# 4.2 Custom fetcher receives settings.start_date (no lookback adjustment)
# ---------------------------------------------------------------------------

def test_custom_fetcher_receives_strategy_start_date(tmp_path):
    """With a custom fetcher, run() passes settings.start_date as-is.
    The custom fetcher is responsible for providing enough lookback history."""
    path = _write_strategy(tmp_path, _INVVOL_DOC)

    fetcher_calls = []

    def mock_fetcher(tickers, start_date, end_date):
        fetcher_calls.append((tickers, start_date, end_date))
        return _make_price_data(tickers, "2022-01-01", "2024-03-29")

    run(path, price_fetcher=mock_fetcher)

    assert len(fetcher_calls) == 1
    _, actual_start, _ = fetcher_calls[0]
    assert actual_start == date(2024, 1, 2).isoformat()


# ---------------------------------------------------------------------------
# 4.3 Custom fetcher with no lookback also receives settings.start_date
# ---------------------------------------------------------------------------

def test_custom_fetcher_no_lookback_receives_strategy_start_date(tmp_path):
    path = _write_strategy(tmp_path, _SIMPLE_DOC)  # equal weight, no lookback

    fetcher_calls = []

    def mock_fetcher(tickers, start_date, end_date):
        fetcher_calls.append((tickers, start_date, end_date))
        return _make_price_data(tickers, "2023-12-01", "2024-03-29")

    run(path, price_fetcher=mock_fetcher)

    _, actual_start, _ = fetcher_calls[0]
    assert actual_start == date(2024, 1, 2).isoformat()


# ---------------------------------------------------------------------------
# 4.4 Ticker extraction — sorted uppercase list passed to fetcher
# ---------------------------------------------------------------------------

def test_ticker_extraction_sorted(tmp_path):
    path = _write_strategy(tmp_path, _SIMPLE_DOC)

    fetcher_calls = []

    def mock_fetcher(tickers, start_date, end_date):
        fetcher_calls.append(tickers)
        return _make_price_data(tickers, "2023-12-01", "2024-03-29")

    run(path, price_fetcher=mock_fetcher)

    tickers_passed = fetcher_calls[0]
    assert tickers_passed == sorted(tickers_passed)
    assert all(t == t.upper() for t in tickers_passed)
    assert set(tickers_passed) == {"SPY", "IWM"}


# ---------------------------------------------------------------------------
# 4.5 Custom fetcher used when provided — pidb_ib not imported
# ---------------------------------------------------------------------------

def test_custom_fetcher_used_not_pidb(tmp_path, monkeypatch):
    path = _write_strategy(tmp_path, _SIMPLE_DOC)

    # Ensure PIDB_IB_DB_PATH is unset so default fetcher would fail
    monkeypatch.delenv("PIDB_IB_DB_PATH", raising=False)

    called = []

    def mock_fetcher(tickers, start_date, end_date):
        called.append(True)
        return _make_price_data(tickers, "2023-12-01", "2024-03-29")

    result = run(path, price_fetcher=mock_fetcher)
    assert called  # custom fetcher was used
    assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# 4.6 DSLValidationError from compiler propagates
# ---------------------------------------------------------------------------

def test_dsl_validation_error_propagates(tmp_path):
    with pytest.raises(DSLValidationError):
        run(str(tmp_path / "nonexistent.moastrat.json"))


# ---------------------------------------------------------------------------
# 4.7 PriceDataError from Runner propagates
# ---------------------------------------------------------------------------

def test_price_data_error_propagates(tmp_path):
    path = _write_strategy(tmp_path, _INVVOL_DOC)

    def mock_fetcher(tickers, start_date, end_date):
        # Return data that starts TOO LATE — missing lookback history
        return _make_price_data(tickers, "2024-01-02", "2024-03-29")

    with pytest.raises(PriceDataError):
        run(path, price_fetcher=mock_fetcher)


# ---------------------------------------------------------------------------
# 4.8 db_path is ignored when a custom price_fetcher is provided
# ---------------------------------------------------------------------------

def test_db_path_ignored_when_custom_fetcher_provided(tmp_path):
    """db_path has no effect when a custom price_fetcher is supplied."""
    path = _write_strategy(tmp_path, _SIMPLE_DOC)

    def custom_fetcher(tickers, start, end):
        return _make_price_data(tickers, start, end)

    # A nonsense db_path should not cause any error when a custom fetcher is used
    result = run(path, price_fetcher=custom_fetcher, db_path="nonexistent.db")
    assert isinstance(result, pd.DataFrame)
