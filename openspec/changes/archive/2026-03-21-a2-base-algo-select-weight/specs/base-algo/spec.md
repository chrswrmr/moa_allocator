## ADDED Requirements

### Requirement: BaseAlgo abstract class
`BaseAlgo` SHALL be an abstract base class (using `abc.ABC`) in `moa_allocations/engine/algos/base.py`. It SHALL define the Algo contract that all concrete Algos MUST follow.

#### Scenario: Abstract __call__ enforced at instantiation
- **WHEN** a subclass of `BaseAlgo` does not implement `__call__`
- **THEN** instantiating that subclass SHALL raise `TypeError`

#### Scenario: __call__ signature
- **WHEN** a concrete Algo's `__call__` is invoked
- **THEN** it SHALL accept exactly one positional argument `target` (a `StrategyNode`) and return a `bool`

### Requirement: BaseAlgo __init__ accepts keyword parameters
`BaseAlgo.__init__` SHALL accept `**params` and store them for use by subclasses. This allows compile-time parameters to be passed when constructing Algos.

#### Scenario: Subclass with no parameters
- **WHEN** a subclass like `SelectAll` is instantiated with no arguments
- **THEN** instantiation SHALL succeed with no stored parameters

#### Scenario: Subclass with compile-time parameters
- **WHEN** a subclass is instantiated with keyword arguments (e.g., `lookback=20`)
- **THEN** those parameters SHALL be stored and accessible within `__call__`

### Requirement: Algo statelessness
Algos SHALL be stateless beyond what is passed via `target`. An Algo instance MUST NOT access global state, parent/sibling/grandparent nodes, or perform DataFrame operations.

#### Scenario: No global state access
- **WHEN** an Algo's `__call__` executes
- **THEN** it SHALL only read from and write to `target.temp` and `target.perm`, and read from `target.children` or other attributes of `target` itself

### Requirement: Return value semantics
An Algo's `__call__` SHALL return `True` to proceed to the next Algo in the stack, or `False` to halt the stack (causing the engine to default the node to 100% XCASHX).

#### Scenario: Return True continues stack
- **WHEN** an Algo returns `True`
- **THEN** the engine SHALL proceed to the next Algo in the AlgoStack

#### Scenario: Return False halts stack
- **WHEN** an Algo returns `False`
- **THEN** the engine SHALL stop executing the AlgoStack and default the node to 100% XCASHX

### Requirement: Public export
`BaseAlgo` SHALL be exported from `moa_allocations.engine.algos` via `__init__.py`.

#### Scenario: Import from package
- **WHEN** a consumer writes `from moa_allocations.engine.algos import BaseAlgo`
- **THEN** the import SHALL resolve to the `BaseAlgo` class from `base.py`
