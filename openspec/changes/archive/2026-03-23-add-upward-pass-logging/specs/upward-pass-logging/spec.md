# Specification: UPWARD Pass Logging

## ADDED Requirements

### Requirement: UPWARD pass boundaries
The system SHALL log structured markers at the start and completion of each upward pass, with timestamp and iteration metadata.

#### Scenario: UPWARD pass starts on day 2+
- **WHEN** the upward pass executes on a backtest day with t_idx > 0
- **THEN** a log entry with keyword "UPWARD" and text "start" is emitted, including date and t_idx

### Requirement: Per-node UPWARD detail with children
For each node processed in the upward pass, the system SHALL log the node's identity, type, and the NAV values of all direct children that feed into that node's calculation.

#### Scenario: WeightNode with asset children
- **WHEN** a WeightNode is processed during the upward pass with asset children [SPY, BND]
- **THEN** a log entry shows:
  - Node name, node type (weight), and node ID
  - Each child's name, NAV value, and weight allocation
  - Node's final calculated NAV

#### Scenario: WeightNode with strategy node children
- **WHEN** a WeightNode is processed during the upward pass with strategy node children
- **THEN** a log entry shows:
  - Node name, node type (weight), and node ID
  - Each child strategy node's name, NAV value (from that node's perm.nav_array), and weight
  - Node's final calculated NAV

#### Scenario: FilterNode with selected and dropped children
- **WHEN** a FilterNode is processed during the upward pass with N children, some selected and some dropped
- **THEN** a log entry shows:
  - Node name, node type (filter), node ID
  - Filter config: metric name and lookback period
  - Selected children marked with `↓` symbol, each with NAV and weight
  - Dropped children marked with `✗` symbol, each with NAV, no weight
  - Node's final calculated NAV

#### Scenario: IfElseNode with condition evaluation
- **WHEN** an IfElseNode is processed during the upward pass, its condition(s) evaluated, and one branch selected
- **THEN** a log entry shows:
  - Node name, node type (if_else), node ID
  - Logic mode (AND/OR)
  - Each condition statement on separate line (Condition1, Condition2, ...)
  - Decision result (true/false)
  - TRUE branch option with child name and NAV
  - FALSE branch option with child name and NAV
  - Selected branch marked with [SELECTED]
  - Node's final calculated NAV

### Requirement: Per-node-type formatting patterns
The system SHALL format UPWARD pass logs with visual patterns that distinguish node types and data flow.

#### Scenario: WeightNode log format
- **WHEN** a WeightNode's UPWARD detail is logged
- **THEN** the format is:
  ```
  ┌─ node=<name>  type=weight-<method>  NodeName = <name>  id=<id>
  │  ← NAV <child_name> nav= <nav_value>  w=<weight>  id=<child_id>
  │  ← NAV <child_name> nav= <nav_value>  w=<weight>  id=<child_id>
  │  NAV node  t=<t_idx>  nav=<calculated_nav>
  └─
  ```
  where `<method>` is "equal", "defined", or "inverse_volatility"

#### Scenario: FilterNode log format
- **WHEN** a FilterNode's UPWARD detail is logged
- **THEN** the format is:
  ```
  ┌─ node=<name>  type=filter-<direction><count>  NodeName = <name>  id=<id>
  │  Config: metric=<metric_name>  lookback=<days>
  │  ↓ NAV <selected_child> nav= <nav_value>  w=<weight>  id=<child_id>
  │  ✗ NAV <dropped_child> nav= <nav_value>  id=<child_id>  [dropped]
  │  NAV node  t=<t_idx>  nav=<calculated_nav>
  └─
  ```
  where `<direction><count>` is e.g. "top2" or "bottom1"

#### Scenario: IfElseNode log format
- **WHEN** an IfElseNode's UPWARD detail is logged
- **THEN** the format is:
  ```
  ┌─ type=if_else  logic_mode=<AND|OR>  NodeName = <name>  id=<id>
  │  Condition1: <condition_expression>
  │  Condition2: <condition_expression>
  │  Decision: <true|false>
  │   - true: NAV <branch_name> nav= <nav_value>  w=<weight>  id=<branch_id>
  │   - false: NAV <branch_name> nav= <nav_value>  w=<weight>  id=<branch_id>  [SELECTED]
  │  NAV node  t=<t_idx>  nav=<calculated_nav>
  └─
  ```

### Requirement: Child NAV values reflect calculation inputs
The NAV values logged for each child SHALL be the actual values used in the weighted return calculation for that iteration.

#### Scenario: Asset child NAV comes from price data
- **WHEN** an asset child is logged during UPWARD pass
- **THEN** the NAV value shown is the asset's price at the current t_idx from the price_data

#### Scenario: Strategy node child NAV comes from node's nav_array
- **WHEN** a strategy node child is logged during UPWARD pass
- **THEN** the NAV value shown is the child strategy node's nav_array[t_idx] value

### Requirement: Log structure respects existing logging level
UPWARD pass detail logs SHALL be emitted at DEBUG level, subject to the logger's existing level configuration. Pass boundaries (UPWARD start/complete) SHALL include keyword="UPWARD" in the extra dict.

#### Scenario: DEBUG level shows all UPWARD detail
- **WHEN** logger is configured at DEBUG level
- **THEN** all UPWARD pass entries (start, complete, per-node detail) appear in output

#### Scenario: INFO level shows no UPWARD detail
- **WHEN** logger is configured at INFO level or higher
- **THEN** UPWARD pass detail does not appear (respecting existing level threshold)
