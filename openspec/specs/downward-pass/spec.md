# Downward Pass

## Purpose

The Downward Pass executes each `StrategyNode`'s AlgoStack in top-down order (root first, deepest last) on rebalance days. It produces `node.temp['weights']` for every strategy node, normalises them to sum to 1.0, and falls back to `{'XCASHX': 1.0}` when a stack halts or weights sum to zero.

## Requirements

### Requirement: Temp reset on every simulation day

At the start of each simulation day (before the Upward Pass), `Runner` SHALL reset `node.temp` to `{"t_idx": t_idx}` for every `StrategyNode` in the tree. This applies on all days, not only rebalance days.

#### Scenario: Temp is clean before first pass
- **WHEN** the simulation loop begins day `t_idx = 5`
- **THEN** every `StrategyNode` SHALL have `node.temp == {"t_idx": 5}` before the Upward Pass executes

#### Scenario: Prior day's weights are cleared
- **WHEN** a node had `temp['weights'] = {"A": 0.6, "B": 0.4}` from the previous day's Downward Pass
- **THEN** after temp reset, `temp` SHALL contain only `{"t_idx": t_idx}` — the prior weights SHALL NOT be present

#### Scenario: t_idx is available for algos
- **WHEN** an Algo reads `target.temp["t_idx"]` during the Downward Pass
- **THEN** the value SHALL equal the current simulation day index

---

### Requirement: Downward Pass executes AlgoStack top-down on rebalance days

`Runner._downward_pass(t_idx)` SHALL iterate all `StrategyNode` instances in top-down order (root first, deepest last) and execute each node's `algo_stack`. Top-down order SHALL be the reverse of `_upward_order`. The Downward Pass SHALL only execute on rebalance days (including day 0).

#### Scenario: Root node executes before children
- **WHEN** the tree has root `W1` with child `W2` (sub-strategy)
- **THEN** `W1`'s AlgoStack SHALL execute before `W2`'s AlgoStack

#### Scenario: Three-level tree traversal order
- **WHEN** the tree has root `W1` → child `W2` → child `FilterNode` F1
- **THEN** execution order SHALL be `W1`, `W2`, `F1`

#### Scenario: Day 0 always runs downward pass
- **WHEN** `t_idx == 0` regardless of `rebalance_frequency`
- **THEN** `_downward_pass(0)` SHALL execute to establish initial weights

#### Scenario: Non-rebalance day skips downward pass
- **WHEN** `rebalance_frequency` is `monthly` and the current day is not the first trading day of a new month
- **THEN** `_downward_pass` SHALL NOT be called and prior weights SHALL carry forward

---

### Requirement: AlgoStack execution per node

For each `StrategyNode`, `_downward_pass` SHALL execute algos sequentially from `node.algo_stack`:

```
for algo in node.algo_stack:
    result = algo(node)
    if not result:
        node.temp['weights'] = {'XCASHX': 1.0}
        break
```

Each Algo receives the node as `target` and returns `bool`. If any Algo returns `False`, the remaining Algos in the stack SHALL NOT execute.

#### Scenario: Successful two-algo stack (SelectAll + WeightEqually)
- **WHEN** a `WeightNode` (method=equal) with children A, B, C executes its AlgoStack
- **THEN** `SelectAll` SHALL set `temp['selected'] = [A.id, B.id, C.id]` returning `True`, then `WeightEqually` SHALL set `temp['weights'] = {A.id: 0.333..., B.id: 0.333..., C.id: 0.333...}` returning `True`

#### Scenario: SelectTopN with all-NaN metrics
- **WHEN** a `FilterNode`'s `SelectTopN` algo finds all children have NaN metric values
- **THEN** `SelectTopN` SHALL return `False`, `WeightEqually` SHALL NOT execute, and `temp['weights']` SHALL be `{'XCASHX': 1.0}`

#### Scenario: IfElseNode routes to one branch
- **WHEN** an `IfElseNode`'s `SelectIfCondition` evaluates the condition as true
- **THEN** `temp['selected']` SHALL contain only `[true_branch.id]`, and `WeightEqually` SHALL set `temp['weights'] = {true_branch.id: 1.0}`

---

### Requirement: XCASHX fallback on halted stack

If any Algo in the stack returns `False`, the node's `temp['weights']` SHALL be set to `{'XCASHX': 1.0}` and no further Algos in that node's stack SHALL execute. XCASHX is a virtual leaf with return `0.0` — no price series is required.

#### Scenario: First algo halts
- **WHEN** the selection Algo (first in stack) returns `False`
- **THEN** `temp['weights']` SHALL be `{'XCASHX': 1.0}` and the weighting Algo SHALL NOT execute

#### Scenario: XCASHX propagates through weight flattening
- **WHEN** a node has `temp['weights'] = {'XCASHX': 1.0}` and `_flatten_weights` traverses it
- **THEN** the XCASHX weight SHALL accumulate in the global weight vector, contributing to the `XCASHX` column in the output DataFrame

---

### Requirement: Weight normalisation after successful stack

After a node's full AlgoStack completes without any Algo returning `False`, `_downward_pass` SHALL normalise `node.temp['weights']` so that values sum to `1.0`. If the sum of weights is `0.0`, the node SHALL fall back to `{'XCASHX': 1.0}`.

#### Scenario: Already-normalised weights pass through
- **WHEN** `WeightEqually` produces `{A: 0.5, B: 0.5}` (sum = 1.0)
- **THEN** after normalisation, weights SHALL remain `{A: 0.5, B: 0.5}`

#### Scenario: Weights not summing to 1.0 are corrected
- **WHEN** a weighting Algo produces `{A: 0.3, B: 0.6}` (sum = 0.9)
- **THEN** after normalisation, weights SHALL be `{A: 0.333..., B: 0.666...}` (each divided by 0.9)

#### Scenario: Zero-sum weights fall back to XCASHX
- **WHEN** a weighting Algo produces `{A: 0.0, B: 0.0}` (sum = 0.0)
- **THEN** `temp['weights']` SHALL be set to `{'XCASHX': 1.0}`

---

### Requirement: Upward Pass reads prior-day weights after temp reset

The Upward Pass computes NAV using `node.temp['weights']` from the previous day. Because temp is reset at the start of each day, the Downward Pass on the prior rebalance day must have populated `temp['weights']`. On non-rebalance days (when the Downward Pass does not run), `Runner.run()` SHALL preserve the prior day's weights by re-setting `node.temp['weights']` to the carried-forward values after the temp reset but before the Upward Pass.

#### Scenario: Weights carry forward on non-rebalance day
- **WHEN** day 5 is a rebalance day setting `temp['weights'] = {A: 0.6, B: 0.4}`, and day 6 is not a rebalance day
- **THEN** on day 6, after temp reset, `temp['weights']` SHALL be restored to `{A: 0.6, B: 0.4}` before the Upward Pass executes

#### Scenario: Day 0 establishes initial weights
- **WHEN** `t_idx == 0` (always a rebalance day)
- **THEN** the Downward Pass SHALL populate `temp['weights']` for all nodes, and the Upward Pass on day 1 SHALL use those weights
