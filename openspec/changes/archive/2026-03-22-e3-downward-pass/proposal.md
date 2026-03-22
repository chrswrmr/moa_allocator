## Why

The Downward Pass is the second half of the daily simulation loop. Without it, no AlgoStack ever executes — `node.temp['weights']` is never populated, so `_flatten_weights()` returns empty or stale data. The Upward Pass (E2) and Runner init (E1) are complete; E3 is the next dependency before the engine can produce correct allocations. The placeholder comment at `runner.py:313` marks the gap.

## What Changes

- Add `Runner._downward_pass(t_idx)` method that iterates strategy nodes root → leaves, executing each node's AlgoStack and applying the XCASHX fallback.
- Reset `node.temp` for every `StrategyNode` at the start of each simulation day (before either pass).
- Normalise `node.temp['weights']` to sum to `1.0` after each node's AlgoStack completes.
- Replace the `# Downward Pass placeholder — E3` block in `Runner.run()` with a call to `_downward_pass(t_idx)`.

## Capabilities

### New Capabilities
- `downward-pass`: Top-down AlgoStack execution per rebalance day — temp reset, algo dispatch, XCASHX fallback on `False` / empty selection, weight normalisation.

### Modified Capabilities

(none — the global-weight-vector, upward-pass, and runner-init specs are unaffected; this change fills the placeholder they already assume)

## Impact

- **Files:** `moa_allocations/engine/runner.py` (extend `Runner` with `_downward_pass`, modify `run()` loop)
- **Tests:** New unit tests for downward-pass behaviour (XCASHX fallback, normalisation, top-down ordering, temp reset)
- **Dependencies:** Relies on E1 (`_build_algo_stack`, `_upward_order`) and E2 (`_upward_pass`). No new external packages.
- **Downstream:** Unblocks E4 (weight flattening + output assembly) — `_flatten_weights()` will now receive correctly populated `node.temp['weights']`.
