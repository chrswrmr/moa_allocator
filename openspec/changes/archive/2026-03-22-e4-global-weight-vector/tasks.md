## 1. Leaf Order Collection

- [x] 1.1 Add `_collect_leaf_order(root)` helper: DFS walk of the compiled tree collecting asset tickers (uppercase) in DSL left-to-right order. Return `list[str]`.
- [x] 1.2 Call `_collect_leaf_order` in `Runner.__init__()` and store as `self._leaf_order`

## 2. Global Weight Flattening

- [x] 2.1 Add `_flatten_weights(root_node)` method on `Runner`: DFS from `root.root`, multiply cumulative parent weight by each child's local weight from `temp['weights']`, accumulate leaf weights into a `dict[str, float]`. Handle `XCASHX` as a virtual leaf key.
- [x] 2.2 Add sum-to-one assertion after flattening: `assert abs(sum - 1.0) < 1e-9`

## 3. Simulation Loop Integration

- [x] 3.1 Wire `_flatten_weights` into `run()`: call after each Downward Pass on rebalance days, append the resulting dict to a `rows` list
- [x] 3.2 Implement carry-forward: on non-rebalance days, copy the previous day's global weight dict into `rows`
- [x] 3.3 Track whether `XCASHX` appeared on any day (for column inclusion)

## 4. Output Assembly

- [x] 4.1 After the simulation loop, build `pd.DataFrame` from collected `rows` with column order `['DATE'] + leaf_order + (['XCASHX'] if seen)`
- [x] 4.2 Change `run()` return type from `None` to `pd.DataFrame`
- [x] 4.3 Write DataFrame to `output/allocations.csv` (`index=False`), creating `output/` directory if absent via `pathlib.Path.mkdir(exist_ok=True)`

## 5. Export Verification

- [x] 5.1 Confirm `Runner` is already exported from `engine/__init__.py` (no change expected)

## 6. Tests

- [x] 6.1 Test `_flatten_weights` with a simple two-level equal-weight tree
- [x] 6.2 Test `_flatten_weights` with nested weight nodes (3 levels)
- [x] 6.3 Test `_flatten_weights` with `if_else` node (only selected branch receives weight)
- [x] 6.4 Test `_flatten_weights` with `XCASHX` from AlgoStack halt
- [x] 6.5 Test sum-to-one assertion fires on invalid weights
- [x] 6.6 Test carry-forward on non-rebalance day (weekly frequency)
- [x] 6.7 Test DataFrame column order: DATE first, tickers in DSL leaf order, XCASHX last if present
- [x] 6.8 Test XCASHX column absent when never triggered
- [x] 6.9 Test CSV file written to `output/allocations.csv`
- [x] 6.10 Run full `uv run pytest` and verify all tests pass
