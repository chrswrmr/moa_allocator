## Context

The price data passed to `Runner` includes pre-simulation lookback history before the simulation start date. `_price_offset` is the index of `start_date` in the full price array — everything before it is lookback buffer.

The upward pass and `_resolve_child_nav` both access asset prices as `price_arr[_price_offset + t_idx]`, correctly anchoring to the simulation start. However, `_evaluate_condition_at_day` slices condition series as `price_arr[:t_idx + 1]`, which anchors to index 0 (the start of the lookback buffer), not the simulation start. The result: at simulation day `t_idx`, conditions evaluate against prices from `_price_offset` trading days in the past.

`_build_algo_stack` is a module-level function called during the BFS in `Runner.__init__`, after `self._price_offset` is already computed. `SelectIfCondition` is constructed there and has no subsequent access to runner state.

## Goals / Non-Goals

**Goals:**
- Fix `_evaluate_condition_at_day` to slice `price_arr[:price_offset + day_idx + 1]`, ensuring both `lhs` and `rhs` metrics are evaluated on prices at the actual simulation date.
- Thread `price_offset` from `Runner.__init__` into `SelectIfCondition` via `_build_algo_stack`.

**Non-Goals:**
- No changes to `compute_metric`, node classes, compiler, DSL schema, or any other algo.
- No change to how `child_series` is stored — the full array (including lookback) is still needed so that lookback metrics (e.g. `sma_price`) have history at early simulation days.
- No change to upward pass or NAV tracking — those are already correct.

## Decisions

### Decision 1: Pass `price_offset` into `SelectIfCondition` at construction, not via `node.perm`

**Choice:** Add a `price_offset: int` parameter to `_build_algo_stack(node, price_offset)` and store it as `self._price_offset` on `SelectIfCondition`. Pass it through to `_evaluate_condition_at_day`.

**Why:** The algo needs `price_offset` only for series slicing — a pure computation concern. Passing it as a constructor argument keeps `SelectIfCondition` self-contained and unit-testable without a runner instance. Using `node.perm` as a side-channel would couple the algo to runner internals and make the dependency invisible.

**Alternative considered:** Store `price_offset` in `node.perm["price_offset"]` during BFS and read it in `_evaluate_condition_at_day` via `target.perm`. Rejected — `perm` is for state that persists across days (NAV arrays, child series), not for static configuration. Using it this way obscures the data flow.

### Decision 2: Fix the slice endpoint, not the start

**Choice:** Change `price_arr[:day_idx + 1]` to `price_arr[:price_offset + day_idx + 1]`. The slice still starts at index 0.

**Why:** The lookback history (indices `0` to `price_offset - 1`) is needed for metrics like `sma_price` at early simulation days. Slicing away that history would cause NaN returns at the start of the simulation. Fixing only the endpoint is the minimal, correct change.

## Risks / Trade-offs

- **Existing tests** that mock condition evaluation with `_price_offset = 0` will continue to pass unmodified — the fix is a no-op when offset is zero. Tests that exercise the full runner with non-zero lookback may need fixture adjustment to assert the now-correct (previously stale) condition values.
- **Decision outcomes may change** for live strategies with lookback > 0. The corrected condition evaluates against the actual current price, not a lagged one — this is the intended behaviour, but backtests will differ from prior runs.
