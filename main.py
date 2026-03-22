from __future__ import annotations

import argparse
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from moa_allocations.compiler import compile_strategy
from moa_allocations.engine import Runner, collect_tickers, compute_max_lookback


def _default_price_fetcher(tickers: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    from access import PidbReader  # lazy import — pidb_ib only needed at runtime

    db_path = os.environ.get("PIDB_IB_DB_PATH")
    if not db_path:
        raise ValueError(
            "PIDB_IB_DB_PATH environment variable is not set. "
            "Set it to the path of the pidb_ib database file."
        )

    reader = PidbReader(db_path)
    pl_df = reader.get_matrix(symbols=tickers, columns=["close_d"], start=start_date, end=end_date)

    df = pl_df.to_pandas()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.index.name = None
    return df.astype("float64")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run moa_allocations engine on a strategy DSL file.")
    parser.add_argument("--strategy", required=True, help="Path to a .moastrat.json DSL file.")
    parser.add_argument("--output", default="output", help="Output directory (default: output/).")
    args = parser.parse_args()

    # Compile
    root = compile_strategy(args.strategy)

    # Extract tickers and max lookback
    tickers = sorted(collect_tickers(root))
    max_lookback = compute_max_lookback(root)

    # Compute lookback-adjusted fetch start (trading days → calendar days)
    calendar_days = math.ceil(max_lookback * 7 / 5) + 10
    fetch_start = root.settings.start_date - timedelta(days=calendar_days)
    fetch_start_iso = fetch_start.isoformat()
    end_date_iso = root.settings.end_date.isoformat()

    # Fetch prices
    price_data = _default_price_fetcher(tickers, fetch_start_iso, end_date_iso)

    # Run engine
    runner = Runner(root, price_data)
    df = runner.run()

    # Build output filename: YYYYMMDD_HHMM_<stem>.csv
    now = datetime.now()
    stem = Path(Path(args.strategy).stem).stem
    filename = f"{now.strftime('%Y%m%d_%H%M')}_{stem}.csv"

    # Write output
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    df.to_csv(output_path, index=False)

    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
