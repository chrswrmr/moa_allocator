## Context

`moa_allocations/__init__.py` contains `_default_price_fetcher`, `_snap_to_trading_day`, and `_resolve_lookback_start`, all of which use pidb_ib. Several issues exist:

1. **Wrong import path**: All three functions use `from access import PidbReader` — the old `moa_rebalancer` internal path. The correct import via the installed editable package is `from pidb_ib import PidbReader`. The current import will fail with `ModuleNotFoundError` unless `pidb_ib/src/` happens to be on `sys.path`.

2. **Wrong column assumption**: `_default_price_fetcher` assumes `get_matrix` returns bare symbol columns (`SPY`, `IWM`). It actually returns `{SYMBOL}_close_d` format. This causes `Runner.__init__` to raise `PriceDataError` for all tickers.

3. **No XCASHX filtering**: `XCASHX` is a synthetic cash placeholder used by the engine. If passed to `get_matrix`, pidb_ib has no data for it. The ticker list must be filtered before fetching.

4. **No symbol validation**: If pidb_ib returns fewer tickers than requested (e.g. unknown symbol), the error surfaces deep in the engine rather than at the fetch boundary.

5. **No error handling**: An absent pidb_ib install, a missing database file, or a zero-row result surfaces as uncontrolled exceptions rather than `PriceDataError`.

The `run-entry-point` spec also reflects the incorrect import path and column assumption.

## Goals / Non-Goals

**Goals:**
- Fix import path from `from access import PidbReader` to `from pidb_ib import PidbReader` in all three functions
- Fix `_default_price_fetcher` to strip the `_close_d` suffix from returned columns
- Filter `XCASHX` from the ticker list before calling `get_matrix()`
- Validate that all requested tickers are present in the returned result
- Add error handling for `ImportError`, `sqlite3.OperationalError`, and empty-DataFrame results
- Correct the `run-entry-point` spec to document the actual API contract

**Non-Goals:**
- Changing the `PriceFetcher` type signature or the `run()` public API
- Modifying the engine, compiler, or any algo/metric modules
- Adding pidb_ib error handling to `_snap_to_trading_day` or `_resolve_lookback_start` (they already propagate exceptions naturally; the calendar-fetch failure modes are the same as the price-fetch ones)
- NaN handling (ffill/bfill) — the engine already handles NaN via its metric functions; adding fill logic in the fetcher would mask data quality issues

## Decisions

### Decision: Fix import to `from pidb_ib import PidbReader`

The `pidb-ib` package is already declared as an editable dependency in `pyproject.toml` (`pidb-ib = { path = "../pidb_ib", editable = true }`). The correct public import is `from pidb_ib import PidbReader`, which goes through the package's `__init__.py`. The old `from access import PidbReader` relied on `pidb_ib/src/` being directly on `sys.path`, which is fragile and incorrect.

All three functions (`_snap_to_trading_day`, `_resolve_lookback_start`, `_default_price_fetcher`) use the lazy-import pattern — this is preserved, just with the correct module path.

### Decision: Filter XCASHX in `run()` before passing tickers to fetcher

`XCASHX` is a synthetic cash ticker that exists only in the engine's allocation logic. It should be filtered from the ticker list in `run()`, before any pidb_ib calls (date snapping, lookback resolution, and price fetching all receive tickers). This is cleaner than filtering inside each helper function.

**Alternative considered — filter inside `_default_price_fetcher` only**: The calendar helpers (`_snap_to_trading_day`, `_resolve_lookback_start`) use `tickers[0]` as the anchor. If `XCASHX` happened to be first alphabetically, those calls would also fail. Filtering once at the top of `run()` is safer.

### Decision: Validate returned symbols in `_default_price_fetcher`

After renaming columns, check that every requested ticker has a corresponding column. Raise `PriceDataError` listing the missing tickers. This catches the case where pidb_ib silently returns fewer columns than requested (e.g. unknown symbol).

### Decision: Strip suffix via column rename, not by dropping and re-fetching

The Polars result with `columns=["close_d"]` has the form `[date, SPY_close_d, IWM_close_d, ...]`. The rename is a simple dict comprehension: `{col: col.replace("_close_d", "") for col in df.columns}`. This is applied after `.to_pandas()` and before `.astype("float64")`.

**Alternative considered — fetch without specifying `columns`**: `get_matrix` defaults to `columns=["close_d"]` anyway, and explicitly passing it is clearer intent. Dropping the argument would not change the column names returned.

**Alternative considered — rename in Polars before converting**: Equivalent, but doing it in pandas after conversion keeps the conversion logic in one place.

### Decision: Raise `PriceDataError` (not a new exception class) for all pidb_ib failure modes

`PriceDataError` is already the canonical signal that Runner uses when price data is invalid. Re-using it for upstream fetch failures keeps the caller's error-handling surface uniform — `run()` already lets `PriceDataError` propagate.

**Alternative considered — new `PriceFetchError`**: Adds a new public exception and import surface with no benefit; callers would need to handle both.

### Decision: Catch errors only in `_default_price_fetcher`, not in the calendar helpers

`_snap_to_trading_day` and `_resolve_lookback_start` also use pidb_ib, but they are private helpers called only on the default-fetcher path. If pidb_ib is missing or the DB is absent, the `ImportError` / `OperationalError` bubbles up to `run()` before reaching the price fetch; wrapping it there would double-handle. A single guard in `_default_price_fetcher` is sufficient and keeps the change minimal.

## Risks / Trade-offs

- **Column rename assumption is fragile if `get_matrix` multi-column mode is ever used**: The `_close_d` strip is hard-coded for a single-column fetch. If a future change passes multiple columns, the rename logic will need to be revisited. Mitigated by the spec explicitly constraining `_default_price_fetcher` to call `columns=["close_d"]`.
- **`PriceDataError` now raised before `Runner`**: Callers that catch `PriceDataError` and assume it comes from `Runner.__init__` will still behave correctly (they just catch it earlier), but the error message will be different. Acceptable: the exception class is the stable contract, not the message text.
