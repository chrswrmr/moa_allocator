"""Tests for _default_price_fetcher and XCASHX filtering in run()."""
from __future__ import annotations

import json
import sqlite3
import sys

import numpy as np
import pandas as pd
import pytest

from moa_allocations import _default_price_fetcher, run
from moa_allocations.engine import PriceDataError


# ---------------------------------------------------------------------------
# Mock Polars DataFrame for _default_price_fetcher tests
# ---------------------------------------------------------------------------

class _MockPolarsDF:
    """Minimal Polars DataFrame stub returned by get_matrix()."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows  # list of {col: value}

    def __len__(self) -> int:
        return len(self._rows)

    def to_pandas(self) -> pd.DataFrame:
        return pd.DataFrame(self._rows)


class _MockReader:
    def __init__(self, db_path: str) -> None:
        pass

    def get_matrix(self, symbols, columns=None, **_kwargs) -> _MockPolarsDF:
        rows = [
            {"date": "2024-01-02", **{f"{s}_close_d": 100.0 + i for i, s in enumerate(symbols)}},
            {"date": "2024-01-03", **{f"{s}_close_d": 101.0 + i for i, s in enumerate(symbols)}},
        ]
        return _MockPolarsDF(rows)


class _MockReaderEmpty:
    def __init__(self, db_path: str) -> None:
        pass

    def get_matrix(self, symbols, columns=None, **_kwargs) -> _MockPolarsDF:
        return _MockPolarsDF([])


class _MockReaderPartial:
    """Returns data for SPY only, missing IWM."""

    def __init__(self, db_path: str) -> None:
        pass

    def get_matrix(self, symbols, columns=None, **_kwargs) -> _MockPolarsDF:
        rows = [
            {"date": "2024-01-02", "SPY_close_d": 100.0},
            {"date": "2024-01-03", "SPY_close_d": 101.0},
        ]
        return _MockPolarsDF(rows)


@pytest.fixture()
def mock_pidb(monkeypatch):
    import pidb_ib
    monkeypatch.setattr(pidb_ib, "PidbReader", _MockReader)


# ---------------------------------------------------------------------------
# 1. Import path — pidb_ib.PidbReader, not access.PidbReader
# ---------------------------------------------------------------------------

def test_import_path_uses_pidb_ib_module(tmp_path):
    """_default_price_fetcher imports from pidb_ib, not access."""
    import inspect
    import moa_allocations
    src = inspect.getsource(moa_allocations._default_price_fetcher)
    assert "from pidb_ib import PidbReader" in src
    assert "from access import" not in src


# ---------------------------------------------------------------------------
# 2. XCASHX filtering
# ---------------------------------------------------------------------------

_XCASH_DOC = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567899",
    "version-dsl": "1.0.0",
    "settings": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678999",
        "name": "Cash Strategy",
        "starting_cash": 100_000,
        "start_date": "2024-01-02",
        "end_date": "2024-01-03",
        "rebalance_frequency": "daily",
    },
    "root_node": {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789099",
        "type": "weight",
        "method": "equal",
        "children": [
            {"id": "d1", "type": "asset", "ticker": "SPY"},
            {"id": "d2", "type": "asset", "ticker": "IWM"},
        ],
    },
}


def test_xcashx_not_passed_to_fetcher(tmp_path, monkeypatch):
    """XCASHX ticker is filtered out before the price fetcher is called."""
    p = tmp_path / "s.moastrat.json"
    p.write_text(json.dumps(_XCASH_DOC), encoding="utf-8")

    fetcher_calls = []

    def mock_fetcher(tickers, start_date, end_date):
        fetcher_calls.append(list(tickers))
        idx = pd.bdate_range(start_date, end_date)
        rng = np.random.default_rng(0)
        return pd.DataFrame(
            rng.uniform(100, 200, size=(len(idx), len(tickers))),
            index=idx,
            columns=tickers,
        ).astype("float64")

    import moa_allocations
    # Inject XCASHX into collected tickers to simulate a cash-allocating strategy
    monkeypatch.setattr(moa_allocations, "collect_tickers", lambda _root: {"SPY", "IWM", "XCASHX"})

    run(str(p), price_fetcher=mock_fetcher)

    assert "XCASHX" not in fetcher_calls[0]
    assert set(fetcher_calls[0]) == {"SPY", "IWM"}


# ---------------------------------------------------------------------------
# 3. Column rename: {SYMBOL}_close_d → bare ticker names
# ---------------------------------------------------------------------------

def test_column_rename(mock_pidb):
    """_default_price_fetcher renames SPY_close_d → SPY etc."""
    df = _default_price_fetcher(["SPY", "IWM"], "2024-01-02", "2024-01-03", "dummy.db")
    assert "SPY" in df.columns
    assert "IWM" in df.columns
    assert "SPY_close_d" not in df.columns
    assert "IWM_close_d" not in df.columns


def test_result_is_datetime_index_float64(mock_pidb):
    """Result has DatetimeIndex and float64 columns."""
    df = _default_price_fetcher(["SPY"], "2024-01-02", "2024-01-03", "dummy.db")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df["SPY"].dtype == np.float64


# ---------------------------------------------------------------------------
# 4. Symbol validation: missing tickers raise PriceDataError
# ---------------------------------------------------------------------------

def test_missing_ticker_raises(monkeypatch):
    """PriceDataError raised when a requested ticker is absent from the result."""
    import pidb_ib
    monkeypatch.setattr(pidb_ib, "PidbReader", _MockReaderPartial)

    with pytest.raises(PriceDataError, match="IWM"):
        _default_price_fetcher(["SPY", "IWM"], "2024-01-02", "2024-01-03", "dummy.db")


# ---------------------------------------------------------------------------
# 5. ImportError → PriceDataError
# ---------------------------------------------------------------------------

def test_import_error_raises_price_data_error(monkeypatch):
    """PriceDataError raised when pidb_ib is not installed."""
    monkeypatch.setitem(sys.modules, "pidb_ib", None)

    with pytest.raises(PriceDataError, match="pidb_ib"):
        _default_price_fetcher(["SPY"], "2024-01-02", "2024-01-03", "dummy.db")


# ---------------------------------------------------------------------------
# 6. sqlite3.OperationalError → PriceDataError
# ---------------------------------------------------------------------------

def test_operational_error_raises_price_data_error(monkeypatch):
    """PriceDataError with db_path raised on sqlite3.OperationalError."""

    class _BrokenReader:
        def __init__(self, db_path: str) -> None:
            raise sqlite3.OperationalError("no such table: prices")

        def get_matrix(self, *a, **kw):  # pragma: no cover
            pass

    import pidb_ib
    monkeypatch.setattr(pidb_ib, "PidbReader", _BrokenReader)

    with pytest.raises(PriceDataError, match="bad_path.db"):
        _default_price_fetcher(["SPY"], "2024-01-02", "2024-01-03", "bad_path.db")


# ---------------------------------------------------------------------------
# 7. Empty result → PriceDataError
# ---------------------------------------------------------------------------

def test_empty_result_raises_price_data_error(monkeypatch):
    """PriceDataError raised when get_matrix returns zero rows."""
    import pidb_ib
    monkeypatch.setattr(pidb_ib, "PidbReader", _MockReaderEmpty)

    with pytest.raises(PriceDataError, match="No price data"):
        _default_price_fetcher(["SPY"], "2024-01-02", "2024-01-03", "dummy.db")
