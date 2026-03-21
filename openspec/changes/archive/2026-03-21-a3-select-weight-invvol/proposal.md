## Why

The engine can currently only select all children (`SelectAll`) and weight them equally or by defined weights. Filter nodes (`top`/`bottom`) and inverse-volatility weighting are defined in the DSL schema but have no runtime implementation. Without `SelectTopN`, `SelectBottomN`, and `WeightInvVol`, strategies that use `filter` nodes or `weight/inverse_volatility` nodes will fail at execution time.

## What Changes

- Add `SelectTopN(n, metric, lookback)` to `selection.py` — ranks children descending by `compute_metric()` over their NAV/price series, selects top N, writes to `target.temp['selected']`
- Add `SelectBottomN(n, metric, lookback)` to `selection.py` — identical to `SelectTopN` but ranks ascending
- Add `WeightInvVol(lookback)` to `weighting.py` — computes `std_dev_return` per selected child, weights inversely proportional to volatility, normalises to sum 1.0; excludes zero/NaN-vol children; returns `False` if all excluded
- Unit tests for all three algos

## Capabilities

### New Capabilities

- `select-topn-bottomn`: SelectTopN and SelectBottomN selection algos — rank children by a metric and select the top or bottom N
- `weight-invvol`: WeightInvVol weighting algo — inverse-volatility weighting with zero/NaN-vol exclusion

### Modified Capabilities

_(none — existing specs are unchanged; these algos extend the module without modifying existing behaviour)_

## Impact

- **Files modified:** `moa_allocations/engine/algos/selection.py`, `moa_allocations/engine/algos/weighting.py`
- **New dependency within module:** both selection algos and `WeightInvVol` call `compute_metric()` from `metrics.py` (already implemented in A1)
- **Downstream:** once landed, the `Runner` can build AlgoStacks for `filter` and `weight/inverse_volatility` node types (Runner wiring is out of scope for this change)
