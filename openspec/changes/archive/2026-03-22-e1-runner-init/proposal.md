## Why

The compiled strategy tree (from C1–C4) and the individual algos (from A1–A4) exist, but there is no `Runner` to wire them together. Without `Runner.__init__()`, the engine cannot attach AlgoStacks to nodes, validate price data, or prepare the numpy arrays that algos depend on. This is the prerequisite for the simulation loop (E2–E4).

## What Changes

- Implement `Runner.__init__(root: RootNode, price_data: pd.DataFrame)` in `moa_allocations/engine/runner.py`
- Traverse the compiled tree and attach the correct `AlgoStack` to each `StrategyNode` based on node type and parameters (per the AlgoStack composition table)
- Pre-convert all price and NAV series to numpy arrays and store on `node.perm`
- Validate that all required tickers are present in `price_data.columns` and date range covers `[start_date - max_lookback, end_date]`; raise `PriceDataError` otherwise
- Define `PriceDataError` exception class
- Wire `pidb_ib.get_prices()` as the price source (called externally; Runner receives the resulting DataFrame)
- Export `Runner` and `PriceDataError` from `moa_allocations/engine/__init__.py`

## Capabilities

### New Capabilities
- `runner-init`: Runner construction — tree traversal, AlgoStack attachment, price data validation, and numpy array pre-computation
- `price-data-error`: PriceDataError exception for missing tickers or insufficient date range

### Modified Capabilities
_(none — no existing spec requirements are changing)_

## Impact

- **New file:** `moa_allocations/engine/runner.py`
- **Modified file:** `moa_allocations/engine/__init__.py` (re-exports)
- **Dependencies:** imports from `engine.node`, `engine.strategy` (node classes), `engine.algos` (algo classes), `pidb_ib` (price source interface)
- **Architecture boundary:** Runner imports algo classes to construct AlgoStacks — this is the intended dependency direction (engine → algos). Compiler must never do this.
- **Downstream:** Unblocks E2 (simulation loop), E3 (passes), E4 (output)
