# select-if-condition

**Module:** `moa_allocations/engine/algos/selection.py`

Selection algo for `if_else` nodes. Evaluates one or more metric conditions over a trailing duration window and routes to exactly one branch (`true_branch` or `false_branch`).

---

## Requirements

### Requirement: SelectIfCondition evaluates conditions and routes to a branch

`SelectIfCondition` SHALL accept a list of condition dicts, a `logic_mode` string (`"all"` or `"any"`), and a `price_offset: int` that identifies the simulation start position in the full price array. For each condition, it SHALL evaluate `lhs [comparator] rhs` at every day in the trailing duration window `[t - duration + 1, t]`. A condition passes only if the comparison is `True` on every day in the window. Results SHALL be combined using `logic_mode`: `"all"` requires every condition to pass; `"any"` requires at least one. The algo SHALL write `[true_branch.id]` or `[false_branch.id]` to `target.temp['selected']` and SHALL always return `True`.

When slicing a condition asset's price series for simulation day `t_idx`, the algo SHALL use indices `0` through `price_offset + t_idx` (inclusive), so that `series[-1]` is the price at the actual simulation date. The slice SHALL retain pre-simulation history from index 0 so that lookback metrics (e.g. `sma_price`) have sufficient data at early simulation days.

#### Scenario: Single condition, duration=1, condition met

- **WHEN** a single condition `lhs.current_price > 100` with `duration=1` is evaluated at day `t` and `current_price` at `t` is `105`
- **THEN** `target.temp['selected']` SHALL contain `[true_branch.id]` and the algo SHALL return `True`

#### Scenario: Single condition, duration=1, condition not met

- **WHEN** a single condition `lhs.current_price > 100` with `duration=1` is evaluated at day `t` and `current_price` at `t` is `95`
- **THEN** `target.temp['selected']` SHALL contain `[false_branch.id]` and the algo SHALL return `True`

#### Scenario: Condition with rhs metric instead of scalar

- **WHEN** a condition has `rhs` as a metric dict (not a number) with `rhs.asset`, `rhs.function`, and `rhs.lookback`
- **THEN** the algo SHALL compute `rhs_value` via `compute_metric()` on the rhs asset's series and compare `lhs_value [comparator] rhs_value`

#### Scenario: price_offset > 0 — current_price evaluates at simulation date

- **WHEN** `price_offset=100` and `t_idx=5` and the full price array for an asset is `price_arr` of length 200+
- **THEN** `current_price` SHALL return `price_arr[105]` (the price at simulation day 5), NOT `price_arr[5]` (a price from the pre-simulation lookback buffer)

#### Scenario: price_offset > 0 — sma_price uses window ending at simulation date

- **WHEN** `price_offset=100` and `t_idx=50` and the condition is `sma_price` with `lookback=100`
- **THEN** the SMA SHALL be computed over `price_arr[51:151]` (100 prices ending at simulation day 50), NOT over `price_arr[0:50]` (prices from the pre-simulation period)

#### Scenario: price_offset=0 — behaviour is unchanged

- **WHEN** `price_offset=0` (no pre-simulation lookback buffer)
- **THEN** condition evaluation SHALL behave identically to the previous implementation — `price_arr[:t_idx+1]` is unaffected by the offset

### Requirement: Duration window evaluates every day in the trailing window

For a condition with `duration = D`, the algo SHALL evaluate the comparison independently at each day index in `[max(0, t - D + 1), t]`. The condition passes only if every day in the window returns `True`.

#### Scenario: Duration=3, all days pass

- **WHEN** `duration=3` and the condition is `True` at days `t-2`, `t-1`, and `t`
- **THEN** the condition SHALL pass

#### Scenario: Duration=3, one day fails

- **WHEN** `duration=3` and the condition is `True` at days `t-2` and `t` but `False` at `t-1`
- **THEN** the condition SHALL fail and the algo SHALL route to `false_branch`

#### Scenario: Duration exceeds available history

- **WHEN** `duration=5` but only 3 days of history are available (day index 2 of the backtest)
- **THEN** the algo SHALL evaluate only the available days `[0, 1, 2]` and SHALL NOT fail solely because the window is shorter than duration

### Requirement: NaN causes condition failure

If `compute_metric()` returns `NaN` for either `lhs` or `rhs` on any day within the duration window, that day's check SHALL return `False`, causing the entire duration check to fail and routing to `false_branch`.

#### Scenario: NaN on lhs metric

- **WHEN** `lhs` metric returns `NaN` at any day in the duration window
- **THEN** the condition SHALL fail for that day, the duration check SHALL fail, and the algo SHALL route to `false_branch`

#### Scenario: NaN on rhs metric

- **WHEN** `rhs` is a metric dict and returns `NaN` at any day in the duration window
- **THEN** the condition SHALL fail for that day, the duration check SHALL fail, and the algo SHALL route to `false_branch`

### Requirement: Logic mode combines multiple conditions

When multiple conditions are present, `logic_mode` SHALL determine how individual condition results are combined: `"all"` requires every condition to pass (logical AND); `"any"` requires at least one condition to pass (logical OR).

#### Scenario: Logic mode "all", all conditions pass

- **WHEN** `logic_mode="all"` and conditions `[C1, C2]` both pass their duration checks
- **THEN** the algo SHALL route to `true_branch`

#### Scenario: Logic mode "all", one condition fails

- **WHEN** `logic_mode="all"` and condition `C1` passes but `C2` fails
- **THEN** the algo SHALL route to `false_branch`

#### Scenario: Logic mode "any", one condition passes

- **WHEN** `logic_mode="any"` and condition `C1` fails but `C2` passes
- **THEN** the algo SHALL route to `true_branch`

#### Scenario: Logic mode "any", all conditions fail

- **WHEN** `logic_mode="any"` and all conditions fail their duration checks
- **THEN** the algo SHALL route to `false_branch`

### Requirement: Comparator support

The algo SHALL support two comparators: `"greater_than"` (lhs > rhs) and `"less_than"` (lhs < rhs).

#### Scenario: greater_than comparator

- **WHEN** comparator is `"greater_than"` and `lhs_value` is `10` and `rhs_value` is `5`
- **THEN** the comparison SHALL return `True`

#### Scenario: less_than comparator

- **WHEN** comparator is `"less_than"` and `lhs_value` is `3` and `rhs_value` is `5`
- **THEN** the comparison SHALL return `True`

#### Scenario: Equal values with greater_than

- **WHEN** comparator is `"greater_than"` and `lhs_value` equals `rhs_value`
- **THEN** the comparison SHALL return `False` (strict inequality)

### Requirement: _build_algo_stack forwards price_offset to SelectIfCondition

`_build_algo_stack` SHALL accept a `price_offset: int` parameter and SHALL pass it to `SelectIfCondition` when constructing the algo stack for an `IfElseNode`. For all other node types (`WeightNode`, `FilterNode`), `price_offset` SHALL be ignored.

#### Scenario: IfElseNode receives price_offset

- **WHEN** `_build_algo_stack` is called with an `IfElseNode` and `price_offset=100`
- **THEN** the returned `SelectIfCondition` instance SHALL store `price_offset=100` and use it during condition evaluation
