## Purpose

Collect the daily global weight vectors produced by the simulation loop into a `pd.DataFrame` and write it to `output/allocations.csv`. This is the primary deliverable of `Runner.run()` consumed by downstream systems (`bt_rebalancer`, `iba`).

## Requirements

### Requirement: Runner.run() returns allocations DataFrame
`Runner.run()` SHALL return a `pd.DataFrame` containing daily allocation weights. The return type SHALL be `pd.DataFrame`, not `None`.

#### Scenario: Successful run returns DataFrame
- **WHEN** `runner.run()` completes without error
- **THEN** the return value is a `pd.DataFrame` with one row per trading day in `[start_date, end_date]`

### Requirement: DATE column format
The DataFrame SHALL have `DATE` as its first column, containing ISO 8601 date strings (`YYYY-MM-DD`).

#### Scenario: DATE column values
- **WHEN** the simulation runs over trading days 2024-01-02 through 2024-01-04
- **THEN** the `DATE` column contains `['2024-01-02', '2024-01-03', '2024-01-04']` as strings

### Requirement: Ticker column order
Ticker columns SHALL appear after `DATE` in DSL leaf order (left-to-right DFS traversal of the compiled tree). Tickers SHALL be uppercase. If `XCASHX` received weight on any day during the simulation, it SHALL appear as the last column.

#### Scenario: Leaf order matches DSL structure
- **WHEN** the DSL tree has leaves in order `SPY`, `BND`, `GLD`
- **THEN** DataFrame columns are `['DATE', 'SPY', 'BND', 'GLD']`

#### Scenario: XCASHX appended last when present
- **WHEN** at least one day routed weight to `XCASHX`
- **THEN** DataFrame columns end with `XCASHX` (e.g., `['DATE', 'SPY', 'BND', 'XCASHX']`)

#### Scenario: XCASHX absent when never triggered
- **WHEN** no day during the simulation produced weight for `XCASHX`
- **THEN** `XCASHX` does not appear as a column

### Requirement: Weight values
Each cell SHALL contain a `float` in `[0.0, 1.0]`. Every row SHALL sum to `1.0`.

#### Scenario: Row sums
- **WHEN** a row has values `SPY=0.6, BND=0.4`
- **THEN** the row sums to `1.0`

#### Scenario: XCASHX day
- **WHEN** all AlgoStacks halted on a given day
- **THEN** the row has `XCASHX=1.0` and all ticker columns are `0.0`

### Requirement: CSV output
On every successful `run()` call, the engine SHALL write the allocations DataFrame to `output/allocations.csv`. The `output/` directory SHALL be created if it does not exist. The CSV SHALL have no index column (`index=False`).

#### Scenario: Output directory does not exist
- **WHEN** `run()` completes and the `output/` directory is absent
- **THEN** the directory is created and `allocations.csv` is written

#### Scenario: Output directory already exists
- **WHEN** `run()` completes and `output/` already exists
- **THEN** `allocations.csv` is written (overwriting any prior file)

#### Scenario: CSV format
- **WHEN** the DataFrame has columns `['DATE', 'SPY', 'BND', 'XCASHX']`
- **THEN** the CSV header line is `DATE,SPY,BND,XCASHX` and each data row contains comma-separated float values
