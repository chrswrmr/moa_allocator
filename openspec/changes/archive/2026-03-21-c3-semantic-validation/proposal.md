## Why

JSON Schema validation (C2) catches structural errors but cannot enforce cross-field invariants such as UUID uniqueness, weight sums, or date ordering. Without semantic validation, a structurally valid strategy file can reach the engine in a broken state and produce silent wrong results.

## What Changes

- Extend `compile_strategy()` with a semantic validation pass (Step 3) that runs after JSON Schema validation and before node instantiation.
- Implement the following checks, each raising `DSLValidationError` with the offending node's `id` and `name`:
  - All node `id` values in the file are globally unique
  - For `weight` nodes with `method == "defined"`: `custom_weights` keys match child `id`s exactly (no missing, no extra) and values sum to `1.0 ± 0.001`
  - For `filter` nodes: `select.count >= 1` and `select.count <= len(children)`
  - All conditionMetric and sortMetric objects using functions other than `current_price` must include `lookback`
  - `settings.start_date < settings.end_date`
  - `settings.rebalance_threshold`, if set, must satisfy `0 < value < 1`

## Capabilities

### New Capabilities

- `semantic-validation`: Post-schema semantic checks in `compile_strategy()` covering UUID uniqueness, defined-weight completeness and sum, filter count bounds, lookback requirements, date ordering, and rebalance threshold range.

### Modified Capabilities

- `dsl-schema-validation`: The compiler's validation pipeline gains a new Step 3 (semantic pass) between JSON Schema validation and node instantiation. The pipeline sequence in the spec changes.

## Impact

- `moa_allocations/compiler/compiler.py` — primary implementation target
- `DSLValidationError` — already defined (C1/C2); no interface changes needed
- Tests: new unit tests covering each semantic rule (valid and invalid inputs)
- No changes to engine, algos, metrics, or the DSL schema itself
