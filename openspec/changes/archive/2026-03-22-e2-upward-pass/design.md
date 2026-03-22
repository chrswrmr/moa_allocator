## Context

E1 (`Runner.__init__`) already traverses the compiled tree, attaches AlgoStacks, validates price data, and pre-converts price columns to numpy arrays stored in `node.perm['child_series']`. For StrategyNode children, `child_series[child.id]` is currently an empty placeholder array — the upward pass must fill these with live NAV values so that parent Algos can compute metrics over sub-strategy returns during the Downward Pass.

The engine spec (engine.spec.md) defines the two-pass model: Upward Pass (leaves → root, NAV update) then Downward Pass (root → leaves, AlgoStack execution). This change implements the Upward Pass, the simulation loop skeleton, and rebalance-schedule gating. The Downward Pass itself is E3.

## Goals / Non-Goals

**Goals:**
- `Runner.run()` iterates over `[start_date, end_date]` trading days
- Upward Pass updates `node.perm['nav']` bottom-up every day
- `child_series` for StrategyNode children are kept current so Algos see live NAV
- Rebalance schedule (daily/weekly/monthly) gates Downward Pass execution
- Non-rebalance days carry prior target weights forward

**Non-Goals:**
- Downward Pass execution (E3)
- Global weight vector flattening and output assembly (E4)
- Threshold drift check (ADR-005 — deferred to moa_rebalancer)

## Decisions

### D1 — Pre-allocated numpy arrays for NAV, daily view slices for child_series

**Problem:** Algos read `target.perm['child_series'][child_id]` and pass the array to `compute_metric()`, which operates on `series[-lookback:]`. For AssetNode children this works — the full price array is set once at init. For StrategyNode children, the NAV grows daily. The array must appear to "grow" without breaking the Algo interface.

**Decision:** Pre-allocate `perm['nav_array'] = np.ones(T, dtype=np.float64)` for each StrategyNode at init time, where `T = len(sim_dates)`. After computing NAV for day `t_idx`, update the parent's child_series entry to a view: `child_series[child.id] = child.perm['nav_array'][:t_idx + 1]`. Numpy views are O(1), no copy.

**Why not growing lists / append:** Converting list → numpy each day is O(T) per node per day = O(S×T²) total. For T=5000, S=50, that's 1.25B element copies. Pre-allocated arrays with views are O(1) per update.

**Why not store t_idx on target and have Algos slice:** Changes the Algo interface. Algos are already implemented (A1–A4) and expect a plain numpy array.

### D2 — Bottom-up traversal order via reverse-level BFS

**Problem:** The upward pass must process children before parents. The tree contains WeightNode, FilterNode, IfElseNode (branching), and AssetNode (leaf). Need a deterministic bottom-up order.

**Decision:** Single BFS at init time to collect `(depth, node)` pairs. Sort by depth descending. Store as `self._upward_order: list[StrategyNode]` (excludes AssetNodes — they have no NAV to compute, their returns come directly from price arrays). Reused every day.

**Why not recursive DFS:** BFS with reverse-depth gives the same correctness guarantee (children before parents) and avoids recursion depth issues on deeply nested trees. Also consistent with the existing BFS pattern in `_collect_tickers` and `_compute_max_lookback`.

### D3 — Day 0 bootstrapping

On `start_date` (t_idx=0):
- All NAV values are 1.0 (pre-filled by the np.ones allocation)
- No prior weights exist, so `weighted_return` is undefined
- The Downward Pass **must** run on day 0 to establish initial weights — it is always a rebalance day regardless of schedule

On day 1+ (t_idx > 0):
- Upward Pass computes `weighted_return` from `temp['weights']` (set by prior day's Downward Pass or carried forward) × today's child returns
- `nav_array[t_idx] = nav_array[t_idx - 1] * (1 + weighted_return)`

Child returns:
- AssetNode: `price[lookback_offset + t_idx] / price[lookback_offset + t_idx - 1] - 1` (offset because price arrays include lookback period before start_date)
- StrategyNode: `nav_array[t_idx] / nav_array[t_idx - 1] - 1` (child already processed — bottom-up order guarantees this)

### D4 — if_else dual-branch NAV update

Per engine.spec.md: both branches update NAV every day; the if_else node's own NAV uses only the active branch return.

**"Active branch"** = whichever branch was selected on the prior day (stored in `temp['weights']` by `SelectIfCondition` during the Downward Pass). On day 0, no prior selection exists — NAV stays at 1.0 (same as D3).

Implementation: after processing both branches bottom-up, the if_else node reads `temp['weights']` to determine which branch id had weight > 0 yesterday, then uses that branch's return for its own NAV update.

### D5 — Rebalance schedule as pure calendar gate

`_is_rebalance_day(current_date, prev_date, frequency) -> bool`:
- `daily`: always `True`
- `weekly`: `current_date.isocalendar().week != prev_date.isocalendar().week`
- `monthly`: `current_date.month != prev_date.month`

Where `prev_date` is the previous trading day (sim_dates[t_idx - 1]). Day 0 is always a rebalance day (D3).

No threshold logic — ADR-005.

### D6 — sim_dates and price index offset

Compute at init time:
- `self._sim_dates`: `price_data.index` filtered to `[start_date, end_date]` — the dates the loop iterates over
- `self._price_offset`: index position of `start_date` in `price_data.index` — used to translate `t_idx` to the correct position in full price arrays (which include lookback period)

For AssetNode return on day t_idx: `price_array[price_offset + t_idx] / price_array[price_offset + t_idx - 1] - 1`.

### D7 — Weight carry-forward on non-rebalance days

On non-rebalance days, `temp['weights']` is not cleared — it retains the values from the last rebalance day. The Upward Pass reads these carried-forward weights for the weighted_return calculation. The Downward Pass is skipped entirely.

This means `temp` is **not** reset on non-rebalance days. The reset-per-day behavior described in engine.spec.md ("reset at the start of each day's Downward Pass") only applies when the Downward Pass actually runs.

## Risks / Trade-offs

**[Risk] NAV accuracy on day 0** → On day 0, NAV is 1.0 for all nodes and no return is computed. If an Algo queries a sub-strategy's NAV series on day 0, it sees only `[1.0]`. Metrics requiring lookback > 1 will return NaN. This is correct per spec ("Lookback window extends before price_data start → Metric returns NaN; asset treated as excluded") and consistent with how asset price series behave during lookback ramp-up.

**[Risk] price_offset arithmetic off-by-one** → The price arrays from E1 include the lookback period. An off-by-one in `price_offset` would silently shift all returns by one day. Mitigation: unit test that verifies `price_data.index[price_offset] == start_date` as an assertion in init.

**[Trade-off] temp not reset on non-rebalance days** → Slightly deviates from the spec's "reset each day" language, but the spec qualifies this as "at the start of each day's Downward Pass". Since no Downward Pass runs on non-rebalance days, carrying forward is the correct interpretation. E3 must reset temp only when it actually runs the Downward Pass.
