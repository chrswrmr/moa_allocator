## MODIFIED Requirements

### Requirement: Pipeline orchestration order

`run()` SHALL execute the pipeline in this exact order:
1. `compile_strategy(strategy_path)` → `RootNode`
2. Extract tickers via `collect_tickers(root)` and max lookback via `compute_max_lookback(root)`
3. When `price_fetcher is None` (default fetcher), snap `settings.start_date` forward and `settings.end_date` backward to the nearest trading days using `_snap_to_trading_day` — producing `snapped_start` and `snapped_end`. For custom fetchers, use the DSL dates as-is.
4. Resolve precise fetch start date (via trading calendar lookup when `max_lookback > 0`, else `snapped_start`)
5. Call `price_fetcher(tickers, fetch_start, snapped_end)` → `pd.DataFrame`
6. Instantiate `Runner(root, price_data)`
7. Call `runner.run()` → allocations `pd.DataFrame`
8. Return the allocations DataFrame

#### Scenario: Full pipeline execution
- **WHEN** caller invokes `run()` with a valid strategy file and the price fetcher returns valid data
- **THEN** the function SHALL call `compile_strategy`, then `collect_tickers` and `compute_max_lookback`, then snap both dates (default fetcher only), then the price fetcher, then `Runner`, then `runner.run()`, and return the resulting DataFrame

#### Scenario: Compiler failure stops pipeline
- **WHEN** `compile_strategy()` raises `DSLValidationError`
- **THEN** `run()` SHALL let the exception propagate without catching or wrapping it; no price fetch or engine call occurs

#### Scenario: Price fetcher failure stops pipeline
- **WHEN** the price fetcher raises any exception
- **THEN** `run()` SHALL let the exception propagate; no `Runner` instantiation occurs

#### Scenario: Runner validation failure
- **WHEN** `Runner.__init__()` raises `PriceDataError` (e.g. missing tickers, insufficient date range)
- **THEN** `run()` SHALL let the exception propagate

---

### Requirement: Lookback-adjusted fetch start date

When `max_lookback > 0`, `run()` SHALL resolve the precise fetch start date by querying the trading calendar from pidb_ib via `_resolve_lookback_start`, passing the snapped `start_date` (not the raw DSL date). Calendar-day approximations (e.g. `7/5` multipliers) SHALL NOT be used — pidb_ib guarantees one row per trading day, so the trading calendar itself is the source of truth.

`_resolve_lookback_start(anchor_ticker, start_date, max_lookback, db_path)` SHALL:
1. Fetch all dates up to and including `start_date` for `anchor_ticker` using `get_matrix(..., end=start_date)`
2. Locate `start_date` as the last row (index `pos = len(dates) - 1`)
3. Return `dates[pos - max_lookback]` as the fetch start date

When `max_lookback == 0`, the fetch start date SHALL equal the snapped `start_date` (no lookback adjustment needed).

#### Scenario: Strategy with lookback metrics
- **WHEN** the compiled strategy has `compute_max_lookback(root) == 200` and `settings.start_date` snaps to `"2021-02-24"`
- **THEN** `_resolve_lookback_start` SHALL be called with the snapped date, and the price fetcher SHALL be called with `start_date` equal to the date exactly 200 trading days before `"2021-02-24"` in the pidb_ib calendar

#### Scenario: Strategy with no lookback
- **WHEN** the compiled strategy has `compute_max_lookback(root) == 0`
- **THEN** the price fetcher SHALL be called with `start_date` = snapped `settings.start_date`

#### Scenario: Insufficient history
- **WHEN** `_resolve_lookback_start` finds fewer than `max_lookback` rows before `start_date`
- **THEN** it SHALL raise `ValueError` with a message indicating how many bars are available vs required
