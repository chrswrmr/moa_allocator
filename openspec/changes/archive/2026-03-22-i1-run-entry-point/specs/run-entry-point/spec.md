## ADDED Requirements

### Requirement: Public run function signature

The package SHALL expose a single public function `run(strategy_path: str, price_fetcher: PriceFetcher | None = None, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame` in `moa_allocations/__init__.py`.

`PriceFetcher` is defined as `Callable[[list[str], str, str], pd.DataFrame]` where the arguments are `(tickers, start_date, end_date)` — tickers as uppercase strings, dates as ISO-8601 date strings (e.g. `"2024-01-15"`).

`db_path` is passed to the default fetcher when `price_fetcher` is `None`. It is ignored when a custom `price_fetcher` is provided.

#### Scenario: Minimal invocation with default fetcher
- **WHEN** caller invokes `run("path/to/strategy.moastrat.json")` without a `price_fetcher` argument
- **THEN** the function SHALL compile the strategy, fetch prices using the default pidb_ib fetcher, run the engine, and return an allocations `pd.DataFrame`

#### Scenario: Custom price fetcher
- **WHEN** caller invokes `run("path/to/strategy.moastrat.json", price_fetcher=custom_fn)` where `custom_fn` matches the `PriceFetcher` signature
- **THEN** the function SHALL use `custom_fn` instead of the default pidb_ib fetcher to obtain price data

### Requirement: Pipeline orchestration order

`run()` SHALL execute the pipeline in this exact order:
1. `compile_strategy(strategy_path)` → `RootNode`
2. Extract tickers via `collect_tickers(root)` and max lookback via `compute_max_lookback(root)`
3. Compute lookback-adjusted fetch start date
4. Call `price_fetcher(tickers, fetch_start, end_date)` → `pd.DataFrame`
5. Instantiate `Runner(root, price_data)`
6. Call `runner.run()` → allocations `pd.DataFrame`
7. Return the allocations DataFrame

#### Scenario: Full pipeline execution
- **WHEN** caller invokes `run()` with a valid strategy file and the price fetcher returns valid data
- **THEN** the function SHALL call `compile_strategy`, then `collect_tickers` and `compute_max_lookback`, then the price fetcher, then `Runner`, then `runner.run()`, and return the resulting DataFrame

#### Scenario: Compiler failure stops pipeline
- **WHEN** `compile_strategy()` raises `DSLValidationError`
- **THEN** `run()` SHALL let the exception propagate without catching or wrapping it; no price fetch or engine call occurs

#### Scenario: Price fetcher failure stops pipeline
- **WHEN** the price fetcher raises any exception
- **THEN** `run()` SHALL let the exception propagate; no `Runner` instantiation occurs

#### Scenario: Runner validation failure
- **WHEN** `Runner.__init__()` raises `PriceDataError` (e.g. missing tickers, insufficient date range)
- **THEN** `run()` SHALL let the exception propagate

### Requirement: Lookback-adjusted fetch start date

`run()` SHALL compute the price fetch start date by converting the max lookback (in trading days) to calendar days using `ceil(max_lookback * 7 / 5) + 10`, then subtracting that from `settings.start_date`.

This ensures the fetched window always covers enough trading days for the engine's lookback requirements, accounting for weekends and holidays.

#### Scenario: Strategy with lookback metrics
- **WHEN** the compiled strategy has `compute_max_lookback(root) == 200` (trading days) and `settings.start_date == date(2024, 6, 1)`
- **THEN** the price fetcher SHALL be called with `start_date` = `"2024-06-01"` minus `ceil(200 * 7/5) + 10` = 290 calendar days, i.e. `"2023-08-15"`

#### Scenario: Strategy with no lookback
- **WHEN** the compiled strategy has `compute_max_lookback(root) == 0`
- **THEN** the price fetcher SHALL be called with `start_date` = `settings.start_date` (no adjustment, since `ceil(0 * 7/5) + 10 = 10` still provides a small buffer)

### Requirement: Ticker extraction for price fetch

`run()` SHALL pass the complete set of tickers from `collect_tickers(root)` to the price fetcher as a sorted `list[str]` of uppercase strings.

#### Scenario: Tickers from asset nodes and conditions
- **WHEN** the compiled tree contains asset nodes for `SPY`, `IWM` and an if_else condition referencing `QQQ`
- **THEN** the price fetcher SHALL be called with `tickers=["IWM", "QQQ", "SPY"]` (sorted, uppercase)

### Requirement: Default price fetcher wraps pidb_ib

The default price fetcher SHALL be a private function `_default_price_fetcher(tickers, start_date, end_date, db_path)` that:
1. Accepts `db_path` directly as a parameter (no env var lookup)
2. Instantiates `PidbReader(db_path)`
3. Calls `reader.get_matrix(symbols=tickers, columns=["close_d"], start=start_date, end=end_date)`
4. Converts the Polars DataFrame result to a pandas DataFrame matching the engine's price_data contract

#### Scenario: Successful pidb_ib fetch
- **WHEN** `db_path` points to a valid pidb_ib database and it contains data for the requested tickers and date range
- **THEN** the default fetcher SHALL return a `pd.DataFrame` with `DatetimeIndex`, uppercase ticker columns, and `float64` values

### Requirement: Polars-to-pandas conversion in default fetcher

The default fetcher SHALL convert `PidbReader.get_matrix()` output to the engine's price_data contract:
- The Polars `date` column (string, `"YYYY-MM-DD"` format) SHALL become a pandas `DatetimeIndex`
- Since `get_matrix` is called with a single column (`close_d`), the result columns are named directly after symbols (e.g. `SPY`, `IWM`) — these SHALL be preserved as-is
- All values SHALL be `float64`

#### Scenario: Single-column matrix conversion
- **WHEN** `get_matrix(symbols=["SPY", "IWM"], columns=["close_d"], ...)` returns a Polars DataFrame with columns `[date, SPY, IWM]`
- **THEN** the default fetcher SHALL return a pandas DataFrame with `DatetimeIndex` and columns `["SPY", "IWM"]` containing `float64` values

### Requirement: Expose collect_tickers and compute_max_lookback as public API

`collect_tickers` and `compute_max_lookback` SHALL be renamed from their current private `_`-prefixed forms to public functions in `moa_allocations/engine/runner.py` and exported from `moa_allocations.engine`.

`Runner.__init__()` SHALL continue to call these same functions internally — no duplication.

#### Scenario: Public import path
- **WHEN** external code runs `from moa_allocations.engine import collect_tickers, compute_max_lookback`
- **THEN** the import SHALL succeed and both functions SHALL accept a `RootNode` and return `set[str]` and `int` respectively

#### Scenario: Runner still uses them internally
- **WHEN** `Runner(root, price_data)` is instantiated
- **THEN** `Runner.__init__()` SHALL call `collect_tickers(root)` and `compute_max_lookback(root)` as before — the rename does not change engine behavior

### Requirement: No pidb_ib imports outside default fetcher

`pidb_ib` SHALL only be imported inside the `_default_price_fetcher()` function. No other module in `moa_allocations` SHALL import from `pidb_ib`.

#### Scenario: Lazy import isolation
- **WHEN** `run()` is called with a custom `price_fetcher`
- **THEN** `pidb_ib` SHALL NOT be imported at all — no `ImportError` even if `pidb_ib` is not installed

#### Scenario: Default fetcher imports pidb_ib at call time
- **WHEN** `run()` is called without a `price_fetcher` (using the default)
- **THEN** `pidb_ib` SHALL be imported inside `_default_price_fetcher()` — not at module level
