## Context

The compiler produces a `RootNode` containing a `Settings` dataclass and a recursive tree of `StrategyNode`/`AssetNode` instances. The algos are implemented and expect two runtime contracts:

- `target.perm["child_series"]` — a `dict[str, np.ndarray]` mapping each child id to a price or NAV series
- `target.temp["t_idx"]` — an integer day index set by the engine each trading day

No `Runner` class exists yet. This change creates `Runner.__init__()` which wires the compiled tree to the algos and validates price data — the last prerequisite before the simulation loop (E2–E4).

## Goals / Non-Goals

**Goals:**
- Traverse the compiled tree and attach the correct AlgoStack to each StrategyNode
- Pre-convert price columns to numpy arrays and store on `node.perm["child_series"]`
- Validate ticker coverage and date range; raise `PriceDataError` on violations
- Compute `max_lookback` across the entire tree to determine required price history depth
- Export `Runner` and `PriceDataError` from `moa_allocations.engine`

**Non-Goals:**
- Simulation loop (`run()` method) — E2
- Upward/downward pass logic — E3
- Output DataFrame construction — E4
- Any changes to compiler or algos

## Decisions

### D1: Tree traversal strategy — iterative BFS

Use `collections.deque` BFS to traverse all nodes. This avoids recursion depth limits on deeply nested trees and keeps the traversal logic flat and testable.

*Alternative: recursive DFS.* Simpler code but risks stack overflow on deep trees. BFS also naturally processes parents before children, which aligns with how the downward pass will later operate.

### D2: AlgoStack attachment — dispatch on node class

Use `isinstance` checks against the concrete node classes (`WeightNode`, `FilterNode`, `IfElseNode`) rather than a string-based `node.type` field. The node class hierarchy already encodes the type, so a second type tag would be redundant and fragile.

```python
if isinstance(node, WeightNode):
    if node.method == "equal":
        node.algo_stack = [SelectAll(), WeightEqually()]
    elif node.method == "defined":
        node.algo_stack = [SelectAll(), WeightSpecified(node.method_params["weights"])]
    elif node.method == "inverse_volatility":
        node.algo_stack = [SelectAll(), WeightInvVol(node.method_params["lookback"])]
elif isinstance(node, FilterNode):
    select_cls = SelectTopN if node.select["mode"] == "top" else SelectBottomN
    node.algo_stack = [
        select_cls(node.select["count"], node.sort_by["function"], node.sort_by["lookback"]),
        WeightEqually(),
    ]
elif isinstance(node, IfElseNode):
    node.algo_stack = [
        SelectIfCondition(node.conditions, node.logic_mode),
        WeightEqually(),
    ]
# AssetNode: no algo_stack (leaf)
```

*Alternative: registry/dict mapping.* More extensible but over-engineered for 6 fixed variants that map 1:1 to the DSL schema. YAGNI.

### D3: `child_series` population — numpy arrays from price_data columns

For each `StrategyNode`, build `node.perm["child_series"]` as `dict[str, np.ndarray]`:
- For `AssetNode` children: `price_data[ticker].to_numpy()` — the raw price series
- For `StrategyNode` children: initialized as empty; filled during the upward pass (E3) with the child's NAV series

At init time, only asset-leaf arrays are populated. NAV arrays for strategy sub-trees will be allocated and grown by the simulation loop. Runner init stores a reference so the upward pass knows where to write.

*Alternative: store full DataFrames.* Violates the algo contract (no DataFrame operations inside algos) and wastes memory on unused columns.

### D4: `max_lookback` computation — separate BFS helper

`_compute_max_lookback(root)` is a standalone BFS function that collects all lookback values from:
- `FilterNode.sort_by["lookback"]`
- `WeightNode.method_params["lookback"]` (for `inverse_volatility`)
- Each condition's `lhs.lookback` and `rhs.lookback` (for `IfElseNode`)

This runs as a separate BFS pass from the AlgoStack attachment loop (there are 3 passes total: `_collect_tickers`, `_compute_max_lookback`, then the main attach+child_series loop). The separation keeps each helper independently testable and readable at no meaningful runtime cost for typical tree sizes (depth < 10).

Take the maximum. This determines the required date range: `price_data.index` must start on or before `settings.start_date - max_lookback` trading days.

### D5: Price data validation — fail fast at init

Two validation checks, both raising `PriceDataError`:

1. **Ticker coverage:** Collect all unique tickers from `AssetNode` leaves (and from `if_else` condition RHS assets). Every ticker must exist in `price_data.columns`.
2. **Date range:** `price_data.index[0] <= start_date - max_lookback_days` and `price_data.index[-1] >= end_date` (comparing on the DatetimeIndex).

Validation runs after tree traversal (which collects tickers and max_lookback) but before numpy conversion (no point converting if validation fails).

### D6: `PriceDataError` — simple exception in `runner.py`

Define `PriceDataError(Exception)` in `runner.py` itself rather than a separate `exceptions.py`. There is currently only one custom exception in the engine. Extract to a module if more are added later.

### D7: `pidb_ib` integration — caller responsibility

`Runner` receives `price_data: pd.DataFrame` as a constructor argument. The caller is responsible for calling `pidb_ib.get_prices(tickers, start, end)` and passing the result. Runner does not import or call `pidb_ib` directly — this keeps the engine testable without a database dependency.

## Risks / Trade-offs

- **[Risk] IfElseNode condition assets not in child_series** → Conditions can reference tickers (via `lhs.asset`, `rhs.asset`) that are not direct children of the if_else node. These must be collected during traversal and included in ticker validation. Mitigation: the ticker collection step walks conditions explicitly.
- **[Risk] NAV arrays not available at init** → Strategy sub-tree children don't have price arrays at init. The `child_series` dict will have placeholder entries (empty arrays or None) that the upward pass fills. Mitigation: document this clearly; E3 implementation must populate before first downward pass read.
- **[Trade-off] BFS vs DFS** → BFS uses O(width) memory vs DFS O(depth). For typical strategy trees (depth < 10, width < 50), this is negligible. BFS chosen for natural top-down ordering.
