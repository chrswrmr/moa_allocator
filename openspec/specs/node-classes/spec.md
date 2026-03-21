# Spec: Node Classes

**Module:** `moa_allocations/engine/node.py`, `moa_allocations/engine/strategy.py`, `moa_allocations/exceptions.py`
**Version:** 1.0.0

**Purpose:** Defines the pure data structure foundation for the Strategy Tree — all node classes, the Settings dataclass, RootNode, and exception types. No parsing, validation, or simulation logic.

---

## Requirements

### Requirement: BaseNode defines shared identity attributes
Every node in the Strategy Tree SHALL inherit from `BaseNode`. `BaseNode` SHALL carry `id: str` and `name: str | None` — the only attributes shared across all node types regardless of role.

#### Scenario: BaseNode has id and name
- **WHEN** a `BaseNode` instance is created with an `id` and optional `name`
- **THEN** `node.id` returns the given id string and `node.name` returns the name or `None`

---

### Requirement: StrategyNode extends BaseNode with engine state
`StrategyNode` SHALL extend `BaseNode` and carry the shared engine state for all branch nodes: `temp: dict`, `perm: dict`, `algo_stack: list`. These SHALL be initialised as empty containers — never shared mutable defaults.

#### Scenario: StrategyNode initialises with empty state
- **WHEN** a `StrategyNode` subclass is instantiated
- **THEN** `node.temp`, `node.perm`, and `node.algo_stack` are each independent empty containers (not shared references)

---

### Requirement: IfElseNode holds conditional routing attributes
`IfElseNode` SHALL extend `StrategyNode` and carry: `logic_mode: str` (`"all"` or `"any"`), `conditions: list`, `true_branch: StrategyNode | AssetNode`, `false_branch: StrategyNode | AssetNode`.

#### Scenario: IfElseNode holds both branches
- **WHEN** an `IfElseNode` is instantiated with `logic_mode`, `conditions`, `true_branch`, and `false_branch`
- **THEN** all four attributes are accessible on the instance

---

### Requirement: WeightNode holds weighting attributes
`WeightNode` SHALL extend `StrategyNode` and carry: `method: str` (`"equal"`, `"defined"`, or `"inverse_volatility"`), `method_params: dict`, `children: list[StrategyNode | AssetNode]`.

#### Scenario: WeightNode holds method and children
- **WHEN** a `WeightNode` is instantiated with `method`, `method_params`, and `children`
- **THEN** all three attributes are accessible on the instance

---

### Requirement: FilterNode holds filter and ranking attributes
`FilterNode` SHALL extend `StrategyNode` and carry: `sort_by: dict`, `select: dict`, `children: list[StrategyNode | AssetNode]`.

#### Scenario: FilterNode holds sort_by, select, and children
- **WHEN** a `FilterNode` is instantiated with `sort_by`, `select`, and `children`
- **THEN** all three attributes are accessible on the instance

---

### Requirement: AssetNode is a leaf node holding a ticker
`AssetNode` SHALL extend `BaseNode` (not `StrategyNode`) and carry `ticker: str`. It SHALL have no `temp`, `perm`, `algo_stack`, or children attributes.

#### Scenario: AssetNode holds ticker only
- **WHEN** an `AssetNode` is instantiated with `id` and `ticker`
- **THEN** `node.ticker` returns the ticker string and the node has no `algo_stack` or `temp`

---

### Requirement: Settings holds all compiled strategy settings
`Settings` SHALL be a dataclass with the following fields populated from the DSL `settings` block:

| Field | Type |
|---|---|
| `id` | `str` |
| `name` | `str` |
| `starting_cash` | `float` |
| `start_date` | `date` |
| `end_date` | `date` |
| `slippage` | `float` |
| `fees` | `float` |
| `rebalance_frequency` | `str` |
| `rebalance_threshold` | `float | None` |

#### Scenario: Settings holds all fields
- **WHEN** a `Settings` instance is created with all required fields
- **THEN** every field is accessible by attribute name

---

### Requirement: RootNode holds compiled strategy entry point and metadata
`RootNode` SHALL carry: `settings: Settings`, `root: StrategyNode | AssetNode`, `dsl_version: str`. It SHALL NOT extend `StrategyNode` or `BaseNode` — it is a container, not a traversable node.

#### Scenario: RootNode holds settings, root, and dsl_version
- **WHEN** a `RootNode` is instantiated with `settings`, `root`, and `dsl_version`
- **THEN** all three attributes are accessible on the instance

#### Scenario: RootNode is not a node subclass
- **WHEN** `isinstance(root_node, BaseNode)` is evaluated
- **THEN** it returns `False`

---

### Requirement: DSLValidationError carries node context
`DSLValidationError` SHALL extend `Exception` and accept `node_id: str`, `node_name: str`, `message: str` as constructor arguments. All three SHALL be accessible as attributes.

#### Scenario: DSLValidationError stores all fields
- **WHEN** `DSLValidationError("abc123", "My Node", "weights do not sum to 1.0")` is raised and caught
- **THEN** `err.node_id`, `err.node_name`, and `err.message` return the respective values

---

### Requirement: PriceDataError carries a message
`PriceDataError` SHALL extend `Exception` and accept `message: str` as its sole constructor argument.

#### Scenario: PriceDataError stores message
- **WHEN** `PriceDataError("ticker SPY missing from price_data")` is raised and caught
- **THEN** `err.message` returns the given string
