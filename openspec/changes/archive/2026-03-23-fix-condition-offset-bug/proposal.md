## Why

Condition evaluation in `SelectIfCondition` slices the price series using `t_idx` alone, without applying `_price_offset`. As a result, conditions are evaluated against prices from `_price_offset` trading days *before* the actual simulation date — the same offset used to store pre-simulation lookback history. NAV tracking and the upward pass correctly apply `_price_offset + t_idx`; condition evaluation does not, producing a silent data misalignment that corrupts decision logic for any strategy with lookback > 0.

## What Changes

- Fix `_evaluate_condition_at_day` (or its caller) so that condition price series are sliced starting at `_price_offset`, not at 0, ensuring conditions see prices at the actual simulation date and within the correct lookback window.
- No changes to DSL schema, compiler, node classes, or upward/downward pass structure.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `select-if-condition`: The requirement on which date conditions must evaluate against changes — conditions must evaluate against prices at the actual simulation date (index `_price_offset + t_idx`), not from the start of the full price array (index `t_idx`).

## Impact

- `moa_allocations/engine/algos/selection.py` — `_evaluate_condition_at_day` slice logic
- `moa_allocations/engine/runner.py` — `_price_offset` must be accessible to condition evaluation (either passed in or read from node state)
