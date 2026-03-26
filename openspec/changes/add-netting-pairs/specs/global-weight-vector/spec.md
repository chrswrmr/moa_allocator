## MODIFIED Requirements

### Requirement: Flatten local weights to global leaf weights
After each Downward Pass completes, the engine SHALL compute a global weight for every leaf node by multiplying local weights along the path from root to that leaf: `global_weight(leaf) = ∏ local_weights along path from root → leaf`. The flattening SHALL use a DFS walk from `root.root`, carrying the cumulative product downward. `XCASHX` entries in `temp['weights']` SHALL be accumulated as a virtual leaf.

After flattening and before the sum-to-one assertion, if `settings.netting` is configured with a non-empty `pairs` list, the engine SHALL apply the netting transformation to the global weight dict. The netting transformation SHALL process each pair, compute net exposure, collapse to single-leg positions, and allocate freed weight to the configured cash ticker or `XCASHX` (as specified by the `netting` capability).

#### Scenario: Simple two-level equal-weight tree
- **WHEN** root has `temp['weights'] = {'A': 0.5, 'B': 0.5}` and A, B are asset leaves
- **THEN** global weights are `{'A': 0.5, 'B': 0.5}`

#### Scenario: Nested weight nodes
- **WHEN** root has `temp['weights'] = {'sub1': 0.6, 'sub2': 0.4}` and sub1 has `temp['weights'] = {'SPY': 0.5, 'BND': 0.5}` and sub2 has `temp['weights'] = {'GLD': 1.0}`
- **THEN** global weights are `{'SPY': 0.3, 'BND': 0.3, 'GLD': 0.4}`

#### Scenario: if_else node with one branch selected
- **WHEN** an `if_else` node has `temp['selected'] = ['true_branch_id']` and `temp['weights'] = {'true_branch_id': 1.0}` and the true branch is an asset leaf `SPY`
- **THEN** the global weight for `SPY` includes the full parent weight; the false branch leaf receives `0.0` weight

#### Scenario: XCASHX from AlgoStack halt
- **WHEN** a node's AlgoStack halted and `temp['weights'] = {'XCASHX': 1.0}` with parent global weight `0.4`
- **THEN** `XCASHX` accumulates `0.4` in the global weight vector

#### Scenario: Netting applied after flattening
- **WHEN** flattening produces `{QQQ: 0.30, PSQ: 0.10, GLD: 0.60}` and netting is configured with pair `(QQQ, 1, PSQ, -1)` and `cash_ticker="SHV"`
- **THEN** after netting, the weight vector is `{QQQ: 0.20, GLD: 0.60, SHV: 0.20}`

#### Scenario: No netting configured — flatten unchanged
- **WHEN** flattening produces `{QQQ: 0.30, PSQ: 0.10, GLD: 0.60}` and no netting is configured
- **THEN** the weight vector remains `{QQQ: 0.30, PSQ: 0.10, GLD: 0.60}`

### Requirement: Global weights sum to one
The sum of all leaf global weights (including `XCASHX`) SHALL equal `1.0` on every trading day. The engine SHALL assert this with a tolerance of `1e-9`. An `AssertionError` SHALL be raised if the sum falls outside `[1.0 - 1e-9, 1.0 + 1e-9]`. This assertion SHALL run after netting (if configured).

#### Scenario: Weights sum exactly to one
- **WHEN** the flattening produces leaf weights `{'SPY': 0.6, 'BND': 0.4}`
- **THEN** the assertion passes (sum = 1.0)

#### Scenario: Float drift within tolerance
- **WHEN** the flattening produces leaf weights that sum to `0.9999999999` due to floating-point multiplication
- **THEN** the assertion passes (within `1e-9`)

#### Scenario: Weights do not sum to one
- **WHEN** a bug causes leaf weights to sum to `0.95`
- **THEN** the assertion fails with `AssertionError`

#### Scenario: Weights sum to one after netting
- **WHEN** pre-netting weights sum to `1.0` and netting redistributes weight from pairs to cash ticker
- **THEN** post-netting weights still sum to `1.0` (within `1e-9`)

### Requirement: Carry forward on non-rebalance days
On non-rebalance days (when the Downward Pass is skipped), the engine SHALL reuse the previous day's global weight vector unchanged. No flattening SHALL occur. Netting (if configured) SHALL still be applied to the carried-forward flattened output.

#### Scenario: Weekly rebalance mid-week day
- **WHEN** rebalance frequency is `weekly` and the current day is not the first trading day of the calendar week
- **THEN** the global weight vector from the prior day is copied forward without modification

#### Scenario: First simulation day
- **WHEN** `t_idx == 0` (always a rebalance day)
- **THEN** the Downward Pass runs and flattening produces the initial global weight vector
