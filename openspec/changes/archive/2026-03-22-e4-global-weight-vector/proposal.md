## Why

The engine can execute the Upward and Downward passes (E1–E3) but produces no usable output. After the Downward Pass, each node holds local weights relative to its parent — these must be flattened into a single global weight vector per day and assembled into the allocations DataFrame that downstream consumers (`bt_rebalancer`, `iba`) expect. Without this, `Runner.run()` is a no-op.

## What Changes

- Implement global weight flattening: walk root → leaves after each Downward Pass, multiply local weights along each path to produce `global_weight(leaf) = ∏ local_weights`
- Assert all leaf weights sum to `1.0` on every trading day
- Collect daily weight vectors into a `pd.DataFrame` with `DATE` (ISO 8601 strings) as the first column, uppercase tickers in DSL leaf order, `XCASHX` last if present
- Write the DataFrame to `output/allocations.csv`, creating the `output/` directory if absent
- Change `Runner.run()` return type from `None` to `pd.DataFrame`
- Export `Runner` from `engine/__init__.py` (already exported — verify unchanged)

## Capabilities

### New Capabilities
- `global-weight-vector`: Flatten local node weights into per-leaf global weights after each Downward Pass, with sum-to-one assertion
- `output-assembly`: Collect daily global weight vectors into a DataFrame and write to `output/allocations.csv`

### Modified Capabilities
_(none — no existing spec-level requirements change)_

## Impact

- **Code:** `moa_allocations/engine/runner.py` — add flattening logic and DataFrame assembly inside `run()`; change return type to `pd.DataFrame`
- **Code:** `moa_allocations/engine/__init__.py` — confirm `Runner` export (already present)
- **File system:** Creates `output/` directory and writes `allocations.csv` on every successful run
- **Dependencies:** No new external dependencies (uses existing `pandas`, `numpy`)
- **API:** `Runner.run()` return type changes from `None` → `pd.DataFrame` (**BREAKING** for any caller expecting `None`, though no callers exist yet outside tests)
