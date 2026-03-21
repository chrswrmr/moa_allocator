## Context

The engine has four selection algos (`SelectAll`, `SelectTopN`, `SelectBottomN`) and two weighting algos (`WeightEqually`, `WeightInvVol`). Two algo classes remain unimplemented: `SelectIfCondition` for `if_else` nodes and `WeightSpecified` for `weight` nodes with `method: "defined"`. Both are specified in algos.spec.md and required before AlgoStack construction (E1) can wire them into the engine.

Conditions are plain dicts produced by the compiler's `_build_condition()`, with `lhs`/`rhs` metric dicts (or scalar rhs), `comparator`, and `duration` (integer trading days). The `if_else` node stores these in `node.conditions` alongside `node.logic_mode`, `node.true_branch`, and `node.false_branch`.

## Goals / Non-Goals

**Goals:**
- Implement `SelectIfCondition` with full duration-window semantics (every day in the trailing window must satisfy the comparison)
- Implement `WeightSpecified` for direct custom-weight assignment
- Unit tests for both algos

**Non-Goals:**
- AlgoStack construction / attachment to nodes (E1)
- Compiler changes — condition parsing and lookback conversion already exist (C4)
- DSL schema changes

## Decisions

### D1: Condition evaluation as a private helper

Extract a `_evaluate_condition_at_day(target, condition, day_idx)` function in `selection.py` to evaluate a single condition at a single day index. `SelectIfCondition.__call__` loops over the duration window and calls this helper.

**Why over inline:** The spec's pseudocode already suggests this factoring. It keeps the `__call__` method focused on the duration-window + logic-mode combination, while the helper handles lhs/rhs metric computation and comparator dispatch. It also makes unit testing individual condition evaluation straightforward.

**Alternative considered:** A `Condition` class with an `evaluate(day_idx)` method — rejected because conditions are plain dicts from the compiler, and wrapping them adds a new abstraction layer with no clear benefit. The helper function is simpler.

### D2: Series source for lhs vs rhs

- **lhs** always evaluates against `target.perm['child_series']` keyed by `condition['lhs']['asset']`. This is the same series store used by `SelectTopN`/`SelectBottomN`.
- **rhs**, when it's a metric dict (not a scalar), also reads from `target.perm['child_series']` keyed by `condition['rhs']['asset']`.

**Why:** The engine populates `child_series` with NAV/price arrays for all nodes relevant to the current node's scope. Using a single series source keeps the algo consistent with the existing selection algos.

### D3: WeightSpecified stores weights at init time

`WeightSpecified.__init__(custom_weights)` stores the `{node_id: float}` dict. `__call__` writes it directly to `target.temp['weights']`. No runtime validation — the compiler guarantees weights sum to 1.0.

**Why over re-validating at runtime:** The Algo contract says algos receive pre-validated parameters. Adding runtime checks would violate the principle that validation belongs in the compiler, not in algos.

### D4: Duration window clamping

When `day_idx < duration - 1` (early days of the backtest), the window start is clamped to 0. The condition is evaluated over whatever days are available rather than failing outright.

**Why:** Per algos.spec.md — "do not fail the condition solely because the window is shorter than duration." This matches the intent that duration is a minimum-confidence window, not a hard prerequisite.

## Risks / Trade-offs

- **Performance on large duration windows:** Each condition is evaluated at every day in `[t - duration + 1, t]`, and each evaluation calls `compute_metric()` which slices a numpy array. For `duration = 200d` with 9 metrics, this is 200 metric computations per condition per rebalance day. → Acceptable for backtesting workloads; optimize later if profiling shows a bottleneck.
- **NaN propagation:** A NaN on any single day in the duration window fails the entire condition, routing to `false_branch`. This is conservative but spec-compliant. → No mitigation needed; this is intentional.
- **WeightSpecified ignores `target.temp['selected']`:** It writes `custom_weights` directly without filtering by the selected set. This is correct because `SelectAll` always selects all children for `weight` nodes, and the compiler validates that `custom_weights` keys match child ids. → If a future algo filters children before `WeightSpecified`, this assumption breaks. Not a concern for v1 where the AlgoStack is always `[SelectAll(), WeightSpecified(…)]`.
