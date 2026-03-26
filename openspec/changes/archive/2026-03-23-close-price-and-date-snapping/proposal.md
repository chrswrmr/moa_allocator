## Why

The engine currently requires `start_date` and `end_date` in the strategy DSL to fall on exact trading days, which forces users to know the trading calendar before authoring a strategy.

## What Changes

- **Date snapping**: `run()` SHALL snap `start_date` and `end_date` to the nearest available trading day in the pidb_ib calendar before passing them to the price fetcher and engine. `start_date` snaps forward (next available date on or after); `end_date` snaps backward (last available date on or before).

## Capabilities

### New Capabilities

- `date-snapping`: Logic to snap an arbitrary calendar date to the nearest available trading day using the pidb_ib date index, applied to both `start_date` and `end_date` before any price fetch or engine call.

### Modified Capabilities

- `run-entry-point`: Requirement for exact trading-day `start_date`/`end_date` is relaxed — `run()` now snaps both dates before use. The `_resolve_lookback_start` function must also receive the snapped `start_date`.

## Impact

- **`moa_allocations/__init__.py`**: Add `_snap_to_trading_day(date, direction, db_path)` helper; call it for both `start_date` and `end_date` before `_resolve_lookback_start` and the price fetcher invocation.
- **`openspec/specs/run-entry-point/spec.md`**: Add date-snapping requirement and scenarios.
- **Strategy DSL / compiler**: No changes — DSL continues to accept any ISO date string; snapping happens at runtime in `run()`.
- **`Runner.__init__` / `price-data-error` spec**: No changes — date range validation operates on the already-snapped dates.
- **Custom price fetcher callers**: No impact — snapping only applies when the default fetcher is used (snapping requires pidb_ib calendar access).
