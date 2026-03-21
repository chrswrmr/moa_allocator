## Why

The compiler currently parses, schema-validates, and semantically validates a `.moastrat.json` file — but stops short of building the live node tree. Steps 4–5 of `compile_strategy()` raise `NotImplementedError`. Until the compiler can return a fully linked `RootNode`, the engine has nothing to run. This is the last compiler milestone before the engine work (E1) can begin.

## What Changes

- Complete `compile_strategy()` by implementing recursive tree instantiation (step 4) and `RootNode` assembly (step 5), replacing the current `NotImplementedError` stub.
- Add a `_build_node()` helper that recursively walks the `root_node` dict and instantiates the C1 node classes (`IfElseNode`, `WeightNode`, `FilterNode`, `AssetNode`).
- Add a `_convert_lookback()` helper that converts `time_offset` strings (`"200d"`, `"4w"`, `"3m"`) to integer trading days using the multipliers `d×1`, `w×5`, `m×21`. Apply this to every `lookback` and `duration` field on `Condition` and `sortMetric` objects during instantiation.
- Build a `Settings` dataclass from the `settings` block with defaults applied (`slippage=0.0005`, `fees=0.0`).
- Export `compile_strategy` from `compiler/__init__.py` (already done — verify it stays intact).
- Any error during tree construction raises `DSLValidationError` — never return a partial tree.

## Capabilities

### New Capabilities
- `tree-instantiation`: Recursive conversion of validated DSL dict into the C1 node class hierarchy, including lookback-to-trading-days conversion and Settings construction.

### Modified Capabilities
_(none — no existing spec requirements are changing)_

## Impact

- **Files changed:** `moa_allocations/compiler/compiler.py` (complete rewrite of steps 4–5), `moa_allocations/compiler/__init__.py` (verify export).
- **Dependencies:** C1 node classes in `moa_allocations/engine/node.py` and `moa_allocations/engine/strategy.py` — consumed but not modified.
- **Downstream:** Unblocks E1 (AlgoStack attachment / engine runner). After this change, `compile_strategy()` returns a usable `RootNode` for the first time.
- **No breaking changes** — the public interface (`compile_strategy(path) -> RootNode`) was already declared; this change fulfills it.
