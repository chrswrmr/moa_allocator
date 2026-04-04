## Why

Empty arrays and empty strings pass schema validation (the field is present, satisfying `required`) but crash the engine at runtime with unhelpful errors like "float division by zero" (exit code 3). Part 1 added `required` fields to all node types; this part closes the remaining gap by rejecting empty-but-present values at both the schema and semantic layers so users see clean `DSLValidationError` messages (exit code 1) with a `node_id` the frontend can highlight.

## What Changes

- Add `minItems: 1` to `ifElseNode.conditions`, `weightNode.children`, and `filterNode.children` in `moa_DSL_schema.json`
- Add `minLength: 1` to `assetNode.ticker` in `moa_DSL_schema.json`
- Add semantic checks in `_validate_semantics()` that raise `DSLValidationError(node_id, node_name, message)` for:
  - weight node with zero children
  - filter node with zero children
  - if_else node with empty conditions
  - asset node with empty ticker string

## Capabilities

### New Capabilities

_(none — all changes extend existing capabilities)_

### Modified Capabilities

- `dsl-schema-validation`: Add `minItems: 1` constraints on array fields and `minLength: 1` on ticker to reject empty-but-present values at the schema layer
- `semantic-validation`: Add belt-and-suspenders checks for empty children, conditions, and ticker that provide node-specific error messages with `node_id`

## Impact

- **Schema**: `moa_allocations/compiler/schema/moa_DSL_schema.json` — four constraint additions
- **Compiler**: `moa_allocations/compiler/compiler.py` `_validate_semantics()` — four new checks
- **Tests**: New test cases for empty arrays/strings at both validation layers
- **Existing strategies**: Any strategy with empty `children`, `conditions`, or `ticker` fields would now fail at validation instead of at runtime — this is the intended fix, not a regression
