## MODIFIED Requirements

### Requirement: Lookback conversion to trading days
The compiler SHALL convert every `time_offset` string (matching `^[0-9]+d$`) to an integer number of trading days using the multiplier `d=1`. This conversion MUST be applied to:
- `lookback` on condition metric objects (`lhs`, `rhs`) in `if_else` conditions
- `duration` on condition objects in `if_else` conditions
- `lookback` on `sortMetric` objects in `filter` nodes
- `lookback` in `method_params` for `inverse_volatility` weight nodes

The `w` (week) and `m` (month) unit suffixes are removed. Only `d` (day) is accepted. Strategies using `w` or `m` SHALL fail with `DSLValidationError`.

After instantiation, all these fields SHALL contain `int` values — never raw `time_offset` strings.

#### Scenario: Days conversion
- **WHEN** a condition metric has `lookback: "200d"`
- **THEN** the instantiated condition dict contains `lookback: 200`

#### Scenario: Invalid week suffix rejected
- **WHEN** a sortMetric has `lookback: "4w"`
- **THEN** `DSLValidationError` is raised with a message indicating invalid `time_offset` format

#### Scenario: Invalid month suffix rejected
- **WHEN** a condition has `duration: "3m"`
- **THEN** `DSLValidationError` is raised with a message indicating invalid `time_offset` format

#### Scenario: Inverse volatility lookback
- **WHEN** a weight node has `method: "inverse_volatility"` and `method_params.lookback: "126d"`
- **THEN** the instantiated `WeightNode.method_params["lookback"]` equals `126`

## REMOVED Requirements

### Requirement: Week and month lookback multipliers
**Reason**: pidb_ib provides only daily bars. The `w=5` and `m=21` multipliers were approximate conversions for bar types that do not exist in the data source. No existing strategy uses `w` or `m`.
**Migration**: Replace `w` lookbacks with the equivalent in `d` (multiply by 5). Replace `m` lookbacks with the equivalent in `d` (multiply by 21). Example: `"4w"` → `"20d"`, `"3m"` → `"63d"`.
