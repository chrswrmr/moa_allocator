## Context

The DSL schema (`moa_DSL_schema.json`, JSON Schema draft-07) defines four node types via `oneOf` references: `ifElseNode`, `weightNode`, `filterNode`, `assetNode`. Each definition lists its type-specific `properties` but none declare a `required` array. The base `node` definition only requires `["id", "type"]`.

This means a document with `{"id": "...", "type": "weight"}` (no `method`, no `children`) passes schema validation. The compiler's `_build_node()` then hits `raw["method"]` and crashes with a `KeyError` — an unhelpful error for the user.

The same gap exists for sub-objects: `select` inside `filterNode` has no `required` for `mode`/`count`.

## Goals / Non-Goals

**Goals:**
- Add `required` arrays to all four node type definitions so missing fields are caught at schema validation time
- Add `required` to the `select` sub-object inside `filterNode`
- Update `dsl-schema-validation` spec with scenarios for the new constraints
- Verify `conditionMetric` and `sortMetric` already enforce their required fields correctly

**Non-Goals:**
- No changes to `compiler.py` runtime code — schema enforcement is sufficient
- No new semantic validation rules
- No support for optional `false_branch` (conditional allocation) — that is a separate change
- No DSL version bump — adding `required` to existing properties is a tightening of validation, not a schema contract change

## Decisions

### Decision 1: Add `required` at the node-type definition level

Add `required` arrays to `ifElseNode`, `weightNode`, `filterNode`, and `assetNode` definitions. This is the natural JSON Schema location since each definition already lists the properties.

**Alternative considered:** Add required-field checks in `_validate_semantics()`. Rejected because JSON Schema already provides this mechanism and the error messages from `jsonschema` are clear enough. Duplicating the check in Python adds maintenance burden.

### Decision 2: Required fields per node type

Based on `compiler.spec.md` required-field tables:

| Node type | Required fields (in addition to `id`, `type`) |
|---|---|
| `if_else` | `logic_mode`, `conditions`, `true_branch`, `false_branch` |
| `weight` | `method`, `children` |
| `filter` | `sort_by`, `select`, `children` |
| `asset` | `ticker` |

Additionally, the `select` sub-object requires `mode` and `count`.

### Decision 3: No DSL version bump

Per `dsl-integrity.md`, `version-dsl` is frozen at `"1.0.0"` for all v1 work. Adding `required` arrays tightens validation of existing properties — it does not add new properties or change behavior for valid documents. No ADR needed.

### Decision 4: `conditionMetric` and `sortMetric` already handled

The schema already declares `required: ["asset", "function"]` on `conditionMetric` and `required: ["function"]` on `sortMetric`. No changes needed there.

## Risks / Trade-offs

- **[Risk] Existing strategy files that omit optional-looking fields will now fail validation** → Mitigation: The fields being required match what `_build_node()` already accesses unconditionally, so any strategy that worked before must already have these fields. This change just moves the error from a Python crash to a schema validation error.
- **[Risk] `method_params` is intentionally optional on weight nodes** → Not adding it to required. It's only needed for `defined` and `inverse_volatility` methods, and the semantic validator already checks those cases.
