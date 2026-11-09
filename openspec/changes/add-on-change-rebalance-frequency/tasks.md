## 1. Schema and DSL documentation

- [x] 1.1 Add `"on_change"` to `settings.rebalance_frequency.enum` in `moa_allocations/compiler/schema/moa_DSL_schema.json`
- [x] 1.2 Add `"on_change"` to `settings.rebalance_frequency.enum` in `openspec/moa_strategy_DSL/moa_DSL_schema.json` (enum only; do not sync other differences)
- [x] 1.3 In `openspec/moa_strategy_DSL/moa_Req_to_DSL.md`, list `on_change` in the `rebalance_frequency` field description and in the inline schema snippet, with the one-line semantics: "the engine evaluates the tree every trading day; moa_rebalancer trades only when the resulting weights change."

## 2. Engine

- [x] 2.1 Add explicit `elif frequency == "on_change": return True` branch to `_is_rebalance_day` in `moa_allocations/engine/runner.py`, keeping the trailing `return True`
- [x] 2.2 Update the `rebalance_frequency` type comment on `Settings` in `moa_allocations/engine/strategy.py` to include `"on_change"`

## 3. Decisions record

- [x] 3.1 Add ADR-009 to `DECISIONS.md` (above the "Add new ADRs" marker): enum extended with `on_change`; allocator treats it as evaluate-every-day; change/drift gate stays in `moa_rebalancer` (ADR-005); `version-dsl` unchanged

## 4. Tests

- [x] 4.1 Add unit test in the `_is_rebalance_day` section of `tests/unit/test_runner_e2.py`: `"on_change"` returns `True` for a same-week, same-month date pair
- [x] 4.2 Add test: a minimal strategy JSON with `"rebalance_frequency": "on_change"` passes `compile_strategy()` (schema accepts the value and `Settings.rebalance_frequency == "on_change"`)
- [x] 4.3 Add engine test: running an `on_change` strategy over N trading days yields exactly N output rows and the Downward Pass runs every day (weights track a daily-changing selection, matching `daily` output)
- [x] 4.4 Confirm existing `daily`/`weekly`/`monthly` tests are unchanged and still pass

## 5. Verification

- [x] 5.1 Run `uv run pytest` — 395 passed, 1 skipped, all new tests green; 3 failures in `test_compile_strategy_validation.py` (`KeyError` in `_validate_semantics`) are pre-existing at HEAD b704f92 and unrelated to this change
- [x] 5.2 Run `ruff check .` (via `uvx`; ruff is not a project dependency) — 57 pre-existing findings, 0 new; none on lines touched by this change
