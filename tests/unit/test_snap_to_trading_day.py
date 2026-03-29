"""Tests for _snap_to_trading_day and the no-snapping guarantee for custom fetchers."""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from moa_allocations import _snap_to_trading_day, run


# ---------------------------------------------------------------------------
# Mock PidbReader for snap tests
# ---------------------------------------------------------------------------

_CALENDAR = [
    "2024-01-02",
    "2024-01-03",
    "2024-01-04",
    "2024-01-05",
    "2024-01-08",  # 2024-01-06 (Sat) and 2024-01-07 (Sun) are absent
    "2024-01-09",
    "2024-01-10",
]


class _MockDf:
    """Minimal polars-like DataFrame stub."""

    def __init__(self, dates: list[str], ticker: str) -> None:
        self._dates = dates
        self._ticker = ticker

    def sort(self, col: str) -> "_MockDf":  # noqa: ARG002
        return _MockDf(sorted(self._dates), self._ticker)

    def __getitem__(self, col: str) -> "_MockSeries":
        if col == "date":
            return _MockSeries(self._dates)
        return _MockSeries([100.0] * len(self._dates))


class _MockSeries:
    def __init__(self, data: list) -> None:
        self._data = data

    def to_list(self) -> list:
        return list(self._data)


class _MockReader:
    def __init__(self, db_path: str) -> None:  # noqa: ARG002
        pass

    def get_matrix(self, symbols: list[str], columns: list[str], **_kwargs) -> _MockDf:
        return _MockDf(_CALENDAR, symbols[0])


@pytest.fixture()
def mock_pidb(monkeypatch):
    import pidb_ib
    monkeypatch.setattr(pidb_ib, "PidbReader", _MockReader)


# ---------------------------------------------------------------------------
# 4.1 _snap_to_trading_day unit tests
# ---------------------------------------------------------------------------

def test_snap_forward_non_trading_day(mock_pidb):
    """2024-01-06 is Saturday; snaps forward to 2024-01-08."""
    result = _snap_to_trading_day("2024-01-06", "forward", "SPY", "dummy.db")
    assert result == "2024-01-08"


def test_snap_backward_non_trading_day(mock_pidb):
    """2024-01-06 is Saturday; snaps backward to 2024-01-05."""
    result = _snap_to_trading_day("2024-01-06", "backward", "SPY", "dummy.db")
    assert result == "2024-01-05"


def test_snap_forward_already_trading_day(mock_pidb):
    """Date already in calendar passes through unchanged."""
    result = _snap_to_trading_day("2024-01-03", "forward", "SPY", "dummy.db")
    assert result == "2024-01-03"


def test_snap_backward_already_trading_day(mock_pidb):
    """Date already in calendar passes through unchanged."""
    result = _snap_to_trading_day("2024-01-03", "backward", "SPY", "dummy.db")
    assert result == "2024-01-03"


def test_snap_forward_out_of_bounds_raises(mock_pidb):
    """Forward snap beyond last calendar date raises ValueError."""
    with pytest.raises(ValueError, match="no trading day at or after"):
        _snap_to_trading_day("2025-01-01", "forward", "SPY", "dummy.db")


def test_snap_backward_out_of_bounds_raises(mock_pidb):
    """Backward snap before first calendar date raises ValueError."""
    with pytest.raises(ValueError, match="no trading day at or before"):
        _snap_to_trading_day("2020-01-01", "backward", "SPY", "dummy.db")


# ---------------------------------------------------------------------------
# 4.2 run() with custom fetcher — snapping NOT applied
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


def _make_price_data(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        rng.uniform(100, 200, size=(len(idx), len(tickers))),
        index=idx,
        columns=tickers,
    ).astype("float64")


def test_run_no_tickers_raises_before_snap(tmp_path, monkeypatch):
    """run() with default fetcher raises ValueError before snapping when strategy has no tickers."""
    import moa_allocations
    p = tmp_path / "s.moastrat.json"
    p.write_text(json.dumps(_SIMPLE_DOC), encoding="utf-8")

    # Simulate a strategy whose compiled tree yields no tickers
    monkeypatch.setattr(moa_allocations, "collect_tickers", lambda _root: set())

    with pytest.raises(ValueError, match="no real tickers"):
        run(str(p))  # no price_fetcher → default fetcher path → hits the guard


def test_custom_fetcher_receives_raw_dsl_dates(tmp_path):
    """Custom price_fetcher receives the raw DSL dates — no snapping applied."""
    p = tmp_path / "s.moastrat.json"
    p.write_text(json.dumps(_SIMPLE_DOC), encoding="utf-8")

    fetcher_calls = []

    def custom_fetcher(tickers, start_date, end_date):
        fetcher_calls.append((start_date, end_date))
        return _make_price_data(tickers, "2023-12-01", "2024-03-29")

    run(str(p), price_fetcher=custom_fetcher)

    assert len(fetcher_calls) == 1
    actual_start, actual_end = fetcher_calls[0]
    # Custom fetcher receives the raw DSL dates — no snapping applied
    assert actual_start == date(2024, 1, 2).isoformat()
    assert actual_end == date(2024, 3, 29).isoformat()
