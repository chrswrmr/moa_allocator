# run-entry-point

**Module:** `moa_allocations/__init__.py`, `moa_allocations/engine/runner.py`
**Purpose:** Public entry point that wires the compiler, price fetching, and engine into a single `run()` call, plus query functions for validation, ticker extraction, price checking, and indicator listing.
**Modified:** cli-interface-upgrade

---

## Requirements

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

---

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

---

### Requirement: Ticker extraction for price fetch

`run()` SHALL pass the tickers from `collect_tickers(root)`, excluding the synthetic `XCASHX` placeholder, to the price fetcher as a sorted `list[str]` of uppercase strings.

#### Scenario: Tickers from asset nodes and conditions
- **WHEN** the compiled tree contains asset nodes for `SPY`, `IWM` and an if_else condition referencing `QQQ`
- **THEN** the price fetcher SHALL be called with `tickers=["IWM", "QQQ", "SPY"]` (sorted, uppercase)

---

### Requirement: Default price fetcher wraps pidb_ib

The default price fetcher SHALL be a private function `_default_price_fetcher(tickers, start_date, end_date, db_path)` that:
1. Accepts `db_path` directly as a parameter (no env var lookup)
2. Instantiates `PidbReader(db_path)`
3. Calls `reader.get_matrix(symbols=tickers, columns=["close_d"], start=start_date, end=end_date)`
4. Converts the Polars DataFrame result to a pandas DataFrame matching the engine's price_data contract

#### Scenario: Successful pidb_ib fetch
- **WHEN** `db_path` points to a valid pidb_ib database and it contains data for the requested tickers and date range
- **THEN** the default fetcher SHALL return a `pd.DataFrame` with `DatetimeIndex`, uppercase ticker columns, and `float64` values

---

### Requirement: PidbReader import path

All pidb_ib imports in `moa_allocations/__init__.py` SHALL use `from pidb_ib import PidbReader`, not `from access import PidbReader`.

#### Scenario: Import path
- **GIVEN** `pidb-ib` is installed as an editable dependency
- **WHEN** any function in `__init__.py` imports `PidbReader`
- **THEN** it SHALL use `from pidb_ib import PidbReader`

---

### Requirement: XCASHX filtering

`run()` SHALL filter the synthetic `XCASHX` ticker from the ticker list before passing tickers to any fetcher (default or custom). No real price data exists for `XCASHX`.

#### Scenario: Strategy with XCASHX
- **GIVEN** a strategy whose `collect_tickers()` returns `["IWM", "SPY", "XCASHX"]`
- **WHEN** `run()` is called
- **THEN** only `["IWM", "SPY"]` SHALL be passed to the price fetcher (and to date snapping and lookback resolution when using the default fetcher)

---

### Requirement: Returned symbol validation

`_default_price_fetcher` SHALL verify that all requested tickers are present as columns in the result after renaming. If any are missing, it SHALL raise `PriceDataError` listing the missing tickers.

#### Scenario: Missing ticker in result
- **WHEN** `get_matrix` is called with `symbols=["SPY", "FAKE"]` and returns only `[date, SPY_close_d]`
- **THEN** `_default_price_fetcher` SHALL raise `PriceDataError` with a message containing `"FAKE"`

---

### Requirement: Polars-to-pandas conversion in default fetcher

The default fetcher SHALL convert `PidbReader.get_matrix()` output to the engine's price_data contract:
- The Polars `date` column (string, `"YYYY-MM-DD"` format) SHALL become a pandas `DatetimeIndex`
- `get_matrix` called with `columns=["close_d"]` returns columns named `{SYMBOL}_close_d` (e.g. `SPY_close_d`, `IWM_close_d`). The fetcher SHALL rename each such column to its bare ticker name by stripping the `_close_d` suffix, so the resulting pandas DataFrame has columns `["SPY", "IWM"]`.
- All values SHALL be `float64`

#### Scenario: Single-column matrix conversion
- **WHEN** `get_matrix(symbols=["SPY", "IWM"], columns=["close_d"], ...)` returns a Polars DataFrame with columns `[date, SPY_close_d, IWM_close_d]`
- **THEN** the default fetcher SHALL return a pandas DataFrame with `DatetimeIndex` and columns `["SPY", "IWM"]` containing `float64` values

---

### Requirement: Default fetcher raises PriceDataError on pidb_ib import failure

`_default_price_fetcher` SHALL catch `ImportError` when importing `PidbReader` and raise `PriceDataError` with a message indicating that the `pidb_ib` package is not available.

#### Scenario: pidb_ib not installed
- **WHEN** `pidb_ib` is not installed and `_default_price_fetcher` is called
- **THEN** it SHALL raise `PriceDataError` with a message containing `"pidb_ib"`

---

### Requirement: Default fetcher raises PriceDataError on database error

`_default_price_fetcher` SHALL catch `sqlite3.OperationalError` raised by `PidbReader` or `get_matrix` and raise `PriceDataError` with a message indicating the database path and the underlying error.

#### Scenario: Database file not found
- **WHEN** `db_path` points to a non-existent or corrupt SQLite file and `_default_price_fetcher` is called
- **THEN** it SHALL raise `PriceDataError` with a message that includes the `db_path` value

---

### Requirement: Default fetcher raises PriceDataError on empty result

`_default_price_fetcher` SHALL check that the Polars DataFrame returned by `get_matrix` has at least one row. If the result is empty, it SHALL raise `PriceDataError` with a message indicating that no price data was returned for the requested tickers and date range.

#### Scenario: No data for requested range
- **WHEN** `get_matrix` returns an empty Polars DataFrame (zero rows)
- **THEN** `_default_price_fetcher` SHALL raise `PriceDataError` with a message referencing the tickers and date range

---

### Requirement: Expose collect_tickers and compute_max_lookback as public API

`collect_tickers` and `compute_max_lookback` SHALL be public functions in `moa_allocations/engine/runner.py` and exported from `moa_allocations.engine`.

`Runner.__init__()` SHALL continue to call these same functions internally — no duplication.

#### Scenario: Public import path
- **WHEN** external code runs `from moa_allocations.engine import collect_tickers, compute_max_lookback`
- **THEN** the import SHALL succeed and both functions SHALL accept a `RootNode` and return `set[str]` and `int` respectively

#### Scenario: Runner still uses them internally
- **WHEN** `Runner(root, price_data)` is instantiated
- **THEN** `Runner.__init__()` SHALL call `collect_tickers(root)` and `compute_max_lookback(root)` as before

---

### Requirement: No pidb_ib imports outside default fetcher code path

`pidb_ib` SHALL only be imported inside the default-fetcher code path — specifically `_default_price_fetcher()`, `_snap_to_trading_day()`, and `_resolve_lookback_start()`. No other module in `moa_allocations` SHALL import from `pidb_ib`, and it SHALL never be imported at module level.

#### Scenario: Lazy import isolation
- **WHEN** `run()` is called with a custom `price_fetcher`
- **THEN** `pidb_ib` SHALL NOT be imported at all — no `ImportError` even if `pidb_ib` is not installed

#### Scenario: Default fetcher imports pidb_ib at call time
- **WHEN** `run()` is called without a `price_fetcher` (using the default)
- **THEN** `pidb_ib` SHALL be imported inside the default-fetcher helper functions — not at module level

---

### Requirement: validate function compiles and validates strategy

`moa_allocations/__init__.py` SHALL expose `validate(strategy_path: str) -> bool`. It SHALL call `compile_strategy(strategy_path)` and return `True` on success. If compilation raises `DSLValidationError`, the exception SHALL propagate to the caller (not caught).

#### Scenario: Valid strategy returns True

- **WHEN** `validate("path/to/valid.moastrat.json")` is called
- **THEN** it SHALL return `True`

#### Scenario: Invalid strategy raises DSLValidationError

- **WHEN** `validate("path/to/invalid.moastrat.json")` is called and the strategy has a validation error
- **THEN** `DSLValidationError` SHALL propagate with `node_id`, `node_name`, and `message`

---

### Requirement: get_tickers function extracts traded and signal tickers

`moa_allocations/__init__.py` SHALL expose `get_tickers(strategy_path: str) -> dict`. It SHALL compile the strategy and return a dict with:

- `traded_tickers`: sorted list of all AssetNode leaf tickers, excluding `XCASHX`
- `signal_tickers`: sorted list of tickers in `if_else` condition `lhs`/`rhs` `asset` fields that are NOT in the traded set

If compilation fails, `DSLValidationError` SHALL propagate.

#### Scenario: Strategy with traded and signal tickers

- **WHEN** `get_tickers("strat.json")` is called on a strategy with asset leaves `SPY`, `TLT` and an if_else condition referencing `VIXY`
- **THEN** it SHALL return `{"traded_tickers": ["SPY", "TLT"], "signal_tickers": ["VIXY"]}`

#### Scenario: All condition tickers are traded

- **WHEN** `get_tickers("strat.json")` is called on a strategy where all condition tickers are also asset leaves
- **THEN** `signal_tickers` SHALL be `[]`

#### Scenario: XCASHX excluded

- **WHEN** the strategy contains an XCASHX asset leaf
- **THEN** XCASHX SHALL NOT appear in either list

---

### Requirement: check_prices function verifies price data availability

`moa_allocations/__init__.py` SHALL expose `check_prices(strategy_path: str, db_path: str) -> dict`. It SHALL:

1. Compile the strategy (propagate `DSLValidationError` on failure)
2. Collect all tickers (traded + signal, excluding XCASHX)
3. Compute the lookback-adjusted date range
4. Fetch data via `get_matrix` and inspect for missing tickers or date gaps

On success: return `{"prices_available": True}`.
On missing data: raise `PriceDataError` with details about missing tickers and/or dates.

#### Scenario: All data available

- **WHEN** `check_prices("strat.json", "path/to/db")` is called and all tickers have data
- **THEN** it SHALL return `{"prices_available": True}`

#### Scenario: Missing tickers

- **WHEN** a ticker in the strategy has no data in pidb_ib
- **THEN** `PriceDataError` SHALL be raised with a message listing the missing tickers

#### Scenario: Compilation failure

- **WHEN** the strategy is invalid
- **THEN** `DSLValidationError` SHALL propagate (not `PriceDataError`)

---

### Requirement: list_indicators function returns engine indicator metadata

`moa_allocations/__init__.py` SHALL expose `list_indicators() -> list[dict]`. It SHALL read the `_DISPATCH` table and lookback sets from `moa_allocations.engine.algos.metrics` and return a list of dicts, each with:

- `name`: the metric function name (string)
- `requires_lookback`: `True` if the function is in `_NEEDS_LOOKBACK_PRICES` or `_NEEDS_LOOKBACK_RETURNS`, `False` otherwise (boolean)

The list SHALL be sorted alphabetically by `name`.

#### Scenario: Returns all dispatch entries

- **WHEN** `list_indicators()` is called
- **THEN** the returned list SHALL contain exactly the keys from `_DISPATCH`, one entry per key

#### Scenario: current_price does not require lookback

- **WHEN** `list_indicators()` is called
- **THEN** the entry for `"current_price"` SHALL have `"requires_lookback": False`

#### Scenario: Sorted alphabetically

- **WHEN** `list_indicators()` is called
- **THEN** the entries SHALL be sorted by `name` in ascending alphabetical order

---

### Requirement: collect_traded_tickers function

`moa_allocations/engine/runner.py` SHALL expose `collect_traded_tickers(root: RootNode) -> set[str]`. It SHALL walk the strategy tree and return all AssetNode leaf tickers, excluding `XCASHX`.

#### Scenario: Asset leaves only

- **WHEN** `collect_traded_tickers(root)` is called on a tree with AssetNode leaves `SPY`, `TLT`, `XCASHX`
- **THEN** it SHALL return `{"SPY", "TLT"}`

#### Scenario: Condition tickers excluded

- **WHEN** the tree has an if_else condition referencing `VIXY` but no `VIXY` AssetNode
- **THEN** `VIXY` SHALL NOT be in the result

---

### Requirement: collect_signal_tickers function

`moa_allocations/engine/runner.py` SHALL expose `collect_signal_tickers(root: RootNode) -> set[str]`. It SHALL walk the strategy tree and return tickers referenced in `if_else` condition `lhs`/`rhs` `asset` fields that are NOT AssetNode leaves. `XCASHX` SHALL be excluded.

#### Scenario: Signal ticker not traded

- **WHEN** the tree has an if_else condition referencing `VIXY` and `VIXY` is not an AssetNode leaf
- **THEN** `collect_signal_tickers` SHALL return a set containing `"VIXY"`

#### Scenario: Condition ticker is also traded

- **WHEN** the tree has an if_else condition referencing `SPY` and `SPY` is also an AssetNode leaf
- **THEN** `SPY` SHALL NOT be in the signal tickers set

#### Scenario: No conditions

- **WHEN** the strategy has no if_else nodes
- **THEN** `collect_signal_tickers` SHALL return an empty set
