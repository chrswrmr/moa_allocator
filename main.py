from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from moa_allocations.compiler import compile_strategy
from moa_allocations.engine import Runner, collect_tickers, compute_max_lookback

_LOG_FMT = "%(asctime)s  %(levelname)s  %(message)s"


def _setup_logging(log_path: Path, debug: bool) -> None:
    """Configure FileHandler (always DEBUG) and StreamHandler on the moa_allocations logger."""
    root_logger = logging.getLogger("moa_allocations")
    root_logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_LOG_FMT))

    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG if debug else logging.INFO)
    sh.setFormatter(logging.Formatter(_LOG_FMT))

    root_logger.addHandler(fh)
    root_logger.addHandler(sh)


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
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level console output (file always captures DEBUG).")
    args = parser.parse_args()

    # Shared timestamp and stem for file naming
    now = datetime.now()
    stem = Path(Path(args.strategy).stem).stem
    ts = now.strftime("%Y%m%d_%H%M")

    # Set up logging — logs/ dir created here, shared timestamp with CSV
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{ts}_{stem}_log.txt"
    _setup_logging(log_path, args.debug)

    logger = logging.getLogger("moa_allocations")
    t_start = time.monotonic()

    # Compile
    root = compile_strategy(args.strategy)

    # Extract tickers and max lookback
    tickers = sorted(collect_tickers(root))
    max_lookback = compute_max_lookback(root)

    end_date_iso = root.settings.end_date.isoformat()
    start_date_iso = root.settings.start_date.isoformat()

    logger.info(
        "Strategy loaded: %s | tickers: %d | %s -> %s",
        args.strategy, len(tickers), start_date_iso, end_date_iso,
    )

    # Resolve precise fetch start: exactly max_lookback trading days before start_date
    if max_lookback > 0:
        fetch_start_iso = _resolve_lookback_start(tickers[0], start_date_iso, max_lookback, args.db)
    else:
        fetch_start_iso = start_date_iso

    # Fetch prices
    price_data = _default_price_fetcher(tickers, fetch_start_iso, end_date_iso, args.db)

    logger.info(
        "Simulation starting | start=%s  end=%s  rebalance=%s",
        start_date_iso, end_date_iso, root.settings.rebalance_frequency,
    )

    # Run engine
    runner = Runner(root, price_data)
    df = runner.run()

    # Build output filename: YYYYMMDD_HHMM_<stem>.csv
    filename = f"{ts}_{stem}.csv"

    # Write output
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    df.to_csv(output_path, index=False)

    elapsed = time.monotonic() - t_start
    logger.info(
        "Run complete | output=%s  log=%s  elapsed=%.2fs",
        output_path, log_path, elapsed,
    )

    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
