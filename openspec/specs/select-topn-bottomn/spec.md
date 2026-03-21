## Purpose

Selection algos that rank children by a DSL metric and select the top or bottom N. Used by `filter` nodes in the AlgoStack. Both algos read child series from `target.perm['child_series']` and delegate metric computation to `compute_metric()`.

**Module:** `moa_allocations/engine/algos/selection.py`
**Classes:** `SelectTopN`, `SelectBottomN`

---

## Requirements

### Requirement: SelectTopN ranks children descending and selects top N

`SelectTopN(n, metric, lookback)` SHALL rank all children of the target node by computing `compute_metric(child_series, metric, lookback)` for each child, sort descending by metric value, and write the ids of the top `n` children to `target.temp['selected']`.

- `n` is sourced from `filter.select.count`
- `metric` is sourced from `filter.sort_by.function`
- `lookback` is sourced from `filter.sort_by.lookback` (already converted to integer trading days by the compiler)
- Child series: for `AssetNode` children, use the child's price series; for `StrategyNode` children, use the child's NAV series
- Series data SHALL be read from `target.perm['child_series'][child.id]` as numpy arrays and sliced to `[:t_idx+1]` for the current day

#### Scenario: Normal ranking with distinct metric values
- **WHEN** a filter node has 5 asset children with cumulative_return values [0.10, 0.05, 0.20, 0.15, 0.03] and n=3
- **THEN** `target.temp['selected']` SHALL contain the ids of the children with values [0.20, 0.15, 0.10] (top 3 descending)

#### Scenario: N exceeds number of children
- **WHEN** n=5 but the node has only 3 children
- **THEN** all 3 children SHALL be selected

#### Scenario: Tied metric values use stable sort
- **WHEN** two children have identical metric values
- **THEN** the child appearing earlier in the node's `children` list SHALL be selected first, preserving compile-time order

### Requirement: SelectBottomN ranks children ascending and selects bottom N

`SelectBottomN(n, metric, lookback)` SHALL behave identically to `SelectTopN` except it ranks children ascending by metric value and selects the bottom `n`.

- Parameters and series access are identical to `SelectTopN`
- Used by filter nodes with `select.mode == "bottom"`

#### Scenario: Normal ranking ascending
- **WHEN** a filter node has 4 asset children with std_dev_return values [0.02, 0.08, 0.01, 0.05] and n=2
- **THEN** `target.temp['selected']` SHALL contain the ids of the children with values [0.01, 0.02] (bottom 2 ascending)

#### Scenario: Tied metric values use stable sort
- **WHEN** two children have identical metric values
- **THEN** the child appearing earlier in the node's `children` list SHALL be selected first

### Requirement: NaN metric exclusion in selection

When `compute_metric()` returns `np.nan` for a child, that child SHALL be excluded from ranking entirely. Selection proceeds over the remaining children.

#### Scenario: Some children have NaN metrics
- **WHEN** a node has 5 children, 2 return NaN for the metric (insufficient history), and n=3
- **THEN** ranking proceeds over the 3 non-NaN children; all 3 are selected

#### Scenario: All children have NaN metrics
- **WHEN** all children return NaN for the metric
- **THEN** the algo SHALL return `False`, causing the engine to set 100% XCASHX

#### Scenario: Non-NaN children fewer than N after exclusion
- **WHEN** n=3 but only 2 children have valid (non-NaN) metrics
- **THEN** the 2 valid children SHALL be selected and the algo SHALL return `True`

### Requirement: SelectTopN and SelectBottomN return value contract

`SelectTopN` and `SelectBottomN` SHALL return `True` if at least one child is selected, and `False` if zero children are selected (which triggers XCASHX fallback). In practice, the compiler enforces `select.count >= 1`, so `False` only occurs when all children have NaN metrics.

#### Scenario: At least one child selected
- **WHEN** the algo selects 1 or more children
- **THEN** the algo SHALL return `True`

#### Scenario: No children selected
- **WHEN** zero children remain after NaN exclusion
- **THEN** the algo SHALL return `False`
