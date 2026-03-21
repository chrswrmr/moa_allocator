## 1. SelectIfCondition Implementation

- [x] 1.1 Add private `_evaluate_condition_at_day(target, condition, day_idx)` helper to `selection.py` — computes lhs metric, computes rhs (scalar or metric), checks NaN, applies comparator
- [x] 1.2 Implement `SelectIfCondition.__init__(conditions, logic_mode)` — store both params
- [x] 1.3 Implement `SelectIfCondition.__call__(target)` — iterate conditions, apply duration window clamping, call `_evaluate_condition_at_day` for each day, combine with `logic_mode`, write `true_branch.id` or `false_branch.id` to `target.temp['selected']`, always return `True`
- [x] 1.4 Export `SelectIfCondition` from `moa_allocations/engine/algos/__init__.py` (if applicable)

## 2. WeightSpecified Implementation

- [x] 2.1 Implement `WeightSpecified.__init__(custom_weights)` — store the `{node_id: float}` dict
- [x] 2.2 Implement `WeightSpecified.__call__(target)` — write `custom_weights` directly to `target.temp['weights']`, return `True`
- [x] 2.3 Export `WeightSpecified` from `moa_allocations/engine/algos/__init__.py` (if applicable)

## 3. Tests — SelectIfCondition

- [x] 3.1 Test single condition `duration=1`: condition met → `true_branch`, condition not met → `false_branch`
- [x] 3.2 Test single condition `duration=3`: all 3 days pass → `true_branch`; one day fails → `false_branch`
- [x] 3.3 Test duration window clamping: `duration=5` with only 2 days of history evaluates available days only
- [x] 3.4 Test NaN on lhs metric routes to `false_branch`
- [x] 3.5 Test NaN on rhs metric dict routes to `false_branch`
- [x] 3.6 Test `logic_mode="all"`: both conditions pass → `true_branch`; one fails → `false_branch`
- [x] 3.7 Test `logic_mode="any"`: one passes → `true_branch`; all fail → `false_branch`
- [x] 3.8 Test `"greater_than"` and `"less_than"` comparators including equal values
- [x] 3.9 Test rhs as metric dict (not scalar) — verify series lookup and metric computation

## 4. Tests — WeightSpecified

- [x] 4.1 Test two-child assignment: weights written to `target.temp['weights']` unchanged, returns `True`
- [x] 4.2 Test single-child assignment: `{"A": 1.0}` written correctly
- [x] 4.3 Test multi-child unequal weights: all keys/values preserved exactly

## 5. Verification

- [x] 5.1 Run `uv run pytest` — all tests pass with no regressions
