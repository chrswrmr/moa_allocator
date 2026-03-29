from __future__ import annotations

import bisect
import sqlite3
from typing import Callable

import pandas as pd

from moa_allocations.compiler import compile_strategy
from moa_allocations.engine import PriceDataError, Runner, collect_tickers, compute_max_lookback

PriceFetcher = Callable[[list[str], str, str], pd.DataFrame]

DEFAULT_DB_PATH = r"C:\py\pidb_ib\data\pidb_ib.db"

_XCASHX = "XCASHX"


def _snap_to_trading_day(date_str: str, direction: str, anchor_ticker: str, db_path: str) -> str:
    """Return the nearest in-calendar trading day for *date_str*.

    direction='forward' : first date >= date_str  (used for start_date)
    direction='backward': last  date <= date_str  (used for end_date)
    """
    from pidb_ib import PidbReader  # lazy import — pidb_ib only needed for default path

    reader = PidbReader(db_path)
    pl_df = reader.get_matrix(symbols=[anchor_ticker], columns=["close_d"])
    dates = [str(d) for d in pl_df.sort("date")["date"].to_list()]

    if direction == "forward":
        idx = bisect.bisect_left(dates, date_str)
        if idx >= len(dates):
            raise ValueError(
                f"Date snapping failed: no trading day at or after {date_str!r} in the pidb_ib calendar."
            )
        return dates[idx]
    else:  # backward
        idx = bisect.bisect_right(dates, date_str) - 1
        if idx < 0:
            raise ValueError(
                f"Date snapping failed: no trading day at or before {date_str!r} in the pidb_ib calendar."
            )
        return dates[idx]


def _resolve_lookback_start(anchor_ticker: str, start_date: str, max_lookback: int, db_path: str) -> str:
    """Return the ISO date that is exactly max_lookback trading days before start_date."""
    from pidb_ib import PidbReader

    reader = PidbReader(db_path)
    pl_df = reader.get_matrix(symbols=[anchor_ticker], columns=["close_d"], end=start_date)
    dates = pl_df.sort("date")["date"].to_list()
    pos = len(dates) - 1  # index of start_date
    if pos < max_lookback:
        raise ValueError(
            f"Not enough history for {anchor_ticker}: need {max_lookback} bars before "
            f"{start_date}, but only {pos} available."
        )
    return str(dates[pos - max_lookback])


def _default_price_fetcher(tickers: list[str], start_date: str, end_date: str, db_path: str) -> pd.DataFrame:
    try:
        from pidb_ib import PidbReader  # lazy import — pidb_ib only needed for default path
    except ImportError as exc:
        raise PriceDataError(
            "pidb_ib package is not available. Install it as an editable dependency."
        ) from exc

    try:
        reader = PidbReader(db_path)
        pl_df = reader.get_matrix(symbols=tickers, columns=["close_d"], start=start_date, end=end_date)
    except sqlite3.OperationalError as exc:
        raise PriceDataError(
            f"Database error accessing pidb_ib at {db_path!r}: {exc}"
        ) from exc

    if len(pl_df) == 0:
        raise PriceDataError(
            f"No price data returned for tickers {tickers} between {start_date} and {end_date}."
        )

    # Convert Polars wide-format result to the pandas price_data contract:
    # - date string column → DatetimeIndex
    # - get_matrix returns {SYMBOL}_close_d columns; rename to bare ticker names
    # - values as float64
    df = pl_df.to_pandas()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.index.name = None
    df = df.rename(columns={col: col.replace("_close_d", "") for col in df.columns})
    df = df.astype("float64")

    missing = set(tickers) - set(df.columns)
    if missing:
        raise PriceDataError(
            f"Price data missing for tickers: {sorted(missing)}. "
            f"Available columns: {sorted(df.columns.tolist())}."
        )

    return df


def run(strategy_path: str, price_fetcher: PriceFetcher | None = None, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    # Step 1: compile
    root = compile_strategy(strategy_path)

    # Step 2: extract tickers and max lookback
    tickers = sorted(collect_tickers(root))
    max_lookback = compute_max_lookback(root)

    start_date_iso = root.settings.start_date.isoformat()
    end_date_iso = root.settings.end_date.isoformat()

    # Filter synthetic cash placeholder — no real price data exists for it
    fetch_tickers = [t for t in tickers if t != _XCASHX]

    if price_fetcher is None:
        # Step 3: snap dates to nearest trading days in the pidb_ib calendar
        if not fetch_tickers:
            raise ValueError("Cannot snap dates: strategy contains no real tickers.")
        snapped_start = _snap_to_trading_day(start_date_iso, "forward", fetch_tickers[0], db_path)
        snapped_end = _snap_to_trading_day(end_date_iso, "backward", fetch_tickers[0], db_path)
        # Step 4: resolve precise fetch start from the trading calendar
        if max_lookback > 0:
            fetch_start_iso = _resolve_lookback_start(fetch_tickers[0], snapped_start, max_lookback, db_path)
        else:
            fetch_start_iso = snapped_start
        fetcher = lambda t, s, e: _default_price_fetcher(t, s, e, db_path)
        end_date_iso = snapped_end
    else:
        # Custom fetcher: caller is responsible for providing enough history
        fetcher = price_fetcher
        fetch_start_iso = start_date_iso

    # Step 5: fetch prices
    price_data = fetcher(fetch_tickers, fetch_start_iso, end_date_iso)

    # Steps 6–8: run engine and return allocations
    runner = Runner(root, price_data)
    return runner.run()
