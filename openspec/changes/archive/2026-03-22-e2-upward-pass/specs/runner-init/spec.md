## MODIFIED Requirements

### Requirement: Price series pre-conversion to numpy arrays

`Runner.__init__` SHALL convert each required ticker's price column from `price_data` to a `np.ndarray` and store it in `node.perm["child_series"]` for each `StrategyNode` that has children. The key SHALL be the child's `id` and the value SHALL be the numpy array of that child's price series (for `AssetNode` children) or a placeholder for NAV series (for `StrategyNode` children).

Additionally, `Runner.__init__` SHALL pre-allocate `perm['nav_array'] = np.ones(T, dtype=np.float64)` for each `StrategyNode` in the tree, where `T = len(_sim_dates)`. For each parent that has a `StrategyNode` child, the parent's `perm['child_series'][child.id]` SHALL be initialised to `child.perm['nav_array'][:1]` (a view of the first element only, representing NAV = 1.0 on day 0).

#### Scenario: AssetNode child series populated
- **WHEN** a `WeightNode` has an `AssetNode` child with ticker `"SPY"`
- **THEN** after init, the `WeightNode`'s `perm["child_series"]["<child_id>"]` SHALL be a `np.ndarray` equal to `price_data["SPY"].to_numpy()`

#### Scenario: StrategyNode child series initialised with NAV view
- **WHEN** a `WeightNode` has a `StrategyNode` child (sub-strategy)
- **THEN** after init, the parent's `perm["child_series"]["<child_id>"]` SHALL be a numpy view of `child.perm['nav_array'][:1]` containing `[1.0]`

#### Scenario: IfElseNode child series for condition assets
- **WHEN** an `IfElseNode` has conditions referencing ticker assets (via `lhs.asset` or `rhs.asset`)
- **THEN** after init, the `IfElseNode`'s `perm["child_series"]` SHALL include numpy arrays for those condition-referenced assets keyed by the asset identifier

#### Scenario: NAV array pre-allocated for all StrategyNodes
- **WHEN** the tree contains `StrategyNode` instances and `_sim_dates` has 252 entries
- **THEN** each `StrategyNode` SHALL have `perm['nav_array']` as a `np.ndarray` of shape `(252,)` initialised to `1.0`

---

## ADDED Requirements

### Requirement: Simulation date range and price offset computed at init

`Runner.__init__` SHALL compute and store:
- `_sim_dates`: `price_data.index` filtered to `[start_date, end_date]` (inclusive on both ends)
- `_price_offset`: the integer index position of `start_date` within `price_data.index`

These SHALL be used by the simulation loop to iterate over trading days and translate `t_idx` to positions in full price arrays.

#### Scenario: Price data with lookback period before start_date
- **WHEN** `price_data.index` spans 2023-06-01 to 2024-12-31 and `start_date` is 2024-01-02
- **THEN** `_sim_dates` SHALL contain only dates in [2024-01-02, end_date] and `_price_offset` SHALL equal the index of 2024-01-02 in `price_data.index`

#### Scenario: start_date is first date in price_data (no lookback needed)
- **WHEN** `max_lookback == 0` and `price_data.index[0]` equals `start_date`
- **THEN** `_price_offset` SHALL be `0`

---

### Requirement: Bottom-up traversal order computed at init

`Runner.__init__` SHALL compute `_upward_order` — a list of all `StrategyNode` instances sorted by tree depth descending (deepest first). This SHALL be computed via BFS during the existing tree traversal pass. `AssetNode` leaves SHALL be excluded.

#### Scenario: Traversal order stored on Runner
- **WHEN** `Runner.__init__` completes
- **THEN** `self._upward_order` SHALL be a `list[StrategyNode]` sorted deepest-first, reusable for every simulation day
