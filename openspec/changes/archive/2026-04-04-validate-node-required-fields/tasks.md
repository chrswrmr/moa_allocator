## 1. Schema Changes

- [x] 1.1 Add `required: ["logic_mode", "conditions", "true_branch", "false_branch"]` to `ifElseNode` definition in `moa_allocations/compiler/schema/moa_DSL_schema.json`
- [x] 1.2 Add `required: ["method", "children"]` to `weightNode` definition
- [x] 1.3 Add `required: ["sort_by", "select", "children"]` to `filterNode` definition
- [x] 1.4 Add `required: ["ticker"]` to `assetNode` definition
- [x] 1.5 Add `required: ["mode", "count"]` to `select` sub-object inside `filterNode`

## 2. Tests

- [x] 2.1 Add test: `if_else` node missing each required field (`logic_mode`, `conditions`, `true_branch`, `false_branch`) raises `DSLValidationError`
- [x] 2.2 Add test: `weight` node missing `method` or `children` raises `DSLValidationError`
- [x] 2.3 Add test: `filter` node missing `sort_by`, `select`, or `children` raises `DSLValidationError`
- [x] 2.4 Add test: `asset` node missing `ticker` raises `DSLValidationError`
- [x] 2.5 Add test: `filter` node with `select` missing `mode` or `count` raises `DSLValidationError`
- [x] 2.6 Verify existing tests still pass (no regressions from tightened schema)

## 3. Spec Sync

- [x] 3.1 Verify the canonical schema copy at `openspec/moa_strategy_DSL/moa_DSL_schema.json` matches `moa_allocations/compiler/schema/moa_DSL_schema.json` after changes (or update both)
