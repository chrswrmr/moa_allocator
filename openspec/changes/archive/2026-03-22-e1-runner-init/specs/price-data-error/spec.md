## ADDED Requirements

### Requirement: PriceDataError exception class

`PriceDataError` SHALL be a custom exception class inheriting from `Exception`, defined in `moa_allocations.engine.runner`. It SHALL accept a `message: str` parameter. It SHALL be importable from `moa_allocations.engine`.

#### Scenario: PriceDataError is importable
- **WHEN** a caller imports `from moa_allocations.engine import PriceDataError`
- **THEN** the import SHALL succeed and `PriceDataError` SHALL be a subclass of `Exception`

#### Scenario: PriceDataError carries a message
- **WHEN** `PriceDataError("SPY not found in price_data")` is raised
- **THEN** `str(error)` SHALL equal `"SPY not found in price_data"`

---

### Requirement: Validation of ticker coverage

`Runner.__init__` SHALL raise `PriceDataError` if any ticker collected from the tree (asset leaves and condition references) is missing from `price_data.columns`. The error message SHALL list all missing tickers.

#### Scenario: Single missing ticker
- **WHEN** the tree references ticker `"GLD"` but `price_data.columns` contains only `["SPY", "BND"]`
- **THEN** `Runner.__init__` SHALL raise `PriceDataError` with a message containing `"GLD"`

#### Scenario: Multiple missing tickers
- **WHEN** the tree references tickers `["SPY", "GLD", "TLT"]` but `price_data.columns` contains only `["SPY"]`
- **THEN** `Runner.__init__` SHALL raise `PriceDataError` with a message containing both `"GLD"` and `"TLT"`

#### Scenario: All tickers present
- **WHEN** every ticker in the tree exists in `price_data.columns`
- **THEN** `Runner.__init__` SHALL NOT raise `PriceDataError` for ticker coverage

---

### Requirement: Validation of date range coverage

`Runner.__init__` SHALL raise `PriceDataError` if `price_data.index` does not cover the required date range `[start_date - max_lookback trading days, end_date]`. The check SHALL compare against the actual `DatetimeIndex` of `price_data`.

#### Scenario: Price data starts too late
- **WHEN** `settings.start_date` is `2024-01-15`, `max_lookback` is `200` trading days, and `price_data.index[0]` is `2023-10-01` (fewer than 200 trading days before start_date)
- **THEN** `Runner.__init__` SHALL raise `PriceDataError` with a message indicating insufficient history

#### Scenario: Price data ends too early
- **WHEN** `settings.end_date` is `2024-12-31` and `price_data.index[-1]` is `2024-11-30`
- **THEN** `Runner.__init__` SHALL raise `PriceDataError` with a message indicating the end date is not covered

#### Scenario: Sufficient date range
- **WHEN** `price_data.index` starts at least `max_lookback` trading days before `start_date` and ends on or after `end_date`
- **THEN** `Runner.__init__` SHALL NOT raise `PriceDataError` for date range

#### Scenario: Zero max_lookback
- **WHEN** `max_lookback` is `0` (no lookback-dependent algos in the tree)
- **THEN** date range validation SHALL only require `price_data.index[0] <= start_date` and `price_data.index[-1] >= end_date`
