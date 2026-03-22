## 1. PriceDataError Exception

- [x] 1.1 Define `PriceDataError(Exception)` in `moa_allocations/engine/runner.py` with `__init__(self, message: str)`
- [x] 1.2 Export `PriceDataError` from `moa_allocations/engine/__init__.py`

## 2. Runner Skeleton

- [x] 2.1 Create `moa_allocations/engine/runner.py` with `class Runner`
- [x] 2.2 Implement `Runner.__init__(self, root: RootNode, price_data: pd.DataFrame)` signature and store `self.root`, `self.price_data`, `self.settings = root.settings`
- [x] 2.3 Export `Runner` from `moa_allocations/engine/__init__.py`

## 3. Tree Traversal Helpers

- [x] 3.1 Implement `_collect_tickers(root: RootNode) -> set[str]` — BFS walk collecting all `AssetNode` tickers plus condition-referenced asset tickers from `IfElseNode` conditions
- [x] 3.2 Implement `_compute_max_lookback(root: RootNode) -> int` — BFS walk collecting all lookback values from `FilterNode.sort_by["lookback"]`, `WeightNode.method_params["lookback"]` (inverse_volatility only), and `IfElseNode` condition lookbacks; return max (0 if none)

## 4. Price Data Validation

- [x] 4.1 Implement ticker coverage check: call `_collect_tickers`, find missing tickers (`set - price_data.columns`), raise `PriceDataError` listing all missing if any
- [x] 4.2 Implement date range check: call `_compute_max_lookback`, compute required start as `start_date` offset by `max_lookback` trading days (use `price_data.index` to count backwards), raise `PriceDataError` if `price_data.index[0]` is after the required start or `price_data.index[-1]` is before `end_date`
- [x] 4.3 Call both validation checks at the end of `__init__` (after tree traversal, before numpy conversion)

## 5. AlgoStack Attachment

- [x] 5.1 Implement `_build_algo_stack(node: StrategyNode) -> list` — dispatch on `isinstance` to build the correct AlgoStack for `WeightNode`, `FilterNode`, `IfElseNode`; return `[]` for `AssetNode`
- [x] 5.2 BFS-traverse the tree in `__init__` and call `_build_algo_stack` for each `StrategyNode`, assigning the result to `node.algo_stack`

## 6. Price Series Pre-computation

- [x] 6.1 For each `StrategyNode` encountered during the BFS traversal, populate `node.perm["child_series"]` as a `dict[str, np.ndarray]`: for each `AssetNode` child use `price_data[ticker].to_numpy()`; for each `StrategyNode` child insert an empty `np.ndarray` placeholder (the upward pass will fill this)
- [x] 6.2 For `IfElseNode` nodes, also populate `perm["child_series"]` with numpy arrays for any condition-referenced tickers (keyed by the asset string, e.g. `"SPY"`)

## 7. Tests

- [x] 7.1 Test `PriceDataError` is raised with missing tickers (single and multiple)
- [x] 7.2 Test `PriceDataError` is raised when `price_data` starts too late (insufficient lookback history)
- [x] 7.3 Test `PriceDataError` is raised when `price_data` ends before `end_date`
- [x] 7.4 Test successful construction: `algo_stack` types match expected classes for a `WeightNode(equal)`, `WeightNode(defined)`, `WeightNode(inverse_volatility)`, `FilterNode(top)`, `FilterNode(bottom)`, `IfElseNode`
- [x] 7.5 Test `AssetNode` leaves have no `algo_stack` set by Runner
- [x] 7.6 Test `perm["child_series"]` contains the correct numpy array for an `AssetNode` child (values match `price_data[ticker].to_numpy()`)
- [x] 7.7 Test `perm["child_series"]` contains an empty placeholder for a `StrategyNode` child
- [x] 7.8 Test `_compute_max_lookback` returns the correct maximum across mixed node types
- [x] 7.9 Run `uv run pytest` — all tests must pass
