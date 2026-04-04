## Why

The JSON Schema node type definitions (`ifElseNode`, `weightNode`, `filterNode`, `assetNode`) do not declare `required` arrays for their type-specific fields. A document like `{"id": "...", "type": "weight"}` (missing `method` and `children`) passes schema validation, then crashes the compiler with a `KeyError` in `_build_node()`. Required-field enforcement should happen at the schema level (fail-fast) rather than relying on Python runtime errors.

## What Changes

- Add `required` arrays to each node type definition in `moa_DSL_schema.json`:
  - `ifElseNode`: require `logic_mode`, `conditions`, `true_branch`, `false_branch`
  - `weightNode`: require `method`, `children`
  - `filterNode`: require `sort_by`, `select`, `children`
  - `assetNode`: require `ticker`
- Add `required` arrays to sub-objects that lack them:
  - `conditionMetric`: require `asset`, `function` (already declared in schema but verify enforcement via `oneOf`)
  - `sortMetric`: require `function`
  - `select` (inside filterNode): require `mode`, `count`
- Update the `dsl-schema-validation` spec to document the new required-field constraints
- Add compiler tests for each node type with missing required fields

## Capabilities

### New Capabilities

- `node-required-fields`: Schema-level enforcement of required fields per node type definition, ensuring invalid documents are rejected before semantic validation or node instantiation

### Modified Capabilities

- `dsl-schema-validation`: Adding required-field constraints to node type definitions in the schema and corresponding validation scenarios

## Impact

- **Schema**: `moa_DSL_schema.json` — adds `required` arrays to four node definitions and two sub-object definitions
- **Specs**: `dsl-schema-validation` spec updated with new scenarios
- **Tests**: New test cases in compiler tests for missing-field rejection
- **Reference doc**: `moa_Req_to_DSL.md` — Filter and Asset schema snippets updated with explicit `required` arrays and `select.required` for consistency
- **No runtime code changes**: The compiler (`compiler.py`) does not need modification — schema validation already runs before `_build_node()`, so the new `required` arrays will catch missing fields at the schema step
