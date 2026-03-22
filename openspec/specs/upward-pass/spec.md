## Purpose

Defines the bottom-up NAV computation that runs on every trading day, updating each StrategyNode's unitized NAV series from leaves to root. This enables parent Algos to evaluate metrics (SMA, RSI, etc.) over sub-strategy returns during the Downward Pass.

**Module:** `moa_allocations/engine/runner.py`
**Introduced:** e2-upward-pass

---

## Requirements

### Requirement: Bottom-up traversal order computed at init

`Runner.__init__` SHALL compute a bottom-up traversal order (`_upward_order`) by collecting all `StrategyNode` instances with their tree depth via BFS, then sorting by depth descending. `AssetNode` leaves SHALL be excluded — their returns come directly from price arrays. This order SHALL be reused on every simulation day.

#### Scenario: Simple two-level tree
- **WHEN** a `WeightNode` (depth 0) has three `AssetNode` children (depth 1)
- **THEN** `_upward_order` SHALL contain only the `WeightNode` (AssetNodes excluded)

#### Scenario: Nested tree with sub-strategies
- **WHEN** a `WeightNode` W1 (depth 0) has children `WeightNode` W2 (depth 1) and `AssetNode` A1, and W2 has children `AssetNode` A2 and `AssetNode` A3
- **THEN** `_upward_order` SHALL be `[W2, W1]` — deepest StrategyNode first

#### Scenario: IfElseNode with nested branches
- **WHEN** an `IfElseNode` IE (depth 0) has `true_branch` = `WeightNode` W1 (depth 1) and `false_branch` = `AssetNode` A1
- **THEN** `_upward_order` SHALL be `[W1, IE]` — W1 before IE because it is deeper

---

### Requirement: NAV array pre-allocation at init

`Runner.__init__` SHALL pre-allocate `perm['nav_array'] = np.ones(T, dtype=np.float64)` for each `StrategyNode` in the tree, where `T = len(sim_dates)`. The initial value of `1.0` represents the unitized NAV starting point.

#### Scenario: NAV array shape matches simulation length
- **WHEN** `sim_dates` has 252 trading days
- **THEN** each StrategyNode's `perm['nav_array']` SHALL be a `np.ndarray` of shape `(252,)` with all values initialised to `1.0`

---

### Requirement: Simulation date range computed at init

`Runner.__init__` SHALL compute `_sim_dates` by filtering `price_data.index` to the range `[start_date, end_date]` (inclusive). It SHALL also compute `_price_offset` as the integer index position of `start_date` within `price_data.index`, used to translate simulation day index (`t_idx`) to the corresponding position in full price arrays.

#### Scenario: Price data with lookback period
- **WHEN** `price_data.index` covers 2023-01-01 to 2024-12-31, `start_date` is 2024-01-02, and `end_date` is 2024-12-31
- **THEN** `_sim_dates` SHALL contain only dates from 2024-01-02 to 2024-12-31, and `_price_offset` SHALL be the index of 2024-01-02 in the full `price_data.index`

---

### Requirement: Runner.run() simulation loop skeleton

`Runner.run()` SHALL iterate over each trading day in `_sim_dates`. For each day at index `t_idx`:
1. If `t_idx > 0`: execute the Upward Pass
2. Determine if this is a rebalance day (delegated to rebalance-schedule capability)
3. If rebalance day: execute the Downward Pass (placeholder for E3)
4. After the Upward Pass: update `child_series` views for all StrategyNode children

Day 0 (`t_idx == 0`) SHALL skip the Upward Pass (NAV is already 1.0) and SHALL always execute the Downward Pass to establish initial weights.

#### Scenario: Loop iterates all simulation days
- **WHEN** `_sim_dates` has 252 entries
- **THEN** `run()` SHALL process exactly 252 days in order

#### Scenario: Day 0 skips upward pass
- **WHEN** the loop reaches `t_idx == 0`
- **THEN** the Upward Pass SHALL NOT execute, NAV SHALL remain at 1.0 for all nodes, and the Downward Pass SHALL execute

#### Scenario: Day 1+ runs upward pass before downward pass
- **WHEN** the loop reaches `t_idx > 0`
- **THEN** the Upward Pass SHALL complete fully before any Downward Pass decision is made (P4 — strict phase ordering)

---

### Requirement: Upward Pass NAV computation for WeightNode and FilterNode

For each `WeightNode` or `FilterNode` in `_upward_order` at `t_idx > 0`, the Upward Pass SHALL:
1. Read the node's `temp['weights']` from the prior day (set by the Downward Pass or carried forward)
2. For each child in `temp['weights']`, compute the child's daily return:
   - `AssetNode` child: `price[_price_offset + t_idx] / price[_price_offset + t_idx - 1] - 1` using the child's entry in `perm['child_series']`
   - `StrategyNode` child: `nav_array[t_idx] / nav_array[t_idx - 1] - 1` using the child's `perm['nav_array']` (already computed — bottom-up order guarantees this)
3. Compute `weighted_return = sum(weight[child] * child_return)` across all children in `temp['weights']`
4. Update `nav_array[t_idx] = nav_array[t_idx - 1] * (1 + weighted_return)`

#### Scenario: WeightNode with two AssetNode children
- **WHEN** a `WeightNode` has `temp['weights'] = {"A": 0.6, "B": 0.4}`, asset A returns +1% and asset B returns -0.5%
- **THEN** `weighted_return` SHALL be `0.6 * 0.01 + 0.4 * (-0.005) = 0.004` and `nav_array[t_idx]` SHALL be `nav_array[t_idx - 1] * 1.004`

#### Scenario: WeightNode with StrategyNode child
- **WHEN** a `WeightNode` has a child `StrategyNode` S1 with `nav_array = [..., 1.05, 1.08]` at t_idx
- **THEN** S1's return SHALL be `1.08 / 1.05 - 1 ≈ 0.02857` and this SHALL be used in the parent's weighted_return calculation

#### Scenario: Single child receives full weight
- **WHEN** a `WeightNode` has a single child with `temp['weights'] = {"A": 1.0}` and child A returns +2%
- **THEN** `weighted_return` SHALL be `0.02` and the node's NAV SHALL update accordingly

---

### Requirement: Upward Pass NAV computation for IfElseNode

For each `IfElseNode` in `_upward_order` at `t_idx > 0`, the Upward Pass SHALL:
1. Both branches (`true_branch` and `false_branch`) SHALL have their NAV already updated (they are deeper in the tree and processed first)
2. Read the node's `temp['weights']` to identify the active branch (the branch id with weight > 0)
3. Compute the active branch's daily return (same formula as for any child)
4. Update the if_else node's own `nav_array[t_idx] = nav_array[t_idx - 1] * (1 + active_branch_return)`

If no prior `temp['weights']` exists (day 0 case), NAV SHALL remain at 1.0.

#### Scenario: True branch is active
- **WHEN** an `IfElseNode` has `temp['weights'] = {"true_id": 1.0}` and the true branch returned +3%
- **THEN** the if_else node's own NAV SHALL update by `* 1.03`

#### Scenario: False branch is active
- **WHEN** an `IfElseNode` has `temp['weights'] = {"false_id": 1.0}` and the false branch returned -1%
- **THEN** the if_else node's own NAV SHALL update by `* 0.99`

#### Scenario: Both branches update NAV regardless of active branch
- **WHEN** the true branch is active (selected) and the false branch is inactive
- **THEN** both branches' `nav_array[t_idx]` SHALL be updated with their respective returns — the active branch selection only affects the *parent* if_else node's own NAV

---

### Requirement: child_series view update after Upward Pass

After the Upward Pass completes for day `t_idx`, the runner SHALL update `child_series` entries for every StrategyNode child. For each parent node that has a StrategyNode child, the parent's `perm['child_series'][child.id]` SHALL be set to `child.perm['nav_array'][:t_idx + 1]` (a numpy view, not a copy). This ensures Algos see the NAV series up to and including the current day during the Downward Pass.

`AssetNode` child_series entries SHALL NOT be modified — they remain the full price arrays set at init.

#### Scenario: child_series grows each day
- **WHEN** the Upward Pass completes for `t_idx == 5`
- **THEN** a StrategyNode child's entry in its parent's `child_series` SHALL be a view of `nav_array[:6]` (6 elements: days 0–5)

#### Scenario: View is O(1) — no array copy
- **WHEN** `child_series[child.id]` is updated
- **THEN** it SHALL be a numpy view of the pre-allocated `nav_array`, sharing the same underlying memory

---

### Requirement: XCASHX handling in weighted_return

If `temp['weights']` contains the key `XCASHX`, its return SHALL be `0.0` (cash earns no return). This ensures that nodes in a cash-fallback state (100% XCASHX from a halted AlgoStack) maintain their prior NAV value unchanged.

#### Scenario: Full XCASHX allocation
- **WHEN** a node has `temp['weights'] = {"XCASHX": 1.0}`
- **THEN** `weighted_return` SHALL be `0.0` and `nav_array[t_idx]` SHALL equal `nav_array[t_idx - 1]`

#### Scenario: Partial XCASHX allocation
- **WHEN** a node has `temp['weights'] = {"A": 0.5, "XCASHX": 0.5}` and asset A returns +2%
- **THEN** `weighted_return` SHALL be `0.5 * 0.02 + 0.5 * 0.0 = 0.01`
