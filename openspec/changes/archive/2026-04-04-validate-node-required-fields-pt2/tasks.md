## 1. ADR

- [x] 1.1 Add ADR entry to `DECISIONS.md` documenting the addition of `minItems`/`minLength` constraints to `moa_DSL_schema.json` (required by `dsl-integrity` rule before any schema modification)

## 2. JSON Schema Constraints

- [x] 2.1 Add `"minItems": 1` to `ifElseNode.conditions` in `moa_DSL_schema.json`
- [x] 2.2 Add `"minItems": 1` to `weightNode.children` in `moa_DSL_schema.json`
- [x] 2.3 Add `"minItems": 1` to `filterNode.children` in `moa_DSL_schema.json`
- [x] 2.4 Add `"minLength": 1` to `assetNode.ticker` in `moa_DSL_schema.json`

## 3. Semantic Validation Checks

- [x] 3.1 Add empty-children check for weight nodes in `_validate_semantics()` — raise `DSLValidationError(node_id, node_name, "weight node must have at least one child")`
- [x] 3.2 Add empty-children check for filter nodes in `_validate_semantics()` — raise `DSLValidationError(node_id, node_name, "filter node must have at least one child")`
- [x] 3.3 Add empty-conditions check for if_else nodes in `_validate_semantics()` — raise `DSLValidationError(node_id, node_name, "if_else node must have at least one condition")`
- [x] 3.4 Add empty-ticker check for asset nodes in `_validate_semantics()` — raise `DSLValidationError(node_id, node_name, "asset node must have a non-empty ticker")`

## 4. Tests

- [x] 4.1 Add schema-level tests: empty `conditions`, `children`, and `ticker` each rejected with `DSLValidationError`
- [x] 4.2 Add schema-level tests: non-empty `conditions`, `children`, and `ticker` still pass validation
- [x] 4.3 Add semantic-level tests: empty arrays/strings raise `DSLValidationError` with correct `node_id` and message
- [x] 4.4 Run full test suite (`uv run pytest`) and verify no regressions
