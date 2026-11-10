## 1. Compiler

- [x] 1.1 In `_validate_semantics()` (`moa_allocations/compiler/compiler.py`, "Lookback required" section), raise `DSLValidationError(node_id, node_name, "weight method 'inverse_volatility' requires 'method_params.lookback'")` when a `weight` node has `method == "inverse_volatility"` and `method_params` is absent or lacks `lookback`

## 2. Tests

- [x] 2.1 Add a test class to `tests/unit/test_semantic_validation.py`: inverse_volatility with lookback passes; without `method_params` fails with the weight node id and "method_params.lookback" in the message; with empty `method_params` fails likewise; `equal` without `method_params` passes
- [x] 2.2 Add a regression test reproducing the bug-report tree shape (inverse_volatility root, if_else child with sma_price conditions, filter false branch) and asserting `DSLValidationError` on the root node id

## 3. Verification

- [x] 3.1 Run `uv run pytest` — full suite green (404 passed, 1 skipped)
- [x] 3.2 Run `uvx ruff check .` — no new findings (56 pre-existing)
