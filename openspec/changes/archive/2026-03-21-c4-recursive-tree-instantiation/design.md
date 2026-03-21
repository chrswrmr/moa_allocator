## Context

`compile_strategy()` currently handles steps 1–3 (load JSON, schema validation, semantic validation) and then raises `NotImplementedError`. The C1 node class hierarchy (`IfElseNode`, `WeightNode`, `FilterNode`, `AssetNode`, `RootNode`, `Settings`) is already defined in `moa_allocations/engine/`. This change completes steps 4–5: recursively instantiate the validated dict into live node objects and return a `RootNode`.

The compiler already guarantees that any dict reaching step 4 is structurally and semantically valid. The instantiation code can therefore trust the shape of the data and focus on two transformations: (a) mapping dict types to node classes, and (b) converting `time_offset` strings to integer trading days.

## Goals / Non-Goals

**Goals:**
- Replace the `NotImplementedError` stub with recursive tree instantiation and `RootNode` assembly.
- Convert all `time_offset` strings (`lookback`, `duration`) to integer trading days during instantiation so downstream code never sees raw strings.
- Build a `Settings` dataclass with defaults applied for optional fields.
- Maintain the all-or-nothing guarantee: any error raises `DSLValidationError`, never a partial tree.

**Non-Goals:**
- AlgoStack attachment — that belongs to E1 (`Runner.__init__()`), per architecture boundaries.
- Modifying the C1 node classes or the `Settings` dataclass.
- Modifying the DSL schema or semantic validation logic.
- Ticker or price-data validation — that's a runtime concern for the engine.

## Decisions

### D1: Single `_build_node(raw)` recursive dispatcher

A single private function takes a node dict and dispatches on `raw["type"]` to instantiate the correct class. For container types (`weight`, `filter`, `if_else`), it recurses into children/branches before constructing the parent. This keeps instantiation in one place rather than spreading across per-type factory methods.

**Alternative considered:** Per-type factory classes. Rejected — four node types with fixed shapes don't warrant the indirection. A single dispatcher with a type→handler mapping is simpler and easier to audit.

### D2: `_convert_lookback(time_offset: str) -> int` pure function

A standalone helper that parses the `^[0-9]+[dwm]$` pattern and returns integer trading days using fixed multipliers: `d=1`, `w=5`, `m=21`. Called in-place wherever a `lookback` or `duration` field appears (condition metrics, sortMetric, method_params for inverse_volatility).

The converted integer replaces the string in the dict/object so downstream consumers always see `int`. This is applied during `_build_node` — lookback conversion happens at the same time as node construction, in a single pass.

**Alternative considered:** Separate pre-processing pass over the raw dict before instantiation. Rejected — it would require a second recursive walk and couples the conversion to dict structure rather than to the node being built.

### D3: `_build_settings(raw: dict) -> Settings` helper

Constructs the `Settings` dataclass from the raw `settings` dict, applying defaults (`slippage=0.0005`, `fees=0.0`, `rebalance_threshold=None`) and converting date strings to `date` objects. Kept separate from `_build_node` because settings are not a node — they're a flat dataclass attached to `RootNode`.

### D4: Compiler imports from `engine/` only for node classes

The compiler imports `IfElseNode`, `WeightNode`, `FilterNode`, `AssetNode` from `engine.node` and `RootNode`, `Settings` from `engine.strategy`. This is a one-way dependency (compiler → engine types) that does not violate the architecture boundary — the compiler never imports engine *logic*, only the data classes it instantiates. The engine never imports from compiler.

### D5: Lookback stored as `int` directly in node dicts/attributes

`IfElseNode.conditions` remains `list[dict]` — but each condition dict's `lhs.lookback`, `rhs.lookback`, and `duration` values are replaced with integers during construction. Similarly, `FilterNode.sort_by["lookback"]` and `WeightNode.method_params["lookback"]` are converted in-place. No new wrapper types are introduced.

**Alternative considered:** A `Lookback` named tuple or dataclass. Rejected — adds a type for a single integer value. The conversion is well-defined and the int is self-documenting given the spec's "trading days" contract.

## Risks / Trade-offs

**[Risk] Node class constructors change in a later change** → The compiler is tightly coupled to constructor signatures. Mitigation: C1 classes are stable and owned by this project; any signature change would require updating the compiler anyway, and tests will catch mismatches immediately.

**[Risk] Lookback multipliers (d=1, w=5, m=21) are hardcoded** → If the multiplier convention changes, updates are needed in one place (`_convert_lookback`). Mitigation: The spec defines these as fixed constants for v1. A constants module is unnecessary for three values in one function.

**[Trade-off] Mutating condition/sort_by dicts during construction** → We modify the validated dicts in-place rather than deep-copying. This is acceptable because `compile_strategy` owns the parsed dict — it's never reused. Avoids the cost and complexity of deep-copy.
