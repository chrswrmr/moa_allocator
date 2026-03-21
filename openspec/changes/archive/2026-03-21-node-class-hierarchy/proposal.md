# Proposal: Node Class Hierarchy

## What

Create the pure data structure foundation for the Strategy Tree:
`BaseNode`, `StrategyNode`, `IfElseNode`, `WeightNode`, `FilterNode`, `AssetNode`, `RootNode`, `Settings`, `DSLValidationError`, `PriceDataError`.

## Why

Every other module depends on these classes. The compiler instantiates them. The engine traverses them. The algos operate on them. Nothing else can be built until the shape of the tree is defined.

## Scope

**In scope:**
- Define all node classes with attributes per the Output Node Class Hierarchy section of `compiler.spec.md`
- Define `Settings` dataclass with all fields per `compiler.spec.md`
- Define `DSLValidationError(node_id, node_name, message)` and `PriceDataError(message)` in `exceptions.py`
- Update all docs and specs that reference `SecurityNode` → `AssetNode`

**Out of scope:**
- No DSL parsing or JSON validation
- No semantic validation logic
- No AlgoStack construction or attachment
- No engine simulation logic

## Files

| File | Content |
|---|---|
| `moa_allocations/engine/node.py` | `BaseNode`, `StrategyNode`, `IfElseNode`, `WeightNode`, `FilterNode`, `AssetNode` |
| `moa_allocations/engine/strategy.py` | `Settings`, `RootNode` |
| `moa_allocations/exceptions.py` | `DSLValidationError`, `PriceDataError` |
| `ARCHITECTURE.md` | Rename `security.py` reference; update node hierarchy diagram |
| `PRODUCT.md` | Rename `SecurityNode` → `AssetNode` in C1 description |
| `openspec/changes/Starting_points/compiler.spec.md` | Rename `SecurityNode` → `AssetNode` |
| `openspec/changes/Starting_points/engine.spec.md` | Rename `SecurityNode` → `AssetNode` |

## Decisions

### D1 — Typed StrategyNode subclasses

`StrategyNode` is subclassed by block type: `IfElseNode`, `WeightNode`, `FilterNode`.

Each block type has structurally distinct attributes (`conditions` vs `children` vs `sort_by`). Subclassing keeps each class's contract clear and makes adding new block types additive — a new block type is a new subclass, not more nullable fields on a shared class.

Rejected: single `StrategyNode` with `node_type: str` and optional fields — grows into attribute soup as block types accumulate.

### D2 — AssetNode lives in node.py

`AssetNode` is a node. It belongs with the other nodes in `node.py`. A separate `asset.py` is not created in this change — that split can happen later if `AssetNode` grows engine-specific behavior.

### D3 — Rename SecurityNode → AssetNode

`SecurityNode` renamed to `AssetNode` throughout. The DSL uses `"type": "asset"` — keeping the same vocabulary in code eliminates a translation step with no benefit. All doc and spec references updated as tasks in this change.

## Depends On

Nothing — this is the foundation for all other changes.
