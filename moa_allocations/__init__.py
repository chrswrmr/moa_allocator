from __future__ import annotations

import math
import os
from datetime import timedelta
from typing import Callable

import pandas as pd

from moa_allocations.compiler import compile_strategy
from moa_allocations.engine import Runner, collect_tickers, compute_max_lookback

PriceFetcher = Callable[[list[str], str, str], pd.DataFrame]


def _default_price_fetcher(tickers: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    from src.access import PidbReader  # lazy import — pidb_ib only needed for default path

    db_path = os.environ.get("PIDB_IB_DB_PATH")
    if not db_path:
        raise ValueError(
            "PIDB_IB_DB_PATH environment variable is not set. "
            "Set it to the path of the pidb_ib database file."
        )

    reader = PidbReader(db_path)
    pl_df = reader.get_matrix(symbols=tickers, columns=["close_d"], start=start_date, end=end_date)

    # Convert Polars wide-format result to the pandas price_data contract:
    # - date string column → DatetimeIndex
    # - single-column get_matrix returns columns named directly after symbols (e.g. SPY, IWM)
    # - values as float64
    df = pl_df.to_pandas()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.index.name = None
    return df.astype("float64")


def run(strategy_path: str, price_fetcher: PriceFetcher | None = None) -> pd.DataFrame:
    fetcher = price_fetcher if price_fetcher is not None else _default_price_fetcher

    # Step 1: compile
    root = compile_strategy(strategy_path)

    # Step 2: extract tickers and max lookback
    tickers = sorted(collect_tickers(root))
    max_lookback = compute_max_lookback(root)

    # Step 3: compute lookback-adjusted fetch start (trading days → calendar days)
    calendar_days = math.ceil(max_lookback * 7 / 5) + 10
    fetch_start = root.settings.start_date - timedelta(days=calendar_days)
    fetch_start_iso = fetch_start.isoformat()
    end_date_iso = root.settings.end_date.isoformat()

    # Step 4: fetch prices
    price_data = fetcher(tickers, fetch_start_iso, end_date_iso)

    # Steps 5–7: run engine and return allocations
    runner = Runner(root, price_data)
    return runner.run()
