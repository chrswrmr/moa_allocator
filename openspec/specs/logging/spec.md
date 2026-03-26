## Purpose

Defines the logging instrumentation across the `moa_allocations` engine. All modules emit structured DEBUG records via `logging.getLogger(__name__)`; `main.py` configures the handlers. Keyword anchors in message strings enable grep-based log analysis.

**Modules:** `moa_allocations.compiler.compiler`, `moa_allocations.engine.runner`, `moa_allocations.engine.algos.selection`, `moa_allocations.engine.algos.weighting`, `main.py`
**Introduced:** add-logger

---

## Requirements

### Requirement: Module-level loggers via `__name__`

Each module that emits log events SHALL create a module-level logger using `logging.getLogger(__name__)`. The following modules MUST have a logger:

- `moa_allocations.compiler.compiler`
- `moa_allocations.engine.runner`
- `moa_allocations.engine.algos.selection`
- `moa_allocations.engine.algos.weighting`

`main.py` (the CLI entry point) SHALL configure handlers on the root `moa_allocations` logger. Library modules MUST NOT configure handlers themselves.

#### Scenario: Logger hierarchy matches module structure
- **WHEN** the engine runs a strategy
- **THEN** every log record's `name` attribute corresponds to the emitting module's `__name__` (e.g., `moa_allocations.engine.algos.selection`)

#### Scenario: Library modules do not configure handlers
- **WHEN** `Runner` or any algo module is imported without running `main.py`
- **THEN** no handlers are attached and no output is produced (NullHandler behaviour)

---

### Requirement: CLI `--debug` flag

`main.py` SHALL accept a `--debug` boolean flag via argparse. The flag defaults to `False`.

- Without `--debug`: console StreamHandler level is INFO.
- With `--debug`: console StreamHandler level is DEBUG.

The flag MUST NOT affect the FileHandler level (always DEBUG).

#### Scenario: Default console level is INFO
- **WHEN** the CLI is invoked without `--debug`
- **THEN** the StreamHandler emits only INFO-level and above messages to stderr

#### Scenario: `--debug` enables console DEBUG
- **WHEN** the CLI is invoked with `--debug`
- **THEN** the StreamHandler emits DEBUG-level and above messages to stderr

---

### Requirement: Two handlers — FileHandler and StreamHandler

`main.py` SHALL configure exactly two handlers on the `moa_allocations` logger:

1. **FileHandler** — writes to the log file path; level is always DEBUG.
2. **StreamHandler** — writes to stderr; level is INFO by default, DEBUG with `--debug`.

Both handlers SHALL use the same format string. The format MUST include at minimum: timestamp, level, and message.

#### Scenario: FileHandler captures all DEBUG output
- **WHEN** a strategy run completes
- **THEN** the log file contains every DEBUG, INFO, WARNING, and ERROR message emitted during the run

#### Scenario: StreamHandler respects level setting
- **WHEN** a strategy run completes without `--debug`
- **THEN** the console output contains only INFO-level and above messages

---

### Requirement: Log file naming and location

Each run SHALL produce a log file at:

```
logs/<YYYYMMDD_HHMM>_<strategy-stem>_log.txt
```

Where:
- `<YYYYMMDD_HHMM>` is the same timestamp used for the output CSV filename.
- `<strategy-stem>` is the strategy file's stem (without `.moastrat.json`).
- The `logs/` directory is created at runtime if it does not exist.
- The `logs/` directory SHALL be added to `.gitignore`.

#### Scenario: Log file created alongside CSV output
- **WHEN** a strategy run completes with strategy file `strategies/spy_sma200.moastrat.json`
- **THEN** a file exists at `logs/<timestamp>_spy_sma200_log.txt` containing the full DEBUG trace

#### Scenario: `logs/` directory created automatically
- **WHEN** the `logs/` directory does not exist before a run
- **THEN** `main.py` creates it before writing the log file

#### Scenario: Timestamp shared with CSV
- **WHEN** a run produces CSV at `output/20240323_1430_spy_sma200.csv`
- **THEN** the log file is `logs/20240323_1430_spy_sma200_log.txt` (same timestamp and stem)

---

### Requirement: COMPILE keyword event

`compiler.py` SHALL emit a DEBUG log with keyword `COMPILE` after successfully building the strategy tree.

The message MUST include: the strategy file path and the root node label (`name or id`).

The call MUST include an `extra` dict with keys: `keyword`, `strategy_path`, `root_node`.

#### Scenario: Strategy compilation logged
- **WHEN** `compile_strategy("strategies/spy_sma200.moastrat.json")` succeeds
- **THEN** a DEBUG record is emitted starting with `COMPILE` containing the file path and root node label

---

### Requirement: REBALANCE keyword event

`runner.py` SHALL emit a DEBUG log with keyword `REBALANCE` at the start of each rebalance day, and a single-line log `t=<YYYY-MM-DD>  (no rebalance)` on non-rebalance days (after `t_idx == 0`).

The rebalance message MUST include: the date (`YYYY-MM-DD`) and `t_idx`.

The call MUST include an `extra` dict with keys: `keyword`, `date`, `t_idx`.

#### Scenario: Rebalance day logged
- **WHEN** the simulation reaches a rebalance day (e.g., `t_idx=0`, `date=2021-01-04`)
- **THEN** a DEBUG record is emitted starting with `REBALANCE` containing the date and t_idx

#### Scenario: Non-rebalance day logged
- **WHEN** the simulation reaches a non-rebalance day (e.g., `date=2021-01-05`)
- **THEN** a single DEBUG record is emitted: `t=2021-01-05  (no rebalance)`

---

### Requirement: METRIC keyword event

`selection.py` SHALL emit a DEBUG log with keyword `METRIC` for every metric computation performed during `_rank_and_select()` and `_evaluate_condition_at_day()`.

The message MUST include: node label (`name or id`), node type, ticker or child label, metric function name, lookback value, and computed value (6 decimal places).

The call MUST include an `extra` dict with keys: `keyword`, `node`, `node_type`, `ticker`, `fn`, `lookback`, `value`.

#### Scenario: Metric computed during ranking
- **WHEN** `_rank_and_select()` computes `sma_price` with lookback 200 for child `SPY` under node `"momentum_filter"`
- **THEN** a DEBUG record is emitted: `METRIC  node=momentum_filter  type=filter  ticker=SPY  fn=sma_price  lookback=200  value=<computed>` with matching `extra` dict

#### Scenario: Metric computed during condition evaluation
- **WHEN** `_evaluate_condition_at_day()` computes the LHS metric (e.g., `rsi`, lookback 14) for asset `SPY`
- **THEN** a DEBUG record is emitted with keyword `METRIC` containing the node, node_type, ticker, function, lookback, and value

---

### Requirement: SELECT keyword event

`selection.py` SHALL emit a DEBUG log with keyword `SELECT` after `_rank_and_select()` determines the selected and dropped children, and after `SelectAll.__call__()` selects all children.

The message MUST include: node label, node type, list of selected child labels, list of dropped child labels.

The call MUST include an `extra` dict with keys: `keyword`, `node`, `node_type`, `selected`, `dropped`.

#### Scenario: Top-N selection result logged
- **WHEN** `SelectTopN(2, "cumulative_return", 20)` runs on a node with 4 children and selects the top 2
- **THEN** a DEBUG record is emitted starting with `SELECT` listing the 2 selected and 2 dropped children

#### Scenario: All children selected
- **WHEN** `SelectAll()` runs on a node
- **THEN** a DEBUG record is emitted with `SELECT` showing all children as selected and none dropped

---

### Requirement: CONDITION keyword event

`selection.py` SHALL emit a DEBUG log with keyword `CONDITION` for each condition evaluation in `_evaluate_condition_at_day()`.

The message MUST include: node label, node type, LHS value, comparator, RHS value, and boolean result.

When `duration > 1`, the condition is evaluated for each sub-day. Each sub-day evaluation SHALL emit its own `CONDITION` log line.

The call MUST include an `extra` dict with keys: `keyword`, `node`, `node_type`, `lhs_value`, `comparator`, `rhs_value`, `result`, and `day_offset` (0-based offset within the duration window).

`CONDITION` is only emitted when both LHS and RHS are non-NaN. If either value is NaN, the function returns `False` early (after the METRIC log for the NaN value) without emitting a CONDITION record.

#### Scenario: Simple condition (duration=1)
- **WHEN** a condition `rsi > 30` evaluates with LHS=45.2 and RHS=30
- **THEN** a single DEBUG record is emitted: `CONDITION  node=<label>  type=if_else  lhs=45.200000  op=>  rhs=30.000000  result=True  day=0`

#### Scenario: Duration condition (duration > 1)
- **WHEN** a condition with `duration=3` evaluates across 3 sub-days
- **THEN** 3 separate DEBUG records are emitted, each with `day=0`, `day=1`, `day=2` respectively, each showing that sub-day's LHS value, RHS value, and result

#### Scenario: NaN value suppresses CONDITION record
- **WHEN** the LHS or RHS metric returns NaN (e.g., insufficient lookback history)
- **THEN** a METRIC record is emitted for the NaN value but no CONDITION record follows

---

### Requirement: DECISION keyword event

`selection.py` SHALL emit a DEBUG log with keyword `DECISION` after `SelectIfCondition.__call__()` resolves which branch to follow.

The message MUST include: node label, node type (`if_else`), branch direction (`true` or `false`), and the label of the selected branch node (ticker for asset nodes, `name or id` for strategy nodes).

The call MUST include an `extra` dict with keys: `keyword`, `node`, `node_type`, `branch`, `selected`.

#### Scenario: True branch taken
- **WHEN** all conditions evaluate to True and the true branch is selected
- **THEN** a DEBUG record is emitted: `DECISION  node=<label>  type=if_else  branch=true  selected=<branch-label>`

#### Scenario: False branch taken
- **WHEN** one or more conditions evaluate to False and the false branch is selected
- **THEN** a DEBUG record is emitted: `DECISION  node=<label>  type=if_else  branch=false  selected=<branch-label>`

---

### Requirement: WEIGHT keyword event

`weighting.py` SHALL emit a DEBUG log with keyword `WEIGHT` after computing per-child weights.

The message MUST include: node label, node type, weighting method name, and the weight map (child label → weight).

The call MUST include an `extra` dict with keys: `keyword`, `node`, `node_type`, `method`, `weights`.

This applies to `WeightEqually`, `WeightSpecified`, and `WeightInvVol`.

#### Scenario: Equal weighting logged
- **WHEN** `WeightEqually()` assigns weights to 3 selected children
- **THEN** a DEBUG record is emitted: `WEIGHT  node=<label>  type=<type>  method=equal  weights={child1: 0.333333, child2: 0.333333, child3: 0.333333}`

#### Scenario: Inverse volatility weighting logged
- **WHEN** `WeightInvVol(60)` computes weights
- **THEN** a DEBUG record is emitted with `method=inverse_volatility` and the per-child weight map

---

### Requirement: NAV keyword event

`runner.py` SHALL emit a DEBUG log with keyword `NAV` after updating each node's `nav_array[t_idx]` in `_upward_pass()`.

The message MUST include: node label, node type, `t_idx`, and the new NAV value (6 decimal places).

The call MUST include an `extra` dict with keys: `keyword`, `node`, `node_type`, `t_idx`, `nav`.

#### Scenario: NAV updated for strategy node
- **WHEN** the upward pass computes `nav_array[5] = 1.023456` for node `"us_equities"`
- **THEN** a DEBUG record is emitted: `NAV  node=us_equities  type=<type>  t=5  nav=1.023456`

---

### Requirement: ALLOC keyword event

`runner.py` SHALL emit a DEBUG log with keyword `ALLOC` after `_flatten_weights()` produces the global weight vector for the day.

The message MUST include: the date (`YYYY-MM-DD`) and the full ticker → weight map.

The call MUST include an `extra` dict with keys: `keyword`, `date`, `weights`.

#### Scenario: Daily allocation logged
- **WHEN** `_flatten_weights()` returns `{"SPY": 0.6, "BND": 0.4}` on date `2021-03-15`
- **THEN** a DEBUG record is emitted: `ALLOC  t=2021-03-15  weights={'SPY': 0.600000, 'BND': 0.400000}`

---

### Requirement: UPWARD pass boundaries

`runner.py` SHALL emit a DEBUG log with keyword `UPWARD` and text `start` at the beginning of each upward pass iteration, with timestamp and iteration metadata.

The message MUST include: the date (`YYYY-MM-DD`) and `t_idx`.

The call MUST include an `extra` dict with keys: `keyword`, `text`, `date`, `t_idx`.

#### Scenario: UPWARD pass starts on day 2+
- **WHEN** the upward pass executes on a backtest day with t_idx > 0
- **THEN** a log entry with keyword "UPWARD" and text "start" is emitted, including date and t_idx

---

### Requirement: Per-node UPWARD detail with children

`runner.py` SHALL log structured detail blocks for each node processed in the upward pass, showing the node's identity, type, and the NAV values of all direct children that feed into that node's calculation.

Detail blocks SHALL be emitted at DEBUG level after each node's NAV is computed.

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

---

### Requirement: Per-node-type formatting patterns for UPWARD detail

UPWARD pass detail logs SHALL use visual patterns with box-drawing characters that distinguish node types and data flow.

#### Scenario: WeightNode log format
- **WHEN** a WeightNode's UPWARD detail is logged
- **THEN** the format uses `┌─` header, `│` content lines with `←` prefix for children, and `└─` footer

#### Scenario: FilterNode log format
- **WHEN** a FilterNode's UPWARD detail is logged
- **THEN** the format uses `┌─` header, `↓` for selected children, `✗` for dropped children, config line showing metric and lookback, and `└─` footer

#### Scenario: IfElseNode log format
- **WHEN** an IfElseNode's UPWARD detail is logged
- **THEN** the format uses `┌─` header, condition lines, decision line, branch lines with `[SELECTED]` marker, and `└─` footer

---

### Requirement: Child NAV values reflect calculation inputs

NAV values logged for each child in UPWARD detail logs SHALL be the actual values used in the weighted return calculation for that iteration.

#### Scenario: Asset child NAV comes from price data
- **WHEN** an asset child is logged during UPWARD pass
- **THEN** the NAV value shown is the asset's price at the current t_idx from the price_data

#### Scenario: Strategy node child NAV comes from node's nav_array
- **WHEN** a strategy node child is logged during UPWARD pass
- **THEN** the NAV value shown is the child strategy node's nav_array[t_idx] value

---

### Requirement: `extra` dict convention on all DEBUG calls

Every DEBUG-level log call in the instrumented modules MUST include an `extra` dict parameter containing the same data as the formatted message string.

Every `extra` dict MUST include a `keyword` key matching the message's keyword anchor (e.g., `"METRIC"`, `"SELECT"`).

The `extra` dict fields are ignored by the text formatter but SHALL be available on the `LogRecord` for future structured formatters.

#### Scenario: Extra dict present on METRIC event
- **WHEN** a METRIC log is emitted
- **THEN** the `LogRecord` has attributes `keyword="METRIC"`, `node=<str>`, `node_type=<str>`, `ticker=<str>`, `fn=<str>`, `lookback=<int>`, `value=<float>`

#### Scenario: Extra dict does not affect text output
- **WHEN** the text formatter renders a DEBUG log with `extra={"keyword": "METRIC", ...}`
- **THEN** the output contains only the formatted message, not the raw extra fields

---

### Requirement: INFO-level events in `main.py`

`main.py` SHALL emit INFO-level logs for run lifecycle events:

1. After compilation: strategy file path, number of tickers found, date range
2. Before simulation: "Simulation starting" with start date, end date, rebalance frequency
3. After simulation: output CSV path, log file path, elapsed time

These messages do NOT use keyword anchors (keyword anchors are for DEBUG-level algo tracing only).

#### Scenario: Compilation info logged
- **WHEN** a strategy is compiled and tickers are collected
- **THEN** an INFO record is emitted containing the strategy path, ticker count, and date range

#### Scenario: Run completion info logged
- **WHEN** a run completes
- **THEN** an INFO record is emitted containing the output path, log path, and elapsed time

---

### Requirement: Node label helper

A utility function or pattern SHALL exist to produce a human-readable label for a node: `node.name or node.id`.

All log messages that reference a node MUST use this label pattern. This ensures logs are readable when names exist and unambiguous when they don't.

#### Scenario: Named node uses name
- **WHEN** a node has `name="us_equities"` and `id="abc-123"`
- **THEN** log messages referencing this node use `"us_equities"`

#### Scenario: Unnamed node falls back to id
- **WHEN** a node has `name=None` and `id="abc-123"`
- **THEN** log messages referencing this node use `"abc-123"`

---

### Requirement: Node type in log messages

All log messages that reference a node MUST include a `type` field reflecting the DSL node type: `if_else`, `weight`, or `filter`.

This is derived from the Python class name via a lookup map and included in both the message string and the `extra` dict as `node_type`.

#### Scenario: Node type shown in METRIC message
- **WHEN** a METRIC log is emitted for a filter node
- **THEN** the message includes `type=filter`

#### Scenario: Node type shown in DECISION message
- **WHEN** a DECISION log is emitted for an if_else node
- **THEN** the message includes `type=if_else`
