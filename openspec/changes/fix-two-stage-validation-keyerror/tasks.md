## 1. Compiler

- [x] 1.1 In `compile_strategy()` (`moa_allocations/compiler/compiler.py`, step 3), catch any non-`DSLValidationError` exception from `_validate_semantics(doc)`; if `schema_error` is set, fall through to raising the schema `DSLValidationError`, otherwise re-raise. `DSLValidationError` from semantics continues to propagate.

## 2. Tests

- [x] 2.1 Confirm the three previously failing tests in `tests/unit/test_compile_strategy_validation.py` pass: `test_missing_settings_raises_dsl_error`, `test_filter_missing_required_field[select]`, `test_filter_select_missing_field[count]`
- [x] 2.2 Add test: document with both a schema violation (`starting_cash` as string) and a semantic violation (duplicate node id) raises the semantic `DSLValidationError` with the offending `node_id`
- [x] 2.3 Add test: document missing `settings` raises `DSLValidationError` whose message is the schema message (mentions `settings`), proving no `KeyError` escaped

## 3. Verification

- [x] 3.1 Run `uv run pytest` — full suite green (399 passed, 1 skipped, 0 failed)
- [x] 3.2 Run `uvx ruff check .` — no new findings (56 pre-existing)
