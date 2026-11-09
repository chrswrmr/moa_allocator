## Why

Commit `62be8aa` ("run always 2 stage validation") changed `compile_strategy()` to run `_validate_semantics()` even when JSON Schema validation fails, so that node-attributed semantic errors are reported in preference to root-level schema errors. But `_validate_semantics()` assumes a schema-valid document and indexes `doc["settings"]` and `node["select"]["count"]` directly. On a structurally broken document it raises a bare `KeyError` that escapes `compile_strategy()`. Three tests in `test_compile_strategy_validation.py` have been failing since that commit, and the behaviour change was never written into a spec.

## What Changes

- `compile_strategy()` catches non-`DSLValidationError` exceptions from `_validate_semantics()` when a schema error is pending and raises the schema error instead. When the document is schema-valid, exceptions still propagate unchanged.
- `dsl-schema-validation` spec: document the two-stage behaviour (semantic error preferred, schema error as fallback, no bare exceptions leak) with three scenarios.
- Tests: the three existing failing tests pass again; two new tests pin the fallback and the semantic-preferred ordering.

No change to `_validate_semantics()` itself, to the schema, or to error messages.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dsl-schema-validation`: "Schema validation" requirement gains the two-stage rule: on a schema violation, semantic validation still runs; a semantic `DSLValidationError` wins; any other outcome reports the schema error.

## Impact

- `moa_allocations/compiler/compiler.py` — `compile_strategy()` step 3, a few lines.
- `openspec/specs/dsl-schema-validation/spec.md` — requirement text and scenarios.
- `tests/unit/test_compile_strategy_validation.py` — two new tests; three existing tests go green.
- Callers (CLI, `moa_portrunner`) see a `DSLValidationError` with exit code 1 instead of an unhandled `KeyError` with exit code 3 for malformed strategy files.
