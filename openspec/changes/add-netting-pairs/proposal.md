## Why

A strategy tree can independently select both a long ETF and its inverse-short ETF in different branches. After flattening, the portfolio holds offsetting positions (e.g., 30% QQQ + 10% PSQ) — economically absurd, costing double the fees and spreads for a net exposure achievable with a single leg. Netting collapses these pairs into a single position and redirects freed cash, producing cleaner output for downstream execution (`bt_rebalancer`, `iba`).

## What Changes

- Add an optional `netting` block to the DSL `settings` object containing a list of long/short ticker pairs with leverage factors and an optional cash ticker for freed allocation. **BREAKING**: DSL schema change (additive — existing strategies without `netting` are unaffected).
- After the global weight vector is flattened each day, apply a netting transformation that:
  - Computes net economic exposure per pair using leverage factors
  - Collapses to a single-leg position (long or short depending on net direction)
  - Allocates freed weight to the designated cash ticker or `XCASHX`
- Ensure the `netting.cash_ticker` (if specified) is included in the ticker collection so price data is fetched for it even if it is not a leaf in the tree.
- Netting is output-only (v1): the upward pass continues to use raw un-netted weights for NAV computation.

## Capabilities

### New Capabilities
- `netting`: Post-flatten transformation that nets offsetting long/short ETF pairs into single-leg positions and redistributes freed weight. Covers the netting math, pair validation, cash ticker handling, and integration into the daily simulation loop.

### Modified Capabilities
- `dsl-schema-validation`: Add `netting` as an optional property within the `settings` object schema definition.
- `semantic-validation`: Validate netting pair tickers exist as tree leaves, leverage signs are correct, no ticker appears in multiple pairs, and cash ticker (if set) is resolvable.
- `global-weight-vector`: After flattening, apply netting transformation before the sum-to-one assertion. The assertion still holds post-netting.
- `runner-init`: Collect tickers from netting config (cash ticker) and store parsed netting config for the simulation loop.
- `output-assembly`: Netting cash ticker may introduce a new column not present as a DSL leaf.

## Impact

- **DSL schema** (`moa_DSL_schema.json`): additive change — new optional `netting` object in `settings`. Requires ADR per project rules.
- **Compiler** (`compiler/compiler.py`): parse and validate `netting` block; pass through to `Settings` dataclass.
- **Engine dataclass** (`engine/strategy.py`): add `netting` field to `Settings`.
- **Runner** (`engine/runner.py`): ticker collection includes cash ticker; post-flatten netting step in the daily loop.
- **Downstream consumers**: output DataFrame may contain a ticker column (the cash ticker) that is not a leaf in the DSL tree. Consumers must already handle arbitrary ticker columns, so no breaking change.
- **Existing strategies**: unaffected — `netting` is optional and defaults to no-op.
