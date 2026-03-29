## MODIFIED Requirements

### Requirement: PidbReader import path

All pidb_ib imports in `moa_allocations/__init__.py` SHALL use `from pidb_ib import PidbReader`, not `from access import PidbReader`.

#### Scenario: Import path
- **GIVEN** `pidb-ib` is installed as an editable dependency
- **WHEN** any function in `__init__.py` imports `PidbReader`
- **THEN** it SHALL use `from pidb_ib import PidbReader`

### Requirement: Polars-to-pandas conversion in default fetcher

The default fetcher SHALL convert `PidbReader.get_matrix()` output to the engine's price_data contract:
- The Polars `date` column (`"YYYY-MM-DD"` format) SHALL become a pandas `DatetimeIndex`
- `get_matrix` called with `columns=["close_d"]` returns columns named `{SYMBOL}_close_d` (e.g. `SPY_close_d`, `IWM_close_d`). The fetcher SHALL rename each such column to its bare ticker name by stripping the `_close_d` suffix, so the resulting pandas DataFrame has columns `["SPY", "IWM"]`.
- All values SHALL be `float64`

#### Scenario: Single-column matrix conversion
- **WHEN** `get_matrix(symbols=["SPY", "IWM"], columns=["close_d"], ...)` returns a Polars DataFrame with columns `[date, SPY_close_d, IWM_close_d]`
- **THEN** the default fetcher SHALL return a pandas DataFrame with `DatetimeIndex` and columns `["SPY", "IWM"]` containing `float64` values

### Requirement: XCASHX filtering

`run()` SHALL filter the synthetic `XCASHX` ticker from the ticker list before any pidb_ib calls (date snapping, lookback resolution, and price fetching).

#### Scenario: Strategy with XCASHX
- **GIVEN** a strategy whose `collect_tickers()` returns `["IWM", "SPY", "XCASHX"]`
- **WHEN** `run()` is called with no custom `price_fetcher`
- **THEN** only `["IWM", "SPY"]` SHALL be passed to the date snapping, lookback, and price fetch functions

### Requirement: Returned symbol validation

`_default_price_fetcher` SHALL verify that all requested tickers are present as columns in the result after renaming. If any are missing, it SHALL raise `PriceDataError` listing the missing tickers.

#### Scenario: Missing ticker in result
- **WHEN** `get_matrix` is called with `symbols=["SPY", "FAKE"]` and returns only `[date, SPY_close_d]`
- **THEN** `_default_price_fetcher` SHALL raise `PriceDataError` with a message containing `"FAKE"`

## ADDED Requirements

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
