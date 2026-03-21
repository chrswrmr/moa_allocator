# weight-specified

**Module:** `moa_allocations/engine/algos/weighting.py`

Weighting algo for `weight` nodes with `method: "defined"`. Assigns pre-validated custom weights from a compiler-provided dict directly to `target.temp['weights']`.

---

## Requirements

### Requirement: WeightSpecified assigns custom weights directly

`WeightSpecified` SHALL accept a `custom_weights` dict (`{node_id: float}`) at init time. On `__call__`, it SHALL write a copy of `custom_weights` to `target.temp['weights']` and SHALL always return `True`. No runtime validation of weight sums is performed — the compiler guarantees weights sum to `1.0`.

#### Scenario: Normal assignment with two children

- **WHEN** `custom_weights` is `{"A": 0.7, "B": 0.3}` and `__call__` is invoked
- **THEN** `target.temp['weights']` SHALL equal `{"A": 0.7, "B": 0.3}` and the algo SHALL return `True`

#### Scenario: Single child with weight 1.0

- **WHEN** `custom_weights` is `{"A": 1.0}` and `__call__` is invoked
- **THEN** `target.temp['weights']` SHALL equal `{"A": 1.0}` and the algo SHALL return `True`

#### Scenario: Multiple children with unequal weights

- **WHEN** `custom_weights` is `{"A": 0.5, "B": 0.3, "C": 0.2}` and `__call__` is invoked
- **THEN** `target.temp['weights']` SHALL equal `{"A": 0.5, "B": 0.3, "C": 0.2}` and the algo SHALL return `True`

### Requirement: WeightSpecified never halts the stack

`WeightSpecified` SHALL always return `True`. It SHALL NOT inspect or validate the contents of `custom_weights` at runtime.

#### Scenario: Return value is always True

- **WHEN** `__call__` is invoked with any valid `custom_weights`
- **THEN** the algo SHALL return `True`
