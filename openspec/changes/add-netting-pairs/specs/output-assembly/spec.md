## MODIFIED Requirements

### Requirement: Ticker column order
Ticker columns SHALL appear after `DATE` in DSL leaf order (left-to-right DFS traversal of the compiled tree). Tickers SHALL be uppercase. If a `netting.cash_ticker` is configured and received weight on any day during the simulation and is NOT already a DSL leaf, it SHALL appear after all DSL leaf columns. If `XCASHX` received weight on any day during the simulation, it SHALL appear as the last column.

Column order: `DATE` → DSL leaf tickers (in DFS order) → netting cash ticker (if non-leaf and used) → `XCASHX` (if used).

#### Scenario: Leaf order matches DSL structure
- **WHEN** the DSL tree has leaves in order `SPY`, `BND`, `GLD`
- **THEN** DataFrame columns are `['DATE', 'SPY', 'BND', 'GLD']`

#### Scenario: XCASHX appended last when present
- **WHEN** at least one day routed weight to `XCASHX`
- **THEN** DataFrame columns end with `XCASHX` (e.g., `['DATE', 'SPY', 'BND', 'XCASHX']`)

#### Scenario: XCASHX absent when never triggered
- **WHEN** no day during the simulation produced weight for `XCASHX`
- **THEN** `XCASHX` does not appear as a column

#### Scenario: Netting cash ticker as non-leaf column
- **WHEN** netting is configured with `cash_ticker="SHV"` and `SHV` is not a DSL leaf and netting produced freed weight on at least one day
- **THEN** `SHV` appears as a column after all DSL leaf columns but before `XCASHX`

#### Scenario: Netting cash ticker is already a DSL leaf
- **WHEN** netting is configured with `cash_ticker="SHV"` and `SHV` is already a DSL leaf
- **THEN** `SHV` appears in its normal DSL leaf order position (no duplicate column)

#### Scenario: Netting frees cash to XCASHX
- **WHEN** netting is configured with no `cash_ticker` (null) and netting produces freed weight
- **THEN** `XCASHX` receives the freed weight and appears as the last column
