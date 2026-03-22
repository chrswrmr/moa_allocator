## Why

E1 wired the compiled Strategy Tree to AlgoStacks and pre-converted price columns to numpy arrays, but `Runner.run()` does not exist yet. Before the Downward Pass (E3) can allocate capital, every `StrategyNode` must expose a unitized NAV series so parent Algos can evaluate metrics (SMA, RSI, etc.) over sub-strategy returns. The Upward Pass computes these NAV series bottom-up each trading day. Additionally, rebalance-frequency gating determines whether the Downward Pass runs on a given day — this logic must be in place before E3 can honour `daily` / `weekly` / `monthly` schedules.

## What Changes

- Add `Runner.run()` method containing the day-by-day simulation loop skeleton (iterates `[start_date, end_date]`).
- Implement the **Upward Pass**: traverse leaves → root updating `node.perm['nav_array']` via `nav[t] = nav[t-1] × (1 + weighted_return[t])`, initialised to `1.0`.
- For `if_else` nodes: update both branches' NAV every day; use active-branch return only for the node's own NAV.
- For `AssetNode` leaves: derive daily return directly from `price_data`.
- Implement **rebalance schedule logic** as a calendar gate: `daily`, `weekly` (first trading day of calendar week), `monthly` (first trading day of calendar month). Threshold drift check is deferred to `moa_rebalancer` (ADR-005).
- On non-rebalance days: carry prior target weights forward, skip Downward Pass entirely.
- Store NAV series in `node.perm['nav_array']` as a pre-allocated `np.ndarray` with O(1) view slices.

## Capabilities

### New Capabilities
- `upward-pass`: Bottom-up NAV computation for every StrategyNode and AssetNode, including if_else dual-branch updates and weighted-return aggregation.
- `rebalance-schedule`: Calendar-based day-classification logic (is today a rebalance day?) that controls whether the Downward Pass executes. No threshold drift — that is `moa_rebalancer`'s responsibility (ADR-005).

### Modified Capabilities
- `runner-init`: Runner.__init__() must initialise NAV arrays (`perm['nav_array']`) to 1.0 for every StrategyNode and prepare the simulation date range. The existing spec needs a delta to cover these new init-time responsibilities.

## Impact

- **Code**: `moa_allocations/engine/runner.py` — extend `Runner` with `.run()`, upward-pass helpers, and rebalance-schedule helpers.
- **Node state**: `node.perm['nav_array']` and `node.temp['weights']` become live state during the simulation loop.
- **Dependencies**: No new external packages. Uses existing numpy arrays pre-computed in E1.
- **Downstream**: E3 (Downward Pass) and E4 (output DataFrame) depend on the loop skeleton and rebalance gating introduced here.
