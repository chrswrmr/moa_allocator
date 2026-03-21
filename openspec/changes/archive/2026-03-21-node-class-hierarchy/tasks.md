## 1. Exceptions

- [x] 1.1 Create `moa_allocations/exceptions.py` with `DSLValidationError(node_id, node_name, message)` storing all three as attributes
- [x] 1.2 Add `PriceDataError(message)` to `exceptions.py` storing `message` as an attribute

## 2. Node Classes

- [x] 2.1 Create `moa_allocations/engine/node.py` with `BaseNode` holding `id: str` and `name: str | None`
- [x] 2.2 Add `StrategyNode(BaseNode)` with `temp: dict`, `perm: dict`, `algo_stack: list` — each initialised as independent empty containers (no shared mutable defaults)
- [x] 2.3 Add `IfElseNode(StrategyNode)` with `logic_mode: str`, `conditions: list`, `true_branch`, `false_branch`
- [x] 2.4 Add `WeightNode(StrategyNode)` with `method: str`, `method_params: dict`, `children: list`
- [x] 2.5 Add `FilterNode(StrategyNode)` with `sort_by: dict`, `select: dict`, `children: list`
- [x] 2.6 Add `AssetNode(BaseNode)` with `ticker: str` — no `temp`, `perm`, or `algo_stack`

## 3. Settings and RootNode

- [x] 3.1 Create `moa_allocations/engine/strategy.py` with `Settings` dataclass — fields: `id`, `name`, `starting_cash`, `start_date`, `end_date`, `slippage`, `fees`, `rebalance_frequency`, `rebalance_threshold`
- [x] 3.2 Add `RootNode` to `strategy.py` holding `settings: Settings`, `root: StrategyNode | AssetNode`, `dsl_version: str` — not a subclass of `BaseNode` or `StrategyNode`

## 4. Doc and Spec Updates

- [x] 4.1 Rename `SecurityNode` → `AssetNode` in `openspec/changes/Starting_points/compiler.spec.md` (3 occurrences)
- [x] 4.2 Rename `SecurityNode` → `AssetNode` in `openspec/changes/Starting_points/engine.spec.md` (1 occurrence)
- [x] 4.3 Rename `SecurityNode` → `AssetNode` and `security.py` → `asset.py` in `ARCHITECTURE.md`
- [x] 4.4 Rename `SecurityNode` → `AssetNode` in `PRODUCT.md` (2 occurrences)

## 5. Tests

- [x] 5.1 Create `tests/unit/test_node_classes.py` — one test per scenario in `specs/node-classes/spec.md`
