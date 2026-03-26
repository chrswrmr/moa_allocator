## 1. Update SelectIfCondition

- [x] 1.1 Add `price_offset: int` parameter to `SelectIfCondition.__init__` and store as `self._price_offset`
- [x] 1.2 Add `price_offset: int` parameter to `_evaluate_condition_at_day` and update both series slices from `[: day_idx + 1]` to `[: price_offset + day_idx + 1]`
- [x] 1.3 Update `SelectIfCondition.__call__` to pass `self._price_offset` through to each `_evaluate_condition_at_day` call

## 2. Update _build_algo_stack

- [x] 2.1 Add `price_offset: int` parameter to `_build_algo_stack`
- [x] 2.2 Pass `price_offset` to `SelectIfCondition(node.conditions, node.logic_mode, price_offset)` in the `IfElseNode` branch
- [x] 2.3 Update the call site in `Runner.__init__` from `_build_algo_stack(node)` to `_build_algo_stack(node, self._price_offset)`

## 3. Tests

- [x] 3.1 Add unit test for `_evaluate_condition_at_day` with `price_offset > 0` — assert `current_price` reads from `price_arr[price_offset + t_idx]`, not `price_arr[t_idx]`
- [x] 3.2 Add unit test for `sma_price` condition with `price_offset > 0` — assert the SMA window ends at the correct simulation date
- [x] 3.3 Add unit test for `price_offset=0` — assert existing behaviour is unchanged
- [x] 3.4 Run `uv run pytest` and confirm all tests pass
