## Context

`_build_algo_stack` in `runner.py` maps `weight / inverse_volatility` to `[SelectAll(), WeightInvVol(node.method_params["lookback"])]`. The JSON schema lists `method_params.lookback` as an optional property and semantic validation has no rule tying it to the method, so a node without it compiles and fails only when the Runner is constructed. Validation-only callers (`--validate`) therefore report success for a strategy that cannot run.

## Goals / Non-Goals

**Goals:**
- Reject the malformed node at validation time with a node-attributed `DSLValidationError`.
- Match the blueprint: lookback is required for inverse volatility.

**Non-Goals:**
- Introducing a default lookback. The blueprint says required, and silently choosing a window would change results without the user knowing.
- Schema-level enforcement via `if/then`. Possible in draft-07 but would need an ADR and would produce a root-level error without node attribution. The semantic layer gives the better message; the same choice was made for metric lookbacks.
- Hardening `_build_algo_stack` with `.get()`. Validation is the contract; the engine may assume validated input (ADR-008 precedent).

## Decisions

**1. Enforce in `_validate_semantics()`, in the existing "Lookback required" section.**
It sits next to the analogous rule for conditionMetric and sortMetric lookbacks, uses the same error shape, and runs on both `--validate` and full runs.

**2. Error message names the method and the field.**
`weight method 'inverse_volatility' requires 'method_params.lookback'`. The frontend keys off `node_id`; the message is for humans.

**3. Treat missing `method_params` and `method_params` without `lookback` identically.**
Both are the same user mistake.

## Risks / Trade-offs

- [Strategies that validated before now fail] → they crashed at Runner construction anyway; the new failure is earlier and explains itself.

## Migration Plan

None. Rollback is a revert.

## Open Questions

None.
