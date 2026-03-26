## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: _build_algo_stack forwards price_offset to SelectIfCondition

`_build_algo_stack` SHALL accept a `price_offset: int` parameter and SHALL pass it to `SelectIfCondition` when constructing the algo stack for an `IfElseNode`. For all other node types (`WeightNode`, `FilterNode`), `price_offset` SHALL be ignored.

#### Scenario: IfElseNode receives price_offset

- **WHEN** `_build_algo_stack` is called with an `IfElseNode` and `price_offset=100`
- **THEN** the returned `SelectIfCondition` instance SHALL store `price_offset=100` and use it during condition evaluation
