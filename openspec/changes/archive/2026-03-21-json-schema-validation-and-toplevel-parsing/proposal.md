## Why

`compile_strategy()` is the entry point to the entire compiler pipeline, but steps 1 and 2 — loading JSON from disk and validating it against the DSL schema — are not yet implemented. Without this gate, any downstream compiler or engine code can receive malformed or version-mismatched input, making silent failures or confusing errors inevitable.

## What Changes

- `compile_strategy(path)` in `moa_allocations/compiler/compiler.py` gains its first two steps:
  - Load and JSON-parse the file at `path`
  - Validate the parsed document against `moa_DSL_schema.json` using `jsonschema`
  - Extract top-level fields: `id`, `version-dsl`, `settings`, `root_node`
  - Raise `DSLValidationError(node_id="root", node_name="settings", message=...)` on any schema violation or if `version-dsl != "1.0.0"`
- `moa_DSL_schema.json` is copied from `openspec/moa_strategy_DSL/` into `moa_allocations/compiler/schema/` so the compiler can resolve it at runtime
- `jsonschema` is added as a project dependency

## Capabilities

### New Capabilities
- `dsl-schema-validation`: JSON loading, schema validation, top-level field extraction, DSL version check (`version-dsl == "1.0.0"`), and `DSLValidationError` propagation for `compile_strategy()`

### Modified Capabilities
_(none — no existing spec-level requirements are changing)_

## Impact

- **Files changed**: `moa_allocations/compiler/compiler.py`
- **New file**: `moa_allocations/compiler/schema/moa_DSL_schema.json` (copied from `openspec/moa_strategy_DSL/`)
- **Dependency added**: `jsonschema`
- **Depends on**: C1 (`DSLValidationError` class must already exist)
- **Out of scope**: Semantic validation (C3), recursive node instantiation (C4)
