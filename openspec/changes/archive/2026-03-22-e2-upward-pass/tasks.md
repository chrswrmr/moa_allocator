## 1. Runner.__init__ extensions (delta to E1)

- [x] 1.1 Compute `_sim_dates` by filtering `price_data.index` to `[start_date, end_date]` inclusive. Compute `_price_offset` as the integer index of `start_date` in `price_data.index`. Add assertion that `price_data.index[_price_offset] == start_date`.
- [x] 1.2 Pre-allocate `perm['nav_array'] = np.ones(len(_sim_dates), dtype=np.float64)` for every `StrategyNode` during the existing BFS traversal.
- [x] 1.3 Replace `StrategyNode` child placeholders in `child_series`: set `child_series[child.id] = child.perm['nav_array'][:1]` (initial NAV view) instead of empty arrays.
- [x] 1.4 Compute `_upward_order`: collect `(depth, node)` pairs during BFS, sort by depth descending, store as `list[StrategyNode]` excluding `AssetNode` leaves.

## 2. Rebalance schedule

- [x] 2.1 Implement `_is_rebalance_day(current_date, prev_date, frequency) -> bool` as a module-level function. `daily` → always True, `weekly` → ISO week differs, `monthly` → month differs.

## 3. Upward Pass

- [x] 3.1 Implement `_upward_pass(self, t_idx: int)` method on `Runner`. Iterate `_upward_order`. For each `WeightNode`/`FilterNode`: read `temp['weights']`, compute child returns (AssetNode via price arrays + `_price_offset`, StrategyNode via `nav_array`), compute `weighted_return`, update `nav_array[t_idx]`. Treat `XCASHX` return as `0.0`.
- [x] 3.2 Handle `IfElseNode` in `_upward_pass`: read `temp['weights']` to identify active branch, use active branch return only for the if_else node's own NAV update. Both branches' NAV arrays are already updated (deeper in tree, processed first).
- [x] 3.3 Implement `_update_child_series_views(self, t_idx: int)` method. For every parent with a `StrategyNode` child, set `child_series[child.id] = child.perm['nav_array'][:t_idx + 1]`.

## 4. Simulation loop skeleton

- [x] 4.1 Implement `Runner.run()`. Loop over `_sim_dates` by `t_idx`. Day 0: skip upward pass, mark as rebalance day (Downward Pass placeholder for E3). Day 1+: run `_upward_pass(t_idx)`, then `_update_child_series_views(t_idx)`, then check `_is_rebalance_day` to determine if Downward Pass should run (placeholder for E3). Return `None` for now (E4 adds the DataFrame return).

## 5. Tests

- [x] 5.1 Unit test `_is_rebalance_day`: daily always True; weekly triggers on ISO week boundary, not mid-week; monthly triggers on month boundary; year-boundary edge case (ISO week spanning Dec/Jan).
- [x] 5.2 Unit test `_sim_dates` and `_price_offset`: verify correct date filtering and offset with lookback period present.
- [x] 5.3 Unit test `_upward_order`: two-level tree, nested tree with sub-strategies, IfElseNode with nested branches — verify depth-descending order and AssetNode exclusion.
- [x] 5.4 Unit test NAV pre-allocation: verify `perm['nav_array']` shape and initial values; verify `child_series` for StrategyNode children points to `nav_array[:1]`.
- [x] 5.5 Unit test upward pass NAV computation: WeightNode with two AssetNode children — verify `nav_array[t_idx]` matches `nav[t-1] * (1 + weighted_return)` for known price data.
- [x] 5.6 Unit test upward pass with StrategyNode child: nested WeightNodes — verify child NAV is computed before parent uses it.
- [x] 5.7 Unit test upward pass IfElseNode: verify both branches update NAV; verify if_else node uses only active branch return.
- [x] 5.8 Unit test XCASHX handling: node with `temp['weights'] = {"XCASHX": 1.0}` — NAV unchanged; partial XCASHX — weighted correctly.
- [x] 5.9 Unit test child_series view update: after upward pass at t_idx=5, verify child_series is `nav_array[:6]` and shares memory (is a view).
- [x] 5.10 Integration test `Runner.run()` loop: build a small tree (WeightNode + 2 AssetNodes), run for 5 days with daily rebalance, verify NAV series are correct end-to-end. Downward Pass placeholder should carry forward equal weights from day 0.
- [x] 5.11 Integration test rebalance gating: weekly frequency — verify Downward Pass placeholder runs on day 0 and first day of new week only; weights carry forward on other days.
