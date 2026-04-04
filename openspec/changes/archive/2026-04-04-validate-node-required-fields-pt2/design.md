## Context

Part 1 (`validate-node-required-fields`) added `required` arrays to all node type definitions in the JSON Schema. This catches missing fields but not empty-but-present values: `"children": []`, `"conditions": []`, and `"ticker": ""` all pass schema validation, then crash the engine at runtime with opaque errors (division by zero, undefined branch selection, failed price fetch).

The compiler already has a two-layer validation pipeline: JSON Schema validation first (`jsonschema.validate()`), then `_validate_semantics()`. Both layers need to be extended.

## Goals / Non-Goals

**Goals:**

- Reject empty `children` arrays on weight and filter nodes at schema level (`minItems: 1`)
- Reject empty `conditions` array on if_else nodes at schema level (`minItems: 1`)
- Reject empty `ticker` string on asset nodes at schema level (`minLength: 1`)
- Add matching semantic checks in `_validate_semantics()` for all four cases, providing `node_id`/`node_name` in the error for frontend block highlighting

**Non-Goals:**

- Modifying `required` arrays (already done in pt1)
- Validating condition content structure (already handled by schema)
- Handling `false_branch: null` (valid use case)
- Any engine or algo changes

## Decisions

### 1. Schema constraints via property-level `minItems`/`minLength`

Add constraints directly on the existing property definitions in `moa_DSL_schema.json`:

```
ifElseNode.conditions  → add "minItems": 1
weightNode.children    → add "minItems": 1
filterNode.children    → add "minItems": 1
assetNode.ticker       → add "minLength": 1
```

**Why not a separate `allOf` or `if/then`?** Property-level constraints are simpler, produce clearer jsonschema error messages, and match the existing pattern in the schema. No need for indirection.

### 2. Belt-and-suspenders semantic checks

Add four checks in `_validate_semantics()` that duplicate the schema constraints but with `node_id`-enriched errors. These go in a new section after the existing UUID uniqueness check (early in the function, before any check that assumes non-empty arrays):

```
weight node:  len(children) == 0  → DSLValidationError
filter node:  len(children) == 0  → DSLValidationError
if_else node: len(conditions) == 0 → DSLValidationError
asset node:   ticker == ""         → DSLValidationError
```

**Why duplicate the schema check?** The schema error reports `node_id="root"` because jsonschema doesn't know which node failed (it just sees a path like `/root_node/children/0/children`). The semantic check can report the exact `node_id` and `node_name` of the offending node, which the moa_shell frontend needs to highlight the specific block.

**Placement:** Insert right after the UUID uniqueness loop, before the defined-weight and filter-count checks. This ensures:
- Empty arrays are caught before `select.count > len(children)` would give a misleading "count exceeds 0 children" error
- The check order matches severity: structural emptiness → weight/filter specifics → metric lookbacks → netting

### 3. Single traversal for new checks

The new checks reuse the existing `all_nodes` list from `_collect_nodes()`. Each check iterates `all_nodes` filtering by type — same pattern as the existing defined-weight and filter-select checks. No new tree traversal needed.

## Risks / Trade-offs

- **Existing strategies with empty arrays break at validation** → This is intentional. These strategies already crash at runtime; failing earlier with a clear message is strictly better. No migration needed.
- **Schema change requires ADR per `dsl-integrity` rule** → The `minItems`/`minLength` additions are additive constraints on existing properties, not structural changes. They tighten the contract but don't change the node type definitions. An ADR entry should be added to `DECISIONS.md` to document this.
- **Semantic checks are redundant with schema** → By design. The cost is four simple `if` checks; the benefit is precise error attribution.
