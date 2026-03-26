## 1. Implement `_snap_to_trading_day`

- [x] 1.1 Add `_snap_to_trading_day(date_str, direction, db_path)` to `moa_allocations/__init__.py` — lazy-imports `PidbReader`, fetches the full date series for the anchor ticker, and binary-searches for the nearest in-calendar date in the specified direction
- [x] 1.2 Raise `ValueError` when no ticker is available to use as anchor
- [x] 1.3 Raise `ValueError` when forward snap finds no date ≥ `date_str` in the calendar
- [x] 1.4 Raise `ValueError` when backward snap finds no date ≤ `date_str` in the calendar

## 2. Wire snapping into `run()`

- [x] 2.1 In the `price_fetcher is None` branch of `run()`, call `_snap_to_trading_day` for `start_date_iso` (forward) and `end_date_iso` (backward), storing results as `snapped_start` and `snapped_end`
- [x] 2.2 Pass `snapped_start` to `_resolve_lookback_start` (instead of the raw DSL date) and use `snapped_end` as the `end_date` argument to the price fetcher

## 3. Update `run-entry-point` spec

- [x] 3.1 Sync the delta spec at `openspec/changes/close-price-and-date-snapping/specs/run-entry-point/spec.md` into `openspec/specs/run-entry-point/spec.md` (add snapping step to pipeline order; update lookback requirement to reference snapped date)

## 4. Tests

- [x] 4.1 Write unit tests for `_snap_to_trading_day`: forward snap on a non-trading day, backward snap on a non-trading day, date already in calendar (pass-through), forward out-of-bounds raises `ValueError`, backward out-of-bounds raises `ValueError`
- [x] 4.2 Write an integration-style unit test for `run()` with a custom price fetcher confirming that snapping is NOT applied (DSL dates passed through unchanged)
- [x] 4.3 Run `uv run pytest` and confirm all tests pass
