## 1. Lookback Conversion Helper

- [x] 1.1 Implement `_convert_lookback(time_offset: str) -> int` in `compiler.py` — parse `^[0-9]+[dwm]$` strings and return integer trading days using multipliers `d=1, w=5, m=21`. Raise `DSLValidationError` on invalid format.
- [x] 1.2 Write tests for `_convert_lookback`: days (`"200d"` → 200), weeks (`"4w"` → 20), months (`"3m"` → 63), and invalid input.

## 2. Settings Construction

- [x] 2.1 Implement `_build_settings(raw: dict) -> Settings` in `compiler.py` — convert `start_date`/`end_date` to `date` objects, apply defaults (`slippage=0.0005`, `fees=0.0`, `rebalance_threshold=None`).
- [x] 2.2 Write tests for `_build_settings`: all fields provided, optional fields omitted with defaults applied.

## 3. Recursive Node Builder

- [x] 3.1 Implement `_build_node(raw: dict) -> StrategyNode | AssetNode` in `compiler.py` — dispatch on `raw["type"]` to instantiate `AssetNode`, `WeightNode`, `FilterNode`, or `IfElseNode`. Recurse into `children`, `true_branch`, `false_branch`.
- [x] 3.2 Apply `_convert_lookback` to all `lookback` and `duration` fields during node construction: condition metrics (`lhs.lookback`, `rhs.lookback`), condition `duration` (default `"1d"` if absent), `sort_by.lookback`, `method_params.lookback`.
- [x] 3.3 Raise `DSLValidationError` for unrecognized node types (defensive guard).

## 4. Compile Strategy Completion

- [x] 4.1 Replace the `NotImplementedError` stub in `compile_strategy()` with calls to `_build_settings`, `_build_node`, and `RootNode` assembly. Pass `dsl_version` from the document.
- [x] 4.2 Verify `compile_strategy` is already exported from `compiler/__init__.py` — no changes expected.

## 5. Integration Tests

- [x] 5.1 Test full `compile_strategy()` with a valid `.moastrat.json` fixture containing mixed node types (weight → asset, if_else with branches, filter with children). Verify returned `RootNode` has correct `settings`, `root` tree structure, and `dsl_version`.
- [x] 5.2 Test lookback conversion end-to-end: compile a strategy with `"200d"`, `"4w"`, `"3m"` lookbacks and verify all are converted to integers on the instantiated nodes.
- [x] 5.3 Test that compilation of a valid strategy never raises — confirm no partial tree or `NotImplementedError`.
- [x] 5.4 Run `uv run pytest` and confirm all existing + new tests pass.
