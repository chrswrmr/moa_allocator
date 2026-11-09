## Why

`moa_rebalancer` now accepts `rebalance_frequency: "on_change"` (its change of the same name): the simulator trades only on days the allocation row differs from the last traded target, never on price drift. Strategies that use this value currently fail schema validation in `moa_allocator`, so they cannot be compiled or run at all. The allocator must accept the value and emit a weight row every trading day so the rebalancer can detect changes.

## What Changes

- Add `"on_change"` to the `settings.rebalance_frequency` enum in both copies of `moa_DSL_schema.json` (canonical compiler copy and the blueprint copy under `openspec/moa_strategy_DSL/`).
- Document the value in `openspec/moa_strategy_DSL/moa_Req_to_DSL.md` with one line of semantics: the engine evaluates the tree every trading day; `moa_rebalancer` trades only when the resulting weights change.
- `_is_rebalance_day` in `moa_allocations/engine/runner.py` gains an explicit `elif frequency == "on_change": return True` branch. Today the value only works through the trailing `return True` fallthrough; the explicit branch makes the contract visible and keeps the fallthrough as a defensive default rather than a load-bearing path.
- Update the `rebalance_frequency` type comment on `Settings` in `moa_allocations/engine/strategy.py`.
- Add an ADR to `DECISIONS.md` recording the enum extension and that the change/drift gate stays in `moa_rebalancer`.
- Tests: a strategy with `"on_change"` compiles; the engine produces one weight row per trading day for it; existing `daily`/`weekly`/`monthly` tests are unchanged.

No change to `moa_rebalancer`. No change to the engine's day loop, Upward/Downward Pass ordering, or output assembly: `on_change` behaves identically to `daily` inside the allocator.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rebalance-schedule`: "Rebalance day classification" gains a fourth frequency value, `"on_change"`, which always returns `True` (Downward Pass runs every trading day).

`dsl-schema-validation` was checked and does not enumerate the `rebalance_frequency` values, so no delta is needed there.

## Impact

- `moa_allocations/compiler/schema/moa_DSL_schema.json` — enum extension (requires an ADR per the `dsl-integrity` rule; this change adds ADR-009).
- `openspec/moa_strategy_DSL/moa_DSL_schema.json`, `openspec/moa_strategy_DSL/moa_Req_to_DSL.md` — blueprint docs kept in sync.
- `moa_allocations/engine/runner.py`, `moa_allocations/engine/strategy.py` — one explicit branch and a comment.
- `openspec/specs/rebalance-schedule/spec.md` — table row and scenario.
- `DECISIONS.md` — new ADR.
- `tests/unit/` — new compile and per-day-row tests.
- Downstream: `moa_rebalancer` consumers can now compile `on_change` strategies with this allocator. Existing strategy files are unaffected (additive enum change, `version-dsl` stays `1.0.0`).
