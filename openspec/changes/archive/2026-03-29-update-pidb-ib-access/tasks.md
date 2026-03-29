## 1. Fix import path

- [x] 1.1 In `moa_allocations/__init__.py`, change all `from access import PidbReader` to `from pidb_ib import PidbReader` (three occurrences: `_snap_to_trading_day`, `_resolve_lookback_start`, `_default_price_fetcher`)

## 2. Filter XCASHX

- [x] 2.1 In `run()`, filter `XCASHX` from the `tickers` list before the default-fetcher branch (before date snapping, lookback resolution, and price fetching)

## 3. Fix column renaming in default fetcher

- [x] 3.1 In `_default_price_fetcher`, rename `{SYMBOL}_close_d` columns to bare ticker names by stripping the `_close_d` suffix, after `.to_pandas()` and before `.astype("float64")`

## 4. Validate returned symbols

- [x] 4.1 In `_default_price_fetcher`, after column rename, verify all requested tickers are present as columns. Raise `PriceDataError` listing any missing tickers.

## 5. Add error handling to default fetcher

- [x] 5.1 Wrap the `PidbReader` import in try/except `ImportError` and raise `PriceDataError` with a message mentioning `pidb_ib`
- [x] 5.2 Wrap `PidbReader()` instantiation and `get_matrix()` call in try/except `sqlite3.OperationalError` and raise `PriceDataError` with a message including `db_path`
- [x] 5.3 After `get_matrix()` returns, check for empty DataFrame (zero rows) and raise `PriceDataError` with a message referencing tickers and date range

## 6. Update run-entry-point spec

- [x] 6.1 In `openspec/specs/run-entry-point/spec.md`, update import path requirement, column naming, XCASHX filtering, and symbol validation requirements per the delta spec

## 7. Tests

- [x] 7.1 Add test verifying the import path is `from pidb_ib import PidbReader`
- [x] 7.2 Add test that XCASHX is filtered out before price fetching
- [x] 7.3 Add test that columns are renamed from `{SYMBOL}_close_d` to bare ticker names
- [x] 7.4 Add test that `PriceDataError` is raised when a requested ticker is missing from the result
- [x] 7.5 Add test that `PriceDataError` is raised when `pidb_ib` is not importable
- [x] 7.6 Add test that `PriceDataError` is raised on `sqlite3.OperationalError`
- [x] 7.7 Add test that `PriceDataError` is raised when `get_matrix` returns an empty DataFrame
- [x] 7.8 Run `uv run pytest` and confirm all tests pass
