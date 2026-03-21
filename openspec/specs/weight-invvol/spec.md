## Purpose

Weighting algo that assigns weights inversely proportional to return volatility. Used by `weight/inverse_volatility` nodes in the AlgoStack. Children with zero or NaN volatility are excluded and their weight redistributed to the remaining children.

**Module:** `moa_allocations/engine/algos/weighting.py`
**Class:** `WeightInvVol`

---

## Requirements

### Requirement: WeightInvVol computes inverse-volatility weights

`WeightInvVol(lookback)` SHALL weight each selected child inversely proportional to its return volatility over the `lookback` window.

- `lookback` is sourced from `weight.method_params.lookback` (already converted to integer trading days by the compiler)
- For each child in `target.temp['selected']`, compute `std_dev_return` over `lookback` days on the child's NAV/price series
- Raw weight for child `i` = `1.0 / vol[i]`
- Normalise: `weight[i] = raw_weight[i] / sum(all raw_weights)`
- Write normalised weights to `target.temp['weights']` as `{node_id: float}`
- All weights SHALL sum to `1.0`

#### Scenario: Normal inverse-volatility weighting
- **WHEN** 3 selected children have std_dev_return values [0.02, 0.04, 0.04]
- **THEN** raw weights are [50.0, 25.0, 25.0], normalised to [0.50, 0.25, 0.25], and the algo SHALL return `True`

#### Scenario: Single selected child
- **WHEN** only 1 child is selected
- **THEN** that child SHALL receive weight `1.0`

### Requirement: WeightInvVol excludes zero and NaN volatility children

Children with zero volatility (`std_dev_return == 0.0`) or NaN volatility (insufficient history for `lookback`) SHALL be excluded from weighting. Their weight is redistributed to the remaining children through renormalisation.

#### Scenario: One child has zero volatility
- **WHEN** 3 selected children have std_dev_return values [0.02, 0.0, 0.04]
- **THEN** the zero-vol child is excluded; the remaining 2 children are weighted as [0.02, 0.04] → raw [50.0, 25.0] → normalised [0.667, 0.333]

#### Scenario: One child has NaN volatility
- **WHEN** 3 selected children have std_dev_return values [0.02, NaN, 0.04]
- **THEN** the NaN-vol child is excluded; the remaining 2 children are weighted identically to the zero-vol exclusion case

#### Scenario: All children have zero or NaN volatility
- **WHEN** every selected child has zero or NaN std_dev_return
- **THEN** the algo SHALL return `False`, causing the engine to set 100% XCASHX

### Requirement: WeightInvVol return value contract

`WeightInvVol` SHALL return `True` if at least one child receives a non-zero weight, and `False` if all children are excluded (zero/NaN vol).

#### Scenario: At least one valid child
- **WHEN** at least one selected child has a positive, finite volatility
- **THEN** the algo SHALL return `True` with `target.temp['weights']` summing to `1.0`

#### Scenario: All children excluded
- **WHEN** all selected children have zero or NaN volatility
- **THEN** the algo SHALL return `False`
