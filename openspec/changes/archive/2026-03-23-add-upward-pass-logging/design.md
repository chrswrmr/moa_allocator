## Context

The `_upward_pass()` method in `runner.py` already computes weighted returns for every node bottom-up and logs individual NAV values using the `NAV` keyword. However, the pass itself has no start/complete markers, and there is no per-node context showing which children contributed to a node's NAV. Users reading the log cannot trace data dependencies or understand how asset prices and sub-strategy NAVs flow into intermediate nodes.

The fix is purely additive: inject structured log calls into `_upward_pass()` without changing any computation.

## Goals / Non-Goals

**Goals:**
- Emit `UPWARD start` and `UPWARD complete` markers with date and t_idx (keyword=`UPWARD`)
- For each node processed, log a formatted block showing node identity, each child with NAV and weight, and the final node NAV
- Support three per-node-type formats: WeightNode, FilterNode, IfElseNode
- All detail logs at DEBUG level; UPWARD boundary logs also at DEBUG with keyword in extra dict
- Zero impact on allocation computations — pure observability addition

**Non-Goals:**
- Changes to Downward Pass logging
- Changes to ALLOC, REBALANCE, SELECT, WEIGHT keyword behaviour
- New log levels or logger configuration changes
- Logging for AssetNode (leaves have no children to log)

## Decisions

### D1: All new logging lives in `_upward_pass()` in `runner.py`

The proposal specifies `runner.py` as the only modified file. Helper functions for per-node-type formatting will be module-level functions in `runner.py` (prefixed `_log_upward_node_*`).

Alternatives considered:
- Adding logging inside each node class — rejected: nodes must not know about logging or their parent context (architecture boundary rule)
- Adding to algo `__call__` methods — rejected: algos run during Downward Pass, not Upward Pass

### D2: Child NAV values retrieved from `price_data` or `nav_array` at `t_idx`

For asset children: `price_arr[self._price_offset + t_idx]` — same array already used for return calculation.
For strategy node children: `self._strategy_nodes[child_id].perm["nav_array"][t_idx]` — the just-computed value.
This matches the spec requirement that logged NAV values are the actual inputs used.

### D3: Per-node-type formatting via three helper functions

One helper per concrete node type handles the complete `┌─ … └─` block:
- `_log_upward_weight(node, weights, t_idx, nav_val, runner)` — WeightNode
- `_log_upward_filter(node, weights, t_idx, nav_val, runner)` — FilterNode
- `_log_upward_ifelse(node, weights, t_idx, nav_val, runner)` — IfElseNode

The helpers receive `runner` (self) to access `_strategy_nodes`, `_asset_nodes`, `price_data`, and `_price_offset`. The type dispatch happens inside `_upward_pass()` after the NAV is computed.

Weight method label for WeightNode is read from `node.method` (values: `"equal"`, `"defined"`, `"inverse_volatility"`).
Filter direction+count label is read from `node.select["mode"]` + `node.select["count"]`.
IfElseNode condition expressions are read from `node.conditions` (each condition's `lhs`, `operator`, `rhs` fields as stored by the compiler).

### D4: `node.temp["selected"]` provides FilterNode selected/dropped distinction

After the Downward Pass runs `SelectTopN`/`SelectBottomN`, the selected child IDs are stored in `node.temp["selected"]`. At Upward Pass time, `node.temp["weights"]` contains only selected children; the full child list is in `node.children`. Children in `node.children` but not in `weights` are dropped.

This approach avoids storing additional state — the distinction is derivable from existing data.

### D5: IfElseNode branch detection from weights

The selected branch is the child_id present in `node.temp["weights"]`. The other branch (the non-selected one) is also logged but without `[SELECTED]`. Both `node.true_branch` and `node.false_branch` are always present.

### D6: Condition expression formatting

Conditions are stored as dicts with `lhs`, `operator`, `rhs`. A compact string representation:
- `lhs` with `asset` key → `"<asset> <lookback> <metric>"`
- `rhs` scalar → displayed as-is
- `rhs` dict → same pattern as lhs

Format: `<lhs_str> <operator> <rhs_str>` — keeps lines short and readable.

## Risks / Trade-offs

- **Lookback/metric field naming in conditions**: The lhs/rhs dicts use fields `asset`, `metric`, `lookback`. If the compiler stores them under different keys, the condition formatter will produce incomplete output. Mitigation: read `moa_Req_to_DSL.md` and verify field names before implementation.
- **FilterNode `temp["selected"]` availability**: `temp` is reset at the start of each day and repopulated by the Downward Pass. The Upward Pass runs before the current-day Downward Pass — so `temp["selected"]` holds the previous rebalance day's selection, which is the same selection used to compute `temp["weights"]` (carried via `_prev_weights`). This is correct: the log shows the weights actually being applied.
- **IfElseNode with XCASHX weight**: If a condition algo returns False and falls back to XCASHX, neither branch is in weights. The formatter should handle this gracefully (show both branches without [SELECTED], or skip the block).
- **No new test for UPWARD keyword**: Existing `test_keyword_anchors_in_log` checks specific keywords. A new test checking for `UPWARD` keyword in log output should be added as part of this change.

## Implementation Decisions

### D7: Only "UPWARD start" boundary log, no "UPWARD complete"

After implementation, "UPWARD complete" boundary logging was intentionally removed to reduce log noise. The "UPWARD start" marker is sufficient to demarcate the upward pass boundary; the detailed per-node logs that follow provide visibility into pass execution without the redundant completion marker.

## Open Questions

(none — design is fully determined)
