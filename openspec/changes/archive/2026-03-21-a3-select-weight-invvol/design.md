## Context

The engine currently supports `SelectAll`, `WeightEqually`, and `WeightSpecified`. Filter nodes (`top`/`bottom`) and `weight/inverse_volatility` nodes are defined in the DSL schema and compiled into `FilterNode` / `WeightNode` instances, but have no runtime algos to execute their AlgoStacks. This change adds the three missing algos: `SelectTopN`, `SelectBottomN`, and `WeightInvVol`.

All three algos depend on `compute_metric()` (landed in A1) and follow the `BaseAlgo` contract (landed in A2). The node classes (`FilterNode`, `WeightNode`, `AssetNode`) and their `perm`/`temp` state model are already in place.

## Goals / Non-Goals

**Goals:**
- Implement `SelectTopN` and `SelectBottomN` in `selection.py` — rank children by any DSL metric and select the top or bottom N
- Implement `WeightInvVol` in `weighting.py` — weight selected children inversely proportional to return volatility
- Full unit test coverage for all three algos

**Non-Goals:**
- Runner wiring (attaching AlgoStacks to filter/inverse_volatility nodes) — separate change
- `SelectIfCondition` — that is A4
- Modifying `compute_metric()` or existing algos
- Any DSL schema changes

## Decisions

### D1: Shared ranking helper for SelectTopN / SelectBottomN

**Decision:** Extract a private `_rank_and_select(target, n, metric, lookback, reverse)` function used by both classes. `SelectTopN` calls it with `reverse=True` (descending), `SelectBottomN` with `reverse=False` (ascending).

**Why over two separate implementations:** The logic is identical except sort direction. A shared helper eliminates duplication and ensures both algos handle edge cases (NaN exclusion, tie-breaking) identically.

**Alternative considered:** Single `SelectByRank` class with a `mode` parameter. Rejected because the spec defines two distinct classes matching the DSL's `top`/`bottom` modes, and separate classes keep the AlgoStack composition table readable.

### D2: Series access pattern for child metrics

**Decision:** All child series are accessed through a single unified key: `target.perm['child_series'][child.id]`, sliced to `[:t_idx+1]` for the current day. The engine populates this dict with price arrays for `AssetNode` children and NAV arrays for `StrategyNode` children. Algos do not distinguish between child types — they use `child.id` uniformly.

The algo receives the current day index via `target.temp['t_idx']` (set by the engine before each Downward Pass).

**Why:** A single `child_series` dict avoids `isinstance` checks inside algos and keeps the algo contract simple: every child is identified by `child.id`, regardless of whether it's a leaf asset or a sub-strategy. The engine is responsible for populating the correct underlying array (price vs NAV) at init time. Algos must not perform DataFrame operations — they receive pre-computed numpy arrays from `target.perm` and pass them to `compute_metric()`.

### D3: NaN metric handling in selection

**Decision:** If `compute_metric()` returns `np.nan` for a child, that child is excluded from ranking. If all children return NaN, the algo returns `True` with an empty `selected` list — the subsequent `WeightEqually` will then see zero selected children and the engine defaults to XCASHX.

**Why over returning False directly:** The spec says SelectTopN/BottomN return `False` only if zero children are selected. Separating "NaN exclusion" from "halt" keeps the control flow consistent: the selection algo selects, the weighting algo halts if there's nothing to weight.

**Correction:** Re-reading the spec — SelectTopN/BottomN should return `True` if at least 1 selected, `False` if none. So if all children have NaN metrics, the algo returns `False` directly (→ XCASHX). This is cleaner: no need to pass an empty list downstream.

### D4: WeightInvVol exclusion and redistribution

**Decision:** `WeightInvVol` computes `std_dev_return` over `lookback` days for each selected child. Children with zero or NaN volatility are excluded. Weights for remaining children are `1/vol[i]` normalised to sum to 1.0. If all children are excluded, return `False` (→ XCASHX).

**Why `std_dev_return` specifically:** The spec explicitly mandates `std_dev_return` as the volatility measure for inverse-volatility weighting. This is already implemented in `metrics.py`.

### D5: Tie-breaking in ranking

**Decision:** When children have identical metric values, use stable sort order (preserve the order children appear in the node's `children` list). Python's `sorted()` with `key=` is stable by default.

**Why:** Deterministic output is essential for reproducible backtests. Child order is set at compile time and is stable across runs.

## Risks / Trade-offs

**[Risk] Large N with many NaN children** → If most children have insufficient history for the metric, the effective pool shrinks. Mitigation: this is expected early-backtest behaviour; the algo handles it correctly by excluding NaN children and selecting from the remainder.

**[Risk] Zero-vol child in WeightInvVol** → A child with perfectly flat price produces `std_dev_return = 0.0`, causing `1/vol = inf`. Mitigation: the spec explicitly requires excluding zero-vol children, which handles this case.

**[Trade-off] No caching of metric values across algos** → If a future algo needs the same metric for the same child on the same day, it will recompute. Accepted: premature optimisation; the cost is negligible for the number of children in typical strategies (< 20).
