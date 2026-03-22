## Purpose

Defines the construction contract for `Runner` — the engine entry point that wires a compiled Strategy Tree to its AlgoStacks, pre-computes price series as numpy arrays, and validates the price data before the simulation loop begins.

**Module:** `moa_allocations/engine/runner.py`
**Introduced:** e1-runner-init

---

## Requirements

### Requirement: Runner construction accepts RootNode and price DataFrame

`Runner.__init__(root: RootNode, price_data: pd.DataFrame)` SHALL accept a compiled `RootNode` and a `pd.DataFrame` of price data. The constructor SHALL store `root` and `price_data` as instance attributes, extract `settings` from `root.settings`, and prepare the tree for simulation.

#### Scenario: Successful Runner construction
- **WHEN** `Runner` is instantiated with a valid `RootNode` and a `price_data` DataFrame covering all required tickers and date range
- **THEN** the instance SHALL have `self.root`, `self.price_data`, and `self.settings` attributes set

#### Scenario: Runner is importable from engine package
- **WHEN** a caller imports `from moa_allocations.engine import Runner`
- **THEN** the import SHALL succeed and `Runner` SHALL be the class from `moa_allocations.engine.runner`

---

### Requirement: AlgoStack attachment via tree traversal

`Runner.__init__` SHALL traverse the entire compiled tree and attach an `algo_stack` list to each `StrategyNode` based on its concrete class and parameters. `AssetNode` leaves SHALL NOT receive an AlgoStack.

The mapping SHALL be:

| Node class | Method/Mode | AlgoStack |
|---|---|---|
| `WeightNode` | `equal` | `[SelectAll(), WeightEqually()]` |
| `WeightNode` | `defined` | `[SelectAll(), WeightSpecified(custom_weights)]` |
| `WeightNode` | `inverse_volatility` | `[SelectAll(), WeightInvVol(lookback)]` |
| `FilterNode` | `select.mode == "top"` | `[SelectTopN(n, metric, lookback), WeightEqually()]` |
| `FilterNode` | `select.mode == "bottom"` | `[SelectBottomN(n, metric, lookback), WeightEqually()]` |
| `IfElseNode` | — | `[SelectIfCondition(conditions, logic_mode), WeightEqually()]` |

#### Scenario: WeightNode with equal method
- **WHEN** the tree contains a `WeightNode` with `method == "equal"`
- **THEN** that node's `algo_stack` SHALL be `[SelectAll(), WeightEqually()]`

#### Scenario: WeightNode with defined method
- **WHEN** the tree contains a `WeightNode` with `method == "defined"` and `method_params["weights"]` is `{"child_a": 0.6, "child_b": 0.4}`
- **THEN** that node's `algo_stack` SHALL be `[SelectAll(), WeightSpecified({"child_a": 0.6, "child_b": 0.4})]`

#### Scenario: WeightNode with inverse_volatility method
- **WHEN** the tree contains a `WeightNode` with `method == "inverse_volatility"` and `method_params["lookback"]` is `60`
- **THEN** that node's `algo_stack` SHALL be `[SelectAll(), WeightInvVol(60)]`

#### Scenario: FilterNode with top mode
- **WHEN** the tree contains a `FilterNode` with `select == {"mode": "top", "count": 3}` and `sort_by == {"function": "cumulative_return", "lookback": 20}`
- **THEN** that node's `algo_stack` SHALL be `[SelectTopN(3, "cumulative_return", 20), WeightEqually()]`

#### Scenario: FilterNode with bottom mode
- **WHEN** the tree contains a `FilterNode` with `select == {"mode": "bottom", "count": 2}` and `sort_by == {"function": "std_dev_return", "lookback": 60}`
- **THEN** that node's `algo_stack` SHALL be `[SelectBottomN(2, "std_dev_return", 60), WeightEqually()]`

#### Scenario: IfElseNode
- **WHEN** the tree contains an `IfElseNode` with `conditions` list and `logic_mode == "all"`
- **THEN** that node's `algo_stack` SHALL be `[SelectIfCondition(conditions, "all"), WeightEqually()]`

#### Scenario: AssetNode receives no AlgoStack
- **WHEN** the tree contains an `AssetNode` leaf
- **THEN** that node SHALL NOT have an `algo_stack` attribute set by Runner (it has no `algo_stack` attribute or its existing empty list is unchanged)

---

### Requirement: Price series pre-conversion to numpy arrays

`Runner.__init__` SHALL convert each required ticker's price column from `price_data` to a `np.ndarray` and store it in `node.perm["child_series"]` for each `StrategyNode` that has children. The key SHALL be the child's `id` and the value SHALL be the numpy array of that child's price series (for `AssetNode` children) or a placeholder for NAV series (for `StrategyNode` children).

#### Scenario: AssetNode child series populated
- **WHEN** a `WeightNode` has an `AssetNode` child with ticker `"SPY"`
- **THEN** after init, the `WeightNode`'s `perm["child_series"]["<child_id>"]` SHALL be a `np.ndarray` equal to `price_data["SPY"].to_numpy()`

#### Scenario: StrategyNode child series placeholder
- **WHEN** a `WeightNode` has a `StrategyNode` child (sub-strategy)
- **THEN** after init, the parent's `perm["child_series"]["<child_id>"]` SHALL contain a placeholder (empty `np.ndarray`) that the simulation loop will later populate with the child's NAV series

#### Scenario: IfElseNode child series for condition assets
- **WHEN** an `IfElseNode` has conditions referencing ticker assets (via `lhs.asset` or `rhs.asset`)
- **THEN** after init, the `IfElseNode`'s `perm["child_series"]` SHALL include numpy arrays for those condition-referenced assets keyed by the asset identifier

---

### Requirement: Max lookback computation

`Runner.__init__` SHALL compute the maximum lookback across the entire tree by examining all lookback parameters from `FilterNode.sort_by["lookback"]`, `WeightNode.method_params["lookback"]` (for inverse_volatility), and all condition lookbacks from `IfElseNode.conditions`. This value SHALL be stored as `self.max_lookback` and used for date range validation.

#### Scenario: Max lookback from mixed node types
- **WHEN** the tree contains a `FilterNode` with `sort_by["lookback"] == 20`, a `WeightNode` (inverse_volatility) with `method_params["lookback"] == 60`, and an `IfElseNode` with a condition `lhs.lookback == 200`
- **THEN** `self.max_lookback` SHALL be `200`

#### Scenario: Tree with no lookback parameters
- **WHEN** the tree contains only `WeightNode` nodes with `method == "equal"`
- **THEN** `self.max_lookback` SHALL be `0`

---

### Requirement: Ticker collection from tree

`Runner.__init__` SHALL collect all unique tickers from `AssetNode` leaves and from `IfElseNode` condition references (`lhs.asset`, `rhs.asset` when rhs is a dict). This complete ticker set SHALL be used for price data validation.

#### Scenario: Tickers from asset leaves
- **WHEN** the tree has `AssetNode` leaves with tickers `["SPY", "BND", "GLD"]`
- **THEN** the collected ticker set SHALL include `"SPY"`, `"BND"`, and `"GLD"`

#### Scenario: Tickers from if_else condition references
- **WHEN** an `IfElseNode` has a condition with `lhs.asset == "VIX"` and `rhs` is a dict with `rhs.asset == "TLT"`
- **THEN** the collected ticker set SHALL include `"VIX"` and `"TLT"` (in addition to any leaf tickers)
