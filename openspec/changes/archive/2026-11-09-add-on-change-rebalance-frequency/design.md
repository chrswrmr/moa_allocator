## Context

`_is_rebalance_day(current_date, prev_date, frequency)` in `runner.py` gates the Downward Pass. It has explicit branches for `daily`, `weekly`, `monthly` and a trailing `return True`. The DSL schema enum currently allows only those three values, so an `on_change` strategy is rejected at compile time before the engine ever sees it.

`moa_rebalancer` has independently adopted `on_change`: it compares each day's allocation row to the last traded target and trades only when the row differs. For that to work, the allocator must (a) accept the value and (b) emit a row for every trading day, which it already does for every frequency (carry-forward days still produce a row). ADR-005 already places all drift/threshold logic in `moa_rebalancer`; this change keeps that boundary.

## Goals / Non-Goals

**Goals:**
- `on_change` strategies compile and run in `moa_allocator`.
- The engine runs the Downward Pass every trading day for `on_change`, so each row reflects the freshly evaluated tree.
- The contract is explicit in code, spec, DSL docs and an ADR.

**Non-Goals:**
- No change-detection or drift logic in the allocator. The allocator never compares today's weights to yesterday's.
- No change to `moa_rebalancer`.
- No change to `version-dsl` (stays `1.0.0`; additive enum values do not break existing files).
- No syncing of the other, pre-existing differences between the two schema copies (`minItems`/`minLength` from ADR-008 are missing in the blueprint copy). That is out of scope here and noted as a follow-up.

## Decisions

**1. `on_change` is an alias for "evaluate every day" inside the allocator.**
Alternative considered: have the allocator suppress unchanged rows or add a `changed` flag column. Rejected because ADR-005 deliberately keeps the allocator a pure daily weight emitter; the rebalancer already owns the comparison and needs a full daily series to compare against. Emitting every row also makes `on_change` and `daily` output identical, which keeps the engine simple and testable.

**2. Add an explicit `elif frequency == "on_change": return True` branch instead of relying on the fallthrough.**
Alternative: leave the function unchanged since the fallthrough already returns `True`. Rejected because a load-bearing fallthrough is fragile: if someone later tightens the function to raise on unknown values (a reasonable hardening), `on_change` would silently break. The explicit branch documents intent and lets the spec table state the rule directly. The trailing `return True` is kept as-is.

**3. Extend the enum in both schema copies; do not bump `version-dsl`.**
Adding an enum value is backward compatible: every document that validated before still validates. `dsl-integrity` requires an ADR for any schema edit, so ADR-009 is added. The blueprint copy under `openspec/moa_strategy_DSL/` is edited too, as explicitly requested, even though `openspec/config.yaml` normally treats it as read-only.

**4. Spec delta only on `rebalance-schedule`.**
`dsl-schema-validation` describes the schema's structure for nodes, `time_offset` and `netting` but does not list the `rebalance_frequency` enum values, so there is nothing there to modify.

## Risks / Trade-offs

- [Allocator output for `on_change` is identical to `daily`, which could make the value look like a no-op] → the DSL doc line and ADR state explicitly that the semantic difference lives in `moa_rebalancer`.
- [The two schema copies continue to drift on unrelated constraints] → called out as a non-goal and follow-up; this change touches only the enum in both.
- [A future hardening of `_is_rebalance_day` to reject unknown values] → the explicit branch means `on_change` is unaffected.

## Migration Plan

Additive. No existing strategy files change. Deploy allocator, then `on_change` strategies become compilable. Rollback is reverting the commit; no data migration.

## Open Questions

None.
