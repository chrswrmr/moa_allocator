## ADDED Requirements

### Requirement: WeightEqually distributes equal weights
`WeightEqually` SHALL be a concrete subclass of `BaseAlgo` in `moa_allocations/engine/algos/weighting.py`. It SHALL read `target.temp['selected']` and write equal weights to `target.temp['weights']`.

#### Scenario: Three selected children
- **WHEN** `WeightEqually.__call__` is invoked and `target.temp['selected']` is `["a", "b", "c"]`
- **THEN** `target.temp['weights']` SHALL equal `{"a": 1/3, "b": 1/3, "c": 1/3}` and the return value SHALL be `True`

#### Scenario: Single selected child
- **WHEN** `WeightEqually.__call__` is invoked and `target.temp['selected']` is `["only"]`
- **THEN** `target.temp['weights']` SHALL equal `{"only": 1.0}` and the return value SHALL be `True`

#### Scenario: Two selected children
- **WHEN** `WeightEqually.__call__` is invoked and `target.temp['selected']` is `["x", "y"]`
- **THEN** `target.temp['weights']` SHALL equal `{"x": 0.5, "y": 0.5}` and the return value SHALL be `True`

### Requirement: Weights sum to 1.0
The values in `target.temp['weights']` written by `WeightEqually` SHALL sum to `1.0` (within floating-point precision).

#### Scenario: Weight sum invariant
- **WHEN** `WeightEqually.__call__` completes on any non-empty selection
- **THEN** `sum(target.temp['weights'].values())` SHALL equal `1.0` (within floating-point tolerance)

### Requirement: WeightEqually never halts
`WeightEqually` SHALL always return `True`. The preceding selection Algo guarantees at least one child is selected before `WeightEqually` runs.

#### Scenario: Always returns True
- **WHEN** `WeightEqually.__call__` is invoked with a non-empty `target.temp['selected']`
- **THEN** the return value SHALL be `True`

### Requirement: WeightEqually has no parameters
`WeightEqually` SHALL require no `__init__` arguments beyond what `BaseAlgo` provides.

#### Scenario: Zero-config instantiation
- **WHEN** `WeightEqually()` is instantiated with no arguments
- **THEN** instantiation SHALL succeed

### Requirement: WeightEqually public export
`WeightEqually` SHALL be exported from `moa_allocations.engine.algos` via `__init__.py`.

#### Scenario: Import from package
- **WHEN** a consumer writes `from moa_allocations.engine.algos import WeightEqually`
- **THEN** the import SHALL resolve to the `WeightEqually` class from `weighting.py`
