## Why

A `weight` node with `method: "inverse_volatility"` and no `method_params.lookback` passes `--validate` cleanly, then crashes the full run with a bare `KeyError: 'lookback'` (exit code 3) when `Runner.__init__` builds the AlgoStack. `BUG_REPORT_lookback_keyerror.md` documents this from `moa_shell`; the report blamed `sma_price` conditions, but the reproduction shows the root `inverse_volatility` node with no `method_params` is the cause. The blueprint (`openspec/changes/Starting_points/compiler.spec.md`, field table) already states that `method_params.lookback` is required when `method == "inverse_volatility"`; the compiler never enforced it.

## What Changes

- `_validate_semantics()` gains a rule: a `weight` node whose `method` is `"inverse_volatility"` MUST have `method_params.lookback`. Violation raises `DSLValidationError` with the node's `id` and `name`, so `--validate` rejects the strategy and the frontend can highlight the block.
- Tests: missing `method_params`, empty `method_params`, present lookback, and the bug-report tree shape.
- Spec: new requirement in `semantic-validation`.

No schema change (so no ADR). No engine change: `_build_algo_stack` keeps indexing `method_params["lookback"]`, which is now guaranteed by validation. No default lookback is introduced, matching the blueprint.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `semantic-validation`: ADDED requirement "Inverse-volatility weight node requires lookback".

## Impact

- `moa_allocations/compiler/compiler.py` — one check in the lookback section of `_validate_semantics()`.
- `openspec/specs/semantic-validation/spec.md` — one new requirement.
- `tests/unit/test_semantic_validation.py` — new test class.
- Existing strategy files with `inverse_volatility` and no lookback now fail validation with a clear message. They already crashed at runtime, so this is strictly an improvement.
- Resolves `BUG_REPORT_lookback_keyerror.md`.
