# Design: Node Class Hierarchy

## Context

No code exists yet. This change lays down the pure data structure foundation that every other module (compiler, engine, algos) depends on. It creates three files: `engine/node.py`, `engine/strategy.py`, and `exceptions.py`.

The node hierarchy is specified in `compiler.spec.md` (Output: Node Class Hierarchy section) and the engine state model is specified in `engine.spec.md` (Node State section).

## Goals / Non-Goals

**Goals:**
- Define all node classes with correct attributes
- Define `Settings` dataclass
- Define both exception classes
- Rename `SecurityNode` → `AssetNode` throughout all docs and specs

**Non-Goals:**
- No parsing, validation, or instantiation logic
- No AlgoStack construction or attachment
- No engine simulation logic
- No `__init__.py` wiring (deferred to the module that uses these classes)

## Decisions

### D1 — Typed StrategyNode subclasses

`StrategyNode` is subclassed by block type: `IfElseNode`, `WeightNode`, `FilterNode`.

Each block type has structurally distinct attributes that don't overlap:

| Class | Unique attributes |
|---|---|
| `IfElseNode` | `conditions`, `logic_mode`, `true_branch`, `false_branch` |
| `WeightNode` | `method`, `method_params`, `children` |
| `FilterNode` | `sort_by`, `select`, `children` |

A single `StrategyNode` with optional fields would accumulate `None`s as new block types are added. Subclasses keep each class's contract explicit and make engine dispatch (`isinstance`) clean.

`StrategyNode` itself carries the shared engine state: `temp`, `perm`, `algo_stack`.

Rejected: single `StrategyNode(node_type: str)` with nullable fields.

### D2 — AssetNode lives in node.py

`AssetNode` is a node. It lives alongside the other node classes in `node.py`. No separate `asset.py` is created — that split is deferred until `AssetNode` grows engine-specific behavior.

### D3 — SecurityNode renamed to AssetNode

The DSL uses `"type": "asset"`. Matching the vocabulary in code eliminates an unnecessary translation. All references in docs and specs are updated as tasks in this change.

### D4 — version-dsl stored on RootNode

`RootNode` gets a `dsl_version: str` attribute populated from the top-level `version-dsl` field after validation. Stored for introspection and debugging — no part of the engine uses it at runtime, but it's available on any compiled tree.

Rejected: validate and discard — loses traceability once the tree is compiled.

### D5 — RootNode is not a StrategyNode subclass

`RootNode` is a container that holds `settings` + `root` (the compiled tree entry point). It is not itself a traversable node — the engine starts traversal at `root`, not at `RootNode`. Making it a `StrategyNode` subclass would imply it participates in the simulation loop, which it does not.

`RootNode` lives in `strategy.py` alongside `Settings`.

### D6 — BaseNode carries only identity fields

`BaseNode` holds only `id` and `name` — attributes shared by every node type regardless of role. Engine state (`temp`, `perm`, `algo_stack`) lives on `StrategyNode` only, since `AssetNode` (leaf) has no AlgoStack and no state dicts.

## Risks / Trade-offs

**Non-uniform child access** — `IfElseNode` exposes children as named attributes (`true_branch`, `false_branch`); `WeightNode` and `FilterNode` expose them as `children[]`. The engine cannot assume a uniform `.children` on all `StrategyNode` types. Mitigation: engine traversal checks `isinstance` and accesses the correct attribute per type — this is an expected consequence of D1 (typed subclasses), not a hidden edge case.

**Mutable defaults** — `temp`, `perm`, and `algo_stack` on `StrategyNode` must not use mutable defaults (e.g. `{}` or `[]`). Use `field(default_factory=...)` if dataclass, or explicit `__init__` assignment. Mitigation: enforce in implementation via code review / tests.
