## Why

The current `_default_price_fetcher` implementation was written against incorrect assumptions about the `pidb_ib` API: `get_matrix(columns=["close_d"])` returns columns named `{SYMBOL}_close_d` (e.g. `SPY_close_d`), not bare `{SYMBOL}` names (e.g. `SPY`). This means the DataFrame handed to `Runner` has wrong column names, causing every run to fail with a `PriceDataError` for missing tickers. The `run-entry-point` spec also reflects this incorrect assumption and must be corrected alongside the implementation.

## What Changes

- **Fix import path**: all three functions use `from access import PidbReader` (the old `moa_rebalancer` path). The correct import via the installed editable package is `from pidb_ib import PidbReader`.
- **Fix column renaming in `_default_price_fetcher`**: strip the `_close_d` suffix from the Polars result columns so the pandas price_data has bare ticker columns (`SPY`, `IWM`), matching the engine's contract.
- **Filter `XCASHX` before fetching**: `XCASHX` is a synthetic cash placeholder, not a real ticker in pidb_ib. Filter it out of the ticker list before calling `get_matrix()`.
- **Validate returned symbols**: after `get_matrix()`, verify all requested tickers are present in the result columns. Raise `PriceDataError` if any are missing.
- **Correct the spec**: the `run-entry-point` spec §"Polars-to-pandas conversion" currently states columns come back as bare symbols; update it to reflect the actual `{SYMBOL}_close_d` output and the renaming step required.
- **Add error handling in `_default_price_fetcher`**: catch `ImportError` (pidb_ib not installed), `sqlite3.OperationalError` (DB not found/corrupt), and empty-DataFrame result — raise `PriceDataError` with a clear message in each case, consistent with the error-handling pattern described in `PIDB_ACCESS_GUIDE.md`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities

- `run-entry-point`: The §"Polars-to-pandas conversion in default fetcher" requirement states the wrong column naming contract and the wrong import path. It must be updated to document: (1) the correct import `from pidb_ib import PidbReader`, (2) that `get_matrix` returns `{SYMBOL}_close_d` columns and the fetcher must rename them, (3) `XCASHX` filtering, (4) returned-symbol validation.

## Impact

- `moa_allocations/__init__.py` — fix import path in all three functions, column rename in `_default_price_fetcher`, XCASHX filtering, symbol validation, error handling
- `openspec/specs/run-entry-point/spec.md` — update import path, column naming, XCASHX filtering, symbol validation requirements and scenarios
- No changes to the DSL schema, compiler, engine core, or any algo/metric modules
- All existing tests that supply a custom `price_fetcher` are unaffected; tests that exercise the default fetcher must be updated/added
