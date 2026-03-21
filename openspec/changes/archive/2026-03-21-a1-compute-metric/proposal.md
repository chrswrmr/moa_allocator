## Why

Selection algos (`IfCondition`, `TopN`, `BottomN`) and the inverse-volatility weighting algo all need to evaluate time-series metrics against price data. Without `compute_metric()` and the 9 metric functions, no conditional or ranking logic can operate — this is the foundation that A2–A4 depend on.

## What Changes

- New file `moa_allocations/engine/algos/metrics.py` containing:
  - `compute_metric(series, function, lookback)` — dispatcher that routes a DSL metric name to the correct function
  - 9 pure metric functions: `current_price`, `cumulative_return`, `sma_price`, `ema_price`, `sma_return`, `max_drawdown`, `rsi` (Wilder smoothing), `std_dev_price`, `std_dev_return`
- Update `moa_allocations/engine/algos/__init__.py` to export `compute_metric`
- All functions are pure (no side effects, no state), return `float`, and return `np.nan` on insufficient data
- All metrics use today's close as reference per ADR-003

## Capabilities

### New Capabilities
- `compute-metric`: The `compute_metric()` dispatcher and all 9 metric functions — public interface, NaN rules, lookback semantics, and per-function computation logic

### Modified Capabilities
_(none — no existing specs are changing)_

## Impact

- **New code:** `moa_allocations/engine/algos/metrics.py` (new module), `moa_allocations/engine/algos/__init__.py` (re-export)
- **Dependencies:** `numpy` (already in project), `pandas` (needed for `ema_price` EWM)
- **Downstream:** Unblocks A2 (selection algos), A3 (weighting algos), A4 (algo integration) — they call `compute_metric` but that wiring is out of scope here
- **No breaking changes** — entirely additive
