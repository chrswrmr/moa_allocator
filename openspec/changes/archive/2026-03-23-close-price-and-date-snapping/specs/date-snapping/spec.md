## ADDED Requirements

### Requirement: Snap date to nearest trading day
`_snap_to_trading_day(date_str, direction, anchor_ticker, db_path)` SHALL return the nearest trading day in the pidb_ib calendar for the given ISO-8601 date string.

- `direction="forward"`: return the first date ≥ `date_str` in the pidb_ib calendar (used for `start_date`).
- `direction="backward"`: return the last date ≤ `date_str` in the pidb_ib calendar (used for `end_date`).

The caller SHALL pass the anchor ticker as the first entry in the sorted ticker list. The function SHALL fetch the full date series for that ticker using `reader.get_matrix(symbols=[anchor_ticker], columns=["close_d"])` with no `start`/`end` arguments, then binary-search for the nearest in-calendar date.

#### Scenario: start_date on a non-trading day snaps forward
- **WHEN** `_snap_to_trading_day("2024-01-06", "forward", db_path)` is called and `2024-01-06` is a Saturday
- **THEN** it SHALL return `"2024-01-08"` (the next trading day)

#### Scenario: end_date on a non-trading day snaps backward
- **WHEN** `_snap_to_trading_day("2024-12-25", "backward", db_path)` is called and `2024-12-25` is not in the pidb_ib calendar
- **THEN** it SHALL return the most recent trading day before `2024-12-25`

#### Scenario: Date already in trading calendar is returned unchanged
- **WHEN** `_snap_to_trading_day` is called with a date that is already present in the pidb_ib calendar
- **THEN** it SHALL return that same date unchanged

#### Scenario: forward snap out of bounds raises ValueError
- **WHEN** `direction="forward"` and no trading day at or after `date_str` exists in the calendar
- **THEN** it SHALL raise `ValueError` with a message indicating `date_str` is beyond the available calendar range

#### Scenario: backward snap out of bounds raises ValueError
- **WHEN** `direction="backward"` and no trading day at or before `date_str` exists in the calendar
- **THEN** it SHALL raise `ValueError` with a message indicating `date_str` is before the available calendar range

#### Scenario: No tickers in strategy raises ValueError
- **WHEN** `run()` is called with the default fetcher and the compiled strategy contains no tickers
- **THEN** `run()` SHALL raise `ValueError` before calling `_snap_to_trading_day`, indicating no anchor ticker is available
