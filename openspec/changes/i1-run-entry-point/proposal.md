## Why

The compiler (C1-C4) and engine (E1-E4) are fully implemented, but there is no public entry point that wires them together with external price data. Callers have no way to go from a `.moastrat.json` file to an allocations DataFrame in a single call. `run()` closes this gap and is the prerequisite for downstream consumers (`bt_rebalancer`, `iba`).

## What Changes

- Add a `run(strategy_path: str) -> pd.DataFrame` function in `moa_allocations/__init__.py` — the single public entry point for the package.
- Orchestrate the full pipeline: `compile_strategy(path)` → extract tickers and date range from `RootNode.settings` → fetch prices via `pidb_ib`'s `PidbReader.get_matrix()` → convert Polars wide-format result to the `pd.DataFrame` contract expected by `Runner` → instantiate `Runner(root, price_data)` → call `runner.run()` → return the allocations DataFrame.
- `pidb_ib` is called exclusively from this function — no other module in the package imports or calls it.
- Compute the lookback-adjusted start date (`settings.start_date - max_lookback_days`) so the fetched price window satisfies the engine's input contract.

## Capabilities

### New Capabilities

- `run-entry-point`: Public `run()` function that wires compiler → price fetch → engine and returns the allocations DataFrame. Covers: function signature, pidb_ib integration, Polars-to-pandas conversion, lookback date math, error propagation, and the package's public API surface.

### Modified Capabilities

_(none — this is purely additive; no existing spec requirements change)_

## Impact

- **New file content:** `moa_allocations/__init__.py` (currently empty) gets the `run()` function.
- **New dependency:** `pidb_ib` (external package, accessed via `PidbReader` from `src.access`). Must be available on `PYTHONPATH` at runtime.
- **Cross-module wiring:** Imports `compile_strategy` from `moa_allocations.compiler` and `Runner` from `moa_allocations.engine`. No changes to those modules.
- **Data format bridge:** `PidbReader.get_matrix()` returns a Polars DataFrame in wide format; `Runner` expects a pandas DataFrame with `DatetimeIndex`. The conversion logic lives here.
