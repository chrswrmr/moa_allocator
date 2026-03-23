# tree-instantiation

**Module:** `moa_allocations/compiler/`
**Purpose:** Recursive conversion of a validated DSL dict into the C1 node class hierarchy, including lookback-to-trading-days conversion and Settings construction.

---

## Requirements

### Requirement: Recursive node instantiation
`compile_strategy()` SHALL recursively walk the validated `root_node` dict and instantiate the corresponding C1 node class for each node based on its `type` field:
- `"if_else"` → `IfElseNode`
- `"weight"` → `WeightNode`
- `"filter"` → `FilterNode`
- `"asset"` → `AssetNode`

Container nodes (`if_else`, `weight`, `filter`) SHALL have their children/branches fully instantiated before the parent is constructed (depth-first, bottom-up). The function SHALL never return a partially built tree — any instantiation error MUST raise `DSLValidationError`.

#### Scenario: Weight node with mixed children
- **WHEN** `root_node` is a `weight` node with two children: one `asset` and one nested `weight`
- **THEN** the compiler returns a `WeightNode` whose `children` list contains an `AssetNode` and a `WeightNode`, both fully instantiated

#### Scenario: If/else node with branches
- **WHEN** `root_node` is an `if_else` node with `true_branch` as a `weight` node and `false_branch` as an `asset` node
- **THEN** the compiler returns an `IfElseNode` with `true_branch` as a `WeightNode` and `false_branch` as an `AssetNode`

#### Scenario: Deeply nested tree
- **WHEN** the DSL contains a `filter` → `weight` → `asset` chain three levels deep
- **THEN** all three levels are instantiated as `FilterNode` → `WeightNode` → `AssetNode` with correct parent-child linkage

#### Scenario: Unknown node type in validated dict
- **WHEN** a node dict contains an unrecognized `type` value (defensive — schema should prevent this)
- **THEN** the compiler raises `DSLValidationError` with the node's `id` and a message identifying the unknown type

---

### Requirement: Lookback conversion to trading days
The compiler SHALL convert every `time_offset` string (matching `^[0-9]+d$`) to an integer number of trading days using the multiplier `d=1`. This conversion MUST be applied to:
- `lookback` on condition metric objects (`lhs`, `rhs`) in `if_else` conditions
- `duration` on condition objects in `if_else` conditions
- `lookback` on `sortMetric` objects in `filter` nodes
- `lookback` in `method_params` for `inverse_volatility` weight nodes

The `w` (week) and `m` (month) unit suffixes are removed. Only `d` (day) is accepted. Strategies using `w` or `m` SHALL fail with `DSLValidationError`.

After instantiation, all these fields SHALL contain `int` values — never raw `time_offset` strings.

#### Scenario: Days conversion
- **WHEN** a condition metric has `lookback: "200d"`
- **THEN** the instantiated condition dict contains `lookback: 200`

#### Scenario: Invalid week suffix rejected
- **WHEN** a sortMetric has `lookback: "4w"`
- **THEN** `DSLValidationError` is raised with a message indicating invalid `time_offset` format

#### Scenario: Invalid month suffix rejected
- **WHEN** a condition has `duration: "3m"`
- **THEN** `DSLValidationError` is raised with a message indicating invalid `time_offset` format

#### Scenario: Inverse volatility lookback
- **WHEN** a weight node has `method: "inverse_volatility"` and `method_params.lookback: "126d"`
- **THEN** the instantiated `WeightNode.method_params["lookback"]` equals `126`

#### Scenario: Current price has no lookback
- **WHEN** a condition metric uses `function: "current_price"` with no `lookback` field
- **THEN** the instantiated condition metric has no `lookback` key (no conversion needed, no error)

#### Scenario: Default duration
- **WHEN** a condition object has no explicit `duration` field
- **THEN** the compiler applies the default `"1d"` and stores `duration: 1` on the instantiated condition

---

### Requirement: Settings construction
`compile_strategy()` SHALL build a `Settings` dataclass from the raw `settings` dict with the following rules:
- `start_date` and `end_date` SHALL be converted from ISO 8601 strings to `date` objects.
- `slippage` SHALL default to `0.0005` when absent.
- `fees` SHALL default to `0.0` when absent.
- `rebalance_threshold` SHALL default to `None` when absent.
- All required fields (`id`, `name`, `starting_cash`, `start_date`, `end_date`, `rebalance_frequency`) MUST be present (guaranteed by prior schema validation).

#### Scenario: All settings provided
- **WHEN** the settings dict includes all required and optional fields
- **THEN** the `Settings` dataclass is constructed with the provided values and dates as `date` objects

#### Scenario: Optional settings use defaults
- **WHEN** the settings dict omits `slippage`, `fees`, and `rebalance_threshold`
- **THEN** the `Settings` dataclass has `slippage=0.0005`, `fees=0.0`, `rebalance_threshold=None`

---

### Requirement: RootNode assembly
`compile_strategy()` SHALL return a `RootNode` containing:
- `settings`: the constructed `Settings` dataclass
- `root`: the recursively instantiated top-level node (a `StrategyNode` subclass or `AssetNode`)
- `dsl_version`: the `version-dsl` string from the document (`"1.0.0"`)

The `RootNode` SHALL only be returned after the entire tree is successfully instantiated. If any step fails, `DSLValidationError` MUST be raised — no partial `RootNode` is ever returned.

#### Scenario: Successful full compilation
- **WHEN** a valid `.moastrat.json` with a weight→asset tree is compiled
- **THEN** `compile_strategy()` returns a `RootNode` with populated `settings`, a `WeightNode` as `root`, and `dsl_version="1.0.0"`

#### Scenario: Instantiation failure prevents return
- **WHEN** tree instantiation fails (e.g., unknown node type)
- **THEN** `compile_strategy()` raises `DSLValidationError` and does not return a `RootNode`

---

### Requirement: Node attribute passthrough
Each instantiated node SHALL carry the attributes from the DSL dict into the corresponding class fields:
- `IfElseNode`: `logic_mode`, `conditions` (with converted lookbacks/durations), `true_branch`, `false_branch`
- `WeightNode`: `method`, `method_params` (with converted lookback if inverse_volatility), `children`
- `FilterNode`: `sort_by` (with converted lookback), `select`, `children`
- `AssetNode`: `ticker`
- All nodes: `id`, `name` (or `None` if absent)

#### Scenario: Weight node attributes
- **WHEN** a weight node dict has `method: "defined"`, `method_params: {"custom_weights": {...}}`, and two children
- **THEN** the `WeightNode` has `.method == "defined"`, `.method_params == {"weights": {...}}` (compiler normalises `custom_weights` → `weights`), and `.children` as a list of two instantiated nodes

#### Scenario: Asset node attributes
- **WHEN** an asset node dict has `id: "abc"`, `ticker: "SPY"`, and no `name`
- **THEN** the `AssetNode` has `.id == "abc"`, `.ticker == "SPY"`, `.name is None`

#### Scenario: Filter node sort_by converted
- **WHEN** a filter node has `sort_by: {"function": "rsi", "lookback": "14d"}`
- **THEN** the `FilterNode.sort_by` equals `{"function": "rsi", "lookback": 14}`
