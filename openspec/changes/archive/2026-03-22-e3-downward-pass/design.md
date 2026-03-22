## Context

The engine's daily simulation loop has two passes per trading day: Upward (leaves → root, NAV update) and Downward (root → leaves, AlgoStack execution). E1 and E2 landed the init and upward pass. The downward pass placeholder at `runner.py:313` currently skips AlgoStack execution and calls `_flatten_weights()` directly, which produces empty or stale results because `node.temp['weights']` is never populated.

Key existing infrastructure this design builds on:
- `Runner._upward_order` — `list[StrategyNode]` sorted deepest-first (bottom-up). Reversing it gives the top-down traversal order needed for the downward pass.
- `node.algo_stack` — already built by `_build_algo_stack()` in `__init__` and attached to each `StrategyNode`.
- `node.temp` / `node.perm` — mutable per-day and persistent state dicts on every `StrategyNode`.
- Algo contract: `algo(target: StrategyNode) -> bool`. Algos read `target.temp["t_idx"]` and `target.perm["child_series"]`; they write `target.temp["selected"]` and `target.temp["weights"]`.

## Goals / Non-Goals

**Goals:**
- Implement `Runner._downward_pass(t_idx)` that executes each node's AlgoStack in root-to-leaf order.
- Reset `node.temp` at the start of each simulation day, seeding it with `{"t_idx": t_idx}` so algos can locate themselves in the price/NAV arrays.
- Apply the XCASHX fallback: if any algo returns `False`, set `node.temp['weights'] = {'XCASHX': 1.0}` and stop that node's stack.
- Normalise `node.temp['weights']` to sum to `1.0` after a successful stack execution.
- Replace the E3 placeholder in `run()` with `self._downward_pass(t_idx)`.

**Non-Goals:**
- Weight flattening and output assembly (E4 — already implemented in `_flatten_weights` and `run()`).
- Changes to any Algo `__call__` implementations.
- Changes to the upward pass or NAV computation.
- Rebalance frequency logic (already correct in `run()`).

## Decisions

### D1: Traversal order — reverse `_upward_order`

The downward pass iterates `reversed(self._upward_order)`, which gives root-first, leaves-last. No separate `_downward_order` list is needed — a reversed view is sufficient and avoids duplicating state.

**Alternative considered:** Pre-compute a `_downward_order` list in `__init__`. Rejected — one more list to keep in sync with `_upward_order` for zero performance benefit.

### D2: Temp reset scope — every simulation day, before both passes

`node.temp` is reset to `{"t_idx": t_idx}` for every `StrategyNode` at the top of the day loop (before the upward pass), not just on rebalance days. This ensures:
- The upward pass sees a clean temp (it currently doesn't read temp, but this is defensive).
- The downward pass (only on rebalance days) always starts with a clean slate.
- `t_idx` is available in temp for algos that need it (`SelectIfCondition`, `SelectTopN/BottomN`, `WeightInvVol`).

**Alternative considered:** Reset only on rebalance days. Rejected — the engine spec says "reset at the start of each day's Downward Pass", and resetting on every day is both simpler and safer.

### D3: XCASHX fallback — on `False` return, not empty selection

The algo contract returns `bool`. The XCASHX fallback triggers when any algo in the stack returns `False`:

```
for algo in node.algo_stack:
    if not algo(target):
        node.temp['weights'] = {'XCASHX': 1.0}
        break
```

An empty `selected` list after a selection algo is the mechanism that causes the subsequent weighting algo to not produce weights — but the selection algo itself returns `False` in that case (see `_rank_and_select` returning `False` when `scored` is empty). So the `False` return is the single trigger point.

### D4: Normalisation — always applied after successful stack completion

After the full algo stack completes without a `False`, normalise weights:

```python
total = sum(node.temp['weights'].values())
if total > 0:
    node.temp['weights'] = {k: v / total for k, v in node.temp['weights'].items()}
```

Current weighting algos already produce normalised weights (e.g., `WeightEqually` divides by count, `WeightInvVol` normalises internally). The normalisation step is a safety net per the engine spec — it costs nothing and prevents subtle bugs if a future algo doesn't self-normalise.

The `total > 0` guard handles the degenerate case where weights are all zero (which shouldn't happen with current algos but is defensive). If `total == 0`, fall back to XCASHX.

### D5: Method placement — private `_downward_pass` on `Runner`

Consistent with `_upward_pass` — both are private methods on `Runner`, called from `run()`. No new classes or abstractions.

## Risks / Trade-offs

**[Risk] Algo raises an exception mid-stack** → Not mitigated here. Algos are trusted internal code; exceptions propagate to the caller. This is consistent with the upward pass behaviour. If robustness is needed later, it belongs in a separate error-handling change.

**[Trade-off] Normalisation on already-normalised weights** → Negligible cost (dict iteration) for correctness guarantee. Acceptable.

**[Trade-off] Resetting temp on non-rebalance days when downward pass won't run** → The reset is O(S) where S is strategy node count. Negligible compared to the upward pass computation. Keeps the code simpler than conditional reset.
