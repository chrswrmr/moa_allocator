from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from moa_allocations import (
    check_prices,
    get_tickers,
    list_indicators,
    validate,
)
from moa_allocations.compiler import compile_strategy
from moa_allocations.engine import PriceDataError, Runner, collect_tickers, compute_max_lookback
from moa_allocations.engine.runner import collect_traded_tickers, collect_signal_tickers
from moa_allocations.exceptions import DSLValidationError

_XCASHX = "XCASHX"

_LOG_FMT = "%(asctime)s  %(levelname)s  %(message)s"

_EPILOG = """\
Query Modes (mutually exclusive, always output JSON -- --json is implied):
  --validate           Validate DSL only -- schema + semantic checks, no price fetch, no engine
  --tickers            Extract traded tickers and signal tickers from strategy tree
  --check-prices       Validate + verify all tickers exist in pidb_ib for date range (requires --db)
  --list-indicators    List all indicator functions the engine supports (no --strategy needed)

Default (no query flag): Run full pipeline -- compile -> fetch prices -> engine -> write CSV

Output (JSON on stdout):
  Run:               {"status": "ok", "allocations_path": "<path>", "rows": <n>, "traded_tickers": [...], "signal_tickers": [...]}
  --validate:        {"status": "ok", "valid": true}
  --tickers:         {"status": "ok", "traded_tickers": ["SPY", "TLT"], "signal_tickers": ["VIXY"]}
  --check-prices:    {"status": "ok", "prices_available": true}
  --list-indicators: {"status": "ok", "indicators": [{"name": "current_price", "requires_lookback": false}, ...]}

Exit Codes:
  0    Success
  1    DSL validation error (invalid .moastrat.json)
  2    Price data error (missing tickers or date range in pidb_ib)
  3    Unexpected error

Errors (with --json or query modes):
  {"status": "error", "code": 1, "valid": false, "errors": [{"node_id": "<id>", "node_name": "<name>", "message": "<text>"}]}
"""


def _setup_logging(log_path: Path, debug: bool) -> None:
    """Configure FileHandler (always DEBUG) and StreamHandler (stderr) on the moa_allocations logger."""
    root_logger = logging.getLogger("moa_allocations")
    root_logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_LOG_FMT))

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.DEBUG if debug else logging.INFO)
    sh.setFormatter(logging.Formatter(_LOG_FMT))

    root_logger.addHandler(fh)
    root_logger.addHandler(sh)


def _resolve_lookback_start(anchor_ticker: str, start_date: str, max_lookback: int, db_path: str) -> str:
    """Return the ISO date that is exactly max_lookback trading days before start_date."""
    from pidb_ib import PidbReader

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
    try:
        from pidb_ib import PidbReader
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


def _print_json(data: dict) -> None:
    """Print JSON to stdout."""
    print(json.dumps(data))


def _handle_error(exc: Exception, use_json: bool) -> int:
    """Handle an exception: return exit code, optionally print JSON error to stdout."""
    if isinstance(exc, DSLValidationError):
        code = 1
        if use_json:
            _print_json({
                "status": "error",
                "code": code,
                "valid": False,
                "errors": [{"node_id": exc.node_id, "node_name": exc.node_name, "message": exc.message}],
            })
    elif isinstance(exc, PriceDataError):
        code = 2
        if use_json:
            error_data: dict = {"status": "error", "code": code, "prices_available": False, "message": exc.message}
            if exc.missing_tickers:
                error_data["missing_tickers"] = exc.missing_tickers
            if exc.missing_dates:
                error_data["missing_dates"] = exc.missing_dates
            _print_json(error_data)
    else:
        code = 3
        if use_json:
            _print_json({"status": "error", "code": code, "message": str(exc)})
    return code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="moa_allocations -- Compile a .moastrat.json strategy and produce daily target weight allocations.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--strategy", default=None, help="Path to a .moastrat.json DSL file (required, except --list-indicators).")
    parser.add_argument("--output", default="output", help="Output directory for allocations CSV (default: output/).")
    parser.add_argument("--db", default=r"C:\py\pidb_ib\data\pidb_ib.db", help="Path to pidb_ib SQLite database (default: C:/py/pidb_ib/data/pidb_ib.db).")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level console output.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Write result to stdout as JSON (only needed for run mode).")

    query_group = parser.add_mutually_exclusive_group()
    query_group.add_argument("--validate", action="store_true", help="Validate DSL only -- schema + semantic checks, no price fetch, no engine.")
    query_group.add_argument("--tickers", action="store_true", help="Extract traded tickers and signal tickers from strategy tree.")
    query_group.add_argument("--check-prices", action="store_true", help="Validate + verify all tickers exist in pidb_ib for date range.")
    query_group.add_argument("--list-indicators", action="store_true", help="List all indicator functions the engine supports (no --strategy needed).")

    args = parser.parse_args()

    # Query modes imply JSON output
    is_query_mode = args.validate or args.tickers or args.check_prices or args.list_indicators
    use_json = args.json_output or is_query_mode

    # --strategy is required unless --list-indicators
    if not args.list_indicators and args.strategy is None:
        parser.error("the following arguments are required: --strategy")

    # Shared timestamp and stem for file naming
    now = datetime.now()
    stem = Path(Path(args.strategy).stem).stem if args.strategy else ""
    ts = now.strftime("%Y%m%d_%H%M")

    # Set up logging -- logs/ dir created here, shared timestamp with CSV
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{ts}_{stem}_log.txt"
    _setup_logging(log_path, args.debug)

    try:
        # --- Query modes ---
        if args.list_indicators:
            result = list_indicators()
            _print_json({"status": "ok", "indicators": result})
            return

        if args.validate:
            validate(args.strategy)
            _print_json({"status": "ok", "valid": True})
            return

        if args.tickers:
            result = get_tickers(args.strategy)
            _print_json({"status": "ok", **result})
            return

        if args.check_prices:
            result = check_prices(args.strategy, args.db)
            _print_json({"status": "ok", **result})
            return

        # --- Default run mode ---
        logger = logging.getLogger("moa_allocations")
        t_start = time.monotonic()

        # Compile
        root = compile_strategy(args.strategy)

        # Extract tickers and max lookback
        tickers = sorted(collect_tickers(root))
        max_lookback = compute_max_lookback(root)

        end_date_iso = root.settings.end_date.isoformat()
        start_date_iso = root.settings.start_date.isoformat()

        # Filter synthetic cash placeholder -- pidb_ib has no data for it
        fetch_tickers = [t for t in tickers if t != _XCASHX]

        logger.info(
            "Strategy loaded: %s | tickers: %d | %s -> %s",
            args.strategy, len(fetch_tickers), start_date_iso, end_date_iso,
        )

        # Resolve precise fetch start: exactly max_lookback trading days before start_date
        if max_lookback > 0:
            fetch_start_iso = _resolve_lookback_start(fetch_tickers[0], start_date_iso, max_lookback, args.db)
        else:
            fetch_start_iso = start_date_iso

        # Fetch prices
        price_data = _default_price_fetcher(fetch_tickers, fetch_start_iso, end_date_iso, args.db)

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

        if use_json:
            traded = sorted(collect_traded_tickers(root))
            signal = sorted(collect_signal_tickers(root))
            _print_json({
                "status": "ok",
                "allocations_path": str(output_path.resolve()),
                "rows": len(df),
                "traded_tickers": traded,
                "signal_tickers": signal,
            })
        else:
            print(f"Written: {output_path}")

    except (DSLValidationError, PriceDataError, Exception) as exc:
        exit_code = _handle_error(exc, use_json)
        if not use_json:
            raise
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
