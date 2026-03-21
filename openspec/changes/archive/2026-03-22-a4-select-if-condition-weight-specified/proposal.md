## Why

The engine currently supports ranking-based selection (`SelectTopN`, `SelectBottomN`) and equal/inverse-volatility weighting, but lacks the conditional branching algo (`SelectIfCondition`) and the user-defined fixed-weight algo (`WeightSpecified`). These are required to support `if_else` nodes and `weight` nodes with `method: "defined"` — two of the six DSL node-type/method combinations specified in algos.spec.md. Without them, strategies using conditional logic or custom weight splits cannot run.

## What Changes

- **Add `SelectIfCondition`** to `moa_allocations/engine/algos/selection.py` — evaluates one or more metric conditions over a trailing duration window, combines with `all`/`any` logic, and writes the winning branch id to `target.temp['selected']`. Always returns `True`.
- **Add `WeightSpecified`** to `moa_allocations/engine/algos/weighting.py` — assigns pre-validated custom weights from a `{node_id: float}` dict directly to `target.temp['weights']`. Always returns `True`.
- **Unit tests** for both algos covering normal path, duration edge cases, NaN handling, and multi-condition `all`/`any` combinations.

## Capabilities

### New Capabilities

- `select-if-condition`: Conditional selection algo that evaluates metric comparisons over a duration window and routes to true/false branch.
- `weight-specified`: Fixed-weight assignment algo that applies compiler-validated custom weights to selected children.

### Modified Capabilities

_(none — these are new algos; no existing spec requirements change)_

## Impact

- **Code**: Extends `selection.py` and `weighting.py` with new algo classes; adds corresponding test files.
- **Dependencies**: Uses existing `compute_metric()` (A1) and `BaseAlgo` (C1). Depends on `target.perm['child_series']` and `target.temp['t_idx']` conventions established by A2/A3.
- **Out of scope**: AlgoStack construction and `Runner` attachment (E1); compiler condition parsing (already handled).
