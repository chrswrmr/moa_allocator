## 1. BaseAlgo

- [x] 1.1 Create `moa_allocations/engine/algos/base.py` with `BaseAlgo(ABC)` — abstract `__call__(self, target: StrategyNode) -> bool` and `__init__(self, **params)`
- [x] 1.2 Add `BaseAlgo` to `moa_allocations/engine/algos/__init__.py` exports

## 2. SelectAll

- [x] 2.1 Create `moa_allocations/engine/algos/selection.py` with `SelectAll(BaseAlgo)` — writes `[child.id for child in target.children]` to `target.temp['selected']`, returns `True`
- [x] 2.2 Add `SelectAll` to `moa_allocations/engine/algos/__init__.py` exports

## 3. WeightEqually

- [x] 3.1 Create `moa_allocations/engine/algos/weighting.py` with `WeightEqually(BaseAlgo)` — reads `target.temp['selected']`, writes `{id: 1/n}` to `target.temp['weights']`, returns `True`
- [x] 3.2 Add `WeightEqually` to `moa_allocations/engine/algos/__init__.py` exports

## 4. Tests

- [x] 4.1 Test `BaseAlgo` — subclass without `__call__` raises `TypeError` on instantiation
- [x] 4.2 Test `SelectAll` — multi-child node populates `temp['selected']` with all child ids and returns `True`
- [x] 4.3 Test `SelectAll` — single-child node returns list with one id
- [x] 4.4 Test `WeightEqually` — 3 selected children get `1/3` each, weights sum to `1.0`, returns `True`
- [x] 4.5 Test `WeightEqually` — single selected child gets `1.0`
- [x] 4.6 Run `uv run pytest` and verify all tests pass
