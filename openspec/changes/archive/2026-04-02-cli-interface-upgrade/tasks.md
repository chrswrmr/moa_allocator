## 1. Ticker extraction functions

- [x] 1.1 Add `collect_traded_tickers(root) -> set[str]` to `engine/runner.py` — walks tree, returns AssetNode leaf tickers excluding XCASHX
- [x] 1.2 Add `collect_signal_tickers(root) -> set[str]` to `engine/runner.py` — returns if_else condition tickers not in traded set, excluding XCASHX
- [x] 1.3 Export `collect_traded_tickers` and `collect_signal_tickers` from `moa_allocations.engine`
- [x] 1.4 Add tests for both functions (traded-only strategy, strategy with signal tickers, XCASHX exclusion, overlap case)

## 2. Public API functions in `__init__.py`

- [x] 2.1 Add `validate(strategy_path: str) -> bool` — calls `compile_strategy`, returns True, lets DSLValidationError propagate
- [x] 2.2 Add `get_tickers(strategy_path: str) -> dict` — compiles, returns `{"traded_tickers": [...], "signal_tickers": [...]}`
- [x] 2.3 Add `check_prices(strategy_path: str, db_path: str) -> dict` — compiles, collects tickers, computes lookback-adjusted range, fetches via `get_matrix`, inspects for missing tickers/dates, returns `{"prices_available": True}` or raises PriceDataError
- [x] 2.4 Add `list_indicators() -> list[dict]` — reads `_DISPATCH` and lookback sets from `metrics.py`, returns sorted list with `name` and `requires_lookback`
- [x] 2.5 Add tests for all four public functions

## 3. CLI argument parsing

- [x] 3.1 Add `--json` flag to argparse
- [x] 3.2 Add mutually exclusive group with `--validate`, `--tickers`, `--check-prices`, `--list-indicators`
- [x] 3.3 Make `--strategy` not required when `--list-indicators` is used
- [x] 3.4 Update argparse description and epilog with comprehensive `--help` text covering output schemas, exit codes, and error format

## 4. CLI dispatch and output

- [x] 4.1 Add dispatch logic in `main()`: route to `validate`, `get_tickers`, `check_prices`, `list_indicators`, or default run based on query flags
- [x] 4.2 Wrap query mode results in `{"status": "ok", ...}` JSON and print to stdout
- [x] 4.3 Add `--json` output for default run mode: `{"status": "ok", "allocations_path": ..., "rows": ..., "traded_tickers": ..., "signal_tickers": ...}`
- [x] 4.4 Preserve existing `"Written: {path}"` output when `--json` is not passed

## 5. Exit codes and error handling

- [x] 5.1 Add top-level try/except in `main()` mapping DSLValidationError → exit 1, PriceDataError → exit 2, Exception → exit 3
- [x] 5.2 When `--json` or query mode is active, write error JSON to stdout (`{"status": "error", "code": N, ...}`) before exiting
- [x] 5.3 When no `--json`, let tracebacks go to stderr as before

## 6. stdout/stderr discipline

- [x] 6.1 Change `StreamHandler` in `_setup_logging` to explicitly use `sys.stderr`
- [x] 6.2 Verify no other `print()` or log calls write to stdout during pipeline execution (except the final result)

## 7. Module entry point

- [x] 7.1 Create `moa_allocations/__main__.py` that imports and calls `main()` from `main`
- [x] 7.2 Verify `python -m moa_allocations --help` works

## 8. Integration tests

- [x] 8.1 Test `--validate` with valid and invalid strategies (exit codes + JSON output)
- [x] 8.2 Test `--tickers` output matches expected traded/signal split
- [x] 8.3 Test `--check-prices` with valid database (exit 0) and missing ticker (exit 2)
- [x] 8.4 Test `--list-indicators` returns all dispatch entries with correct `requires_lookback`
- [x] 8.5 Test `--json` run mode output schema
- [x] 8.6 Test mutual exclusivity of query flags
- [x] 8.7 Run full existing test suite (`uv run pytest`) to confirm no regressions
