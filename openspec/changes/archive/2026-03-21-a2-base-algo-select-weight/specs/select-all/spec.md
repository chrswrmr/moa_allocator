## ADDED Requirements

### Requirement: SelectAll selects all children
`SelectAll` SHALL be a concrete subclass of `BaseAlgo` in `moa_allocations/engine/algos/selection.py`. It SHALL write all child node ids to `target.temp['selected']`.

#### Scenario: Weight node with multiple children
- **WHEN** `SelectAll.__call__` is invoked on a `WeightNode` target with 3 children (ids: `"a"`, `"b"`, `"c"`)
- **THEN** `target.temp['selected']` SHALL equal `["a", "b", "c"]` and the return value SHALL be `True`

#### Scenario: Weight node with single child
- **WHEN** `SelectAll.__call__` is invoked on a target with 1 child (id: `"only"`)
- **THEN** `target.temp['selected']` SHALL equal `["only"]` and the return value SHALL be `True`

#### Scenario: Filter node with multiple children
- **WHEN** `SelectAll.__call__` is invoked on a `FilterNode` target with children
- **THEN** `target.temp['selected']` SHALL contain all child ids and the return value SHALL be `True`

### Requirement: SelectAll never halts
`SelectAll` SHALL always return `True`. It SHALL NOT return `False` under any circumstance — all children are guaranteed valid by the compiler and data contracts.

#### Scenario: Always returns True
- **WHEN** `SelectAll.__call__` is invoked on any valid node with children
- **THEN** the return value SHALL be `True`

### Requirement: SelectAll has no parameters
`SelectAll` SHALL require no `__init__` arguments beyond what `BaseAlgo` provides.

#### Scenario: Zero-config instantiation
- **WHEN** `SelectAll()` is instantiated with no arguments
- **THEN** instantiation SHALL succeed

### Requirement: SelectAll public export
`SelectAll` SHALL be exported from `moa_allocations.engine.algos` via `__init__.py`.

#### Scenario: Import from package
- **WHEN** a consumer writes `from moa_allocations.engine.algos import SelectAll`
- **THEN** the import SHALL resolve to the `SelectAll` class from `selection.py`
