# Validate Node Required Fields — Starting Point

> Context for an `/opsx:new` or `/opsx:ff` change in moa_allocator.

## Problem

The DSL JSON Schema now has `required` fields on all node types (recently added), but empty arrays still pass validation. A weight node with `"children": []` or an if_else node with `"conditions": []` passes both schema and semantic validation, then crashes the engine at runtime with unhelpful errors like "float division by zero" (exit code 3) instead of clean `DSLValidationError` messages (exit code 1).

## Current State After Schema Update

`required` fields were added to all node types. What's still missing:

| Node | Field | `required`? | `minItems`? | Semantic check? | Runtime failure on empty |
|---|---|---|---|---|---|
| `ifElseNode` | `conditions` | Yes | **No** | **No** | Undefined branch selection |
| `ifElseNode` | `true_branch` | Yes | — | — | *(now caught by schema)* |
| `weightNode` | `children` | Yes | **No** | **No** | Division by zero |
| `filterNode` | `children` | Yes | **No** | **No** | Division by zero |
| `assetNode` | `ticker` | Yes | — | **No** (empty string) | Crash at price fetch |

## Scope

### Layer 1: JSON Schema (`moa_DSL_schema.json`)

Add `minItems: 1` to array fields where an empty array is meaningless:

```json
"ifElseNode.conditions":  add "minItems": 1
"weightNode.children":    add "minItems": 1
"filterNode.children":    add "minItems": 1
"assetNode.ticker":       add "minLength": 1
```

### Layer 2: Semantic validation (`_validate_semantics()`)

Add checks in `compiler.py` that raise `DSLValidationError(node_id, node_name, message)`:

- **weight node with zero children**: `"weight node must have at least one child"`
- **filter node with zero children**: `"filter node must have at least one child"`
- **if_else node with empty conditions**: `"if_else node must have at least one condition"`
- **asset node with empty ticker**: `"asset node must have a non-empty ticker"`

These are belt-and-suspenders — schema validation catches them first, but semantic checks provide better error messages with `node_id` for the frontend to highlight the specific block.

## Affected Specs

- `dsl-schema-validation` — schema changes (minItems, minLength)
- `semantic-validation` — new requirements for empty children/conditions/ticker checks

## Not In Scope

- Adding `required` fields to node types — already done
- Validating condition *content* (lhs/rhs structure) — already handled by schema `required` on `condition`
- `false_branch` being null — valid use case (conditional allocation)
- `PriceDataError.message` attribute bug in `engine/runner.py` — separate fix, already applied

## Discovery Source

Found during moa_shell backtest integration testing. The moa_shell strategy editor allows building these invalid trees, and without proper validation errors the user sees raw Python tracebacks instead of highlighted blocks in the editor.
