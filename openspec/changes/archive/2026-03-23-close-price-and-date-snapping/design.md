## Context

`moa_allocations/__init__.py` is the top-level orchestrator: it compiles the strategy, resolves the lookback-adjusted fetch start date, fetches prices from pidb_ib, and runs the engine. Currently both `start_date` and `end_date` in the DSL settings must already be trading days. If a user passes a weekend or holiday date, `_resolve_lookback_start` silently produces a wrong result (it looks for `start_date` as the last element of the returned date series — but if `start_date` is not in the calendar, that element is the prior trading day), and the engine's date-range validation may reject the price data or produce off-by-one results.

## Goals / Non-Goals

**Goals:**
- Add `_snap_to_trading_day(date_str, direction, db_path)` — returns the nearest trading day in the pidb_ib calendar.
  - `direction="forward"`: first date ≥ `date_str` (for `start_date`).
  - `direction="backward"`: last date ≤ `date_str` (for `end_date`).
- Apply snapping to `start_date` and `end_date` before any downstream call (`_resolve_lookback_start`, price fetcher, engine).

**Non-Goals:**
- Snapping for custom `price_fetcher` callers — they receive the unmodified DSL dates (snapping requires pidb_ib calendar access).
- Changes to the DSL schema or compiler — dates remain ISO strings validated as-is.
- Changes to `Runner.__init__` or the `price-data-error` spec — they operate on already-snapped dates.

## Decisions

### Decision 1: Snap at the `run()` boundary, not inside `_resolve_lookback_start`

**Choice:** Snap both dates once at the top of `run()` (default-fetcher branch) before any downstream call.

**Why:** A single snapping point is easier to reason about and test. Snapping inside `_resolve_lookback_start` would fix the lookback start but leave `end_date` unsnapped and the price fetcher would receive a non-trading-day end date. Doing it once at the entry point means all downstream code sees consistent, snapped dates.

**Alternative considered:** Snap inside `_resolve_lookback_start` and the fetcher separately. Rejected — double-snapping risk and two call sites to maintain.

### Decision 2: Use the anchor ticker's existing date series for snapping

**Choice:** `_snap_to_trading_day` calls `reader.get_matrix(symbols=[anchor], columns=["close_d"])` with no start/end to retrieve the full date series, then binary-searches for the snapped date.

**Why:** pidb_ib is the authoritative trading calendar for this backtest. Using the same ticker already used for lookback resolution keeps the calendar source consistent. Fetching the full series is acceptable because the dataset is finite and this is a one-time setup call.

**Alternative considered:** Use a dedicated calendar table or a pandas `BDay` offset. Rejected — pidb_ib may include/exclude dates that differ from generic business-day rules (e.g. early closes, exchange-specific holidays). The actual price data is the ground truth.

**Anchor ticker:** The first ticker in the sorted ticker list (same as `_resolve_lookback_start`). If the strategy has no tickers this is a degenerate case — raise `ValueError`.

### Decision 3: Fail loudly if snapping goes out of bounds

**Choice:** If snapping `start_date` forward finds no date in the calendar at or after `start_date`, raise `ValueError`. Same for `end_date` backward.

**Why:** Silent out-of-range snapping would produce a date range that doesn't match the user's intent and would be very hard to debug. An explicit error with a clear message is better.

### Decision 4: Snapping applies only when using the default fetcher

**Choice:** The snapping block executes inside the `if price_fetcher is None` branch.

**Why:** Custom fetchers manage their own data sources and calendars. Injecting snapping into a custom-fetcher call would be a surprise violation of the custom-fetcher contract defined in `run-entry-point`.

## Risks / Trade-offs

- **Extra pidb_ib round-trip**: `_snap_to_trading_day` is an additional DB read on top of `_resolve_lookback_start`. For small strategies the overhead is negligible; for production batch runs it may add ~10–50 ms. Acceptable trade-off for correctness.
- **Anchor ticker availability**: If the anchor ticker has no data at or near the requested date, snapping will return a wrong date or raise. This is already a risk with `_resolve_lookback_start` and is documented as a known limitation. The `PriceDataError` from `Runner.__init__` will catch downstream mismatches.
- **DSL dates not validated for calendar membership**: This is intentional (Non-Goals). Users who specify 2024-12-25 get silently snapped to the next trading day. A future change could add a DSL-level warning.
