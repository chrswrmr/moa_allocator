from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from moa_allocations.compiler import compile_strategy
from moa_allocations.engine import Runner, collect_tickers, compute_max_lookback


def _resolve_lookback_start(anchor_ticker: str, start_date: str, max_lookback: int, db_path: str) -> str:
    """Return the ISO date that is exactly max_lookback trading days before start_date."""
    from access import PidbReader

    reader = PidbReader(db_path)
    pl_df = reader.get_matrix(symbols=[anchor_ticker], columns=["close_d"], end=start_date)
    dates = pl_df.sort("date")["date"].to_list()
    # dates[-1] is start_date itself; we need the date max_lookback rows before it
    pos = len(dates) - 1  # index of start_date
    if pos < max_lookback:
        raise ValueError(
            f"Not enough history for {anchor_ticker}: need {max_lookback} bars before "
            f"{start_date}, but only {pos} available."
        )
    return str(dates[pos - max_lookback])


def _default_price_fetcher(tickers: list[str], start_date: str, end_date: str, db_path: str) -> pd.DataFrame:
    from access import PidbReader  # lazy import — pidb_ib only needed at runtime

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
    parser.add_argument("--db", default=r"C:\py\pidb_ib\data\pidb_ib.db", help="Path to the pidb_ib database file.")
    args = parser.parse_args()

    # Compile
    root = compile_strategy(args.strategy)

    # Extract tickers and max lookback
    tickers = sorted(collect_tickers(root))
    max_lookback = compute_max_lookback(root)

    end_date_iso = root.settings.end_date.isoformat()
    start_date_iso = root.settings.start_date.isoformat()

    # Resolve precise fetch start: exactly max_lookback trading days before start_date
    if max_lookback > 0:
        fetch_start_iso = _resolve_lookback_start(tickers[0], start_date_iso, max_lookback, args.db)
    else:
        fetch_start_iso = start_date_iso

    # Fetch prices
    price_data = _default_price_fetcher(tickers, fetch_start_iso, end_date_iso, args.db)

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
