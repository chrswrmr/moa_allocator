## 1. Weight carry-forward storage

- [x] 1.1 In `Runner.__init__`, create `self._prev_weights: dict[str, dict[str, float]]` mapping node id → prior-day weights (initialised empty)
- [x] 1.2 In `Runner.run()` day loop, after temp reset (`node.temp = {"t_idx": t_idx}`), restore each node's `temp["weights"]` from `_prev_weights` if an entry exists — so the Upward Pass can read prior-day weights

## 2. Temp reset

- [x] 2.1 In `Runner.run()`, at the start of each day (before Upward Pass), reset `node.temp = {"t_idx": t_idx}` for every `StrategyNode` in `_strategy_nodes`

## 3. Downward Pass method

- [x] 3.1 Add `Runner._downward_pass(self, t_idx: int) -> None` that iterates `reversed(self._upward_order)` (root-first)
- [x] 3.2 For each node, execute algos sequentially: `for algo in node.algo_stack: if not algo(node): node.temp['weights'] = {'XCASHX': 1.0}; break`
- [x] 3.3 After successful stack completion, normalise `node.temp['weights']` to sum to 1.0; if sum is 0.0, fall back to `{'XCASHX': 1.0}`
- [x] 3.4 After each node completes (success or XCASHX), store `node.temp['weights']` into `_prev_weights[node.id]`

## 4. Wire into run() loop

- [x] 4.1 Replace the `# Downward Pass placeholder — E3` block in `Runner.run()` with `self._downward_pass(t_idx)` on rebalance days
- [x] 4.2 Verify day 0 always calls `_downward_pass(0)` (already true — `is_rebalance = True` on `t_idx == 0`)

## 5. Tests

- [x] 5.1 Test temp reset: verify `node.temp == {"t_idx": t_idx}` at start of each day before passes run
- [x] 5.2 Test top-down order: mock algo stacks on a two-level tree, assert root executes before child
- [x] 5.3 Test successful stack: `WeightNode(equal)` with 3 asset children → `temp['weights']` has 3 equal entries summing to 1.0
- [x] 5.4 Test XCASHX fallback: `FilterNode` with `SelectTopN` where all metrics are NaN → `temp['weights'] == {'XCASHX': 1.0}`
- [x] 5.5 Test normalisation: inject a weighting algo that produces non-normalised weights, verify they sum to 1.0 after downward pass
- [x] 5.6 Test weight carry-forward: run two days with monthly rebalance, verify day 2 (non-rebalance) uses day 1's weights in the Upward Pass
- [x] 5.7 Test IfElseNode routing: condition true → `temp['weights']` keys only the true_branch id
- [x] 5.8 Run full test suite (`uv run pytest`) — all existing + new tests pass (3 pre-existing failures in test_run_entry_point.py are unrelated to E3)
