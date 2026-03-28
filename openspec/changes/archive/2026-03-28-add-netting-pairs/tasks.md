## 1. ADR and DSL Schema

- [x] 1.1 Add ADR to `DECISIONS.md` documenting the netting DSL extension (required before schema change)
- [x] 1.2 Add optional `netting` property to the `settings` object in `moa_allocations/compiler/schema/moa_DSL_schema.json` with pairs array and cash_ticker fields, including leverage sign constraints (`exclusiveMinimum: 0` for long, `exclusiveMaximum: 0` for short)

## 2. Settings Dataclass

- [x] 2.1 Add `netting: dict | None` field to the `Settings` dataclass in `moa_allocations/engine/strategy.py` (default `None`)

## 3. Compiler — Semantic Validation

- [x] 3.1 In `compiler.py` `_validate_semantics()`, add netting validation: pair tickers must exist as `AssetNode` leaves in the tree, no ticker in multiple pairs, long_ticker != short_ticker within each pair. Skip if netting is absent.
- [x] 3.2 In `compiler.py`, parse the `netting` block from settings and pass it through to the `Settings` dataclass during construction

## 4. Runner — Ticker Collection and Init

- [x] 4.1 In `runner.py` or `__init__.py`, extend ticker collection to include `netting.cash_ticker` when configured and non-null
- [x] 4.2 Store the parsed netting config on the `Runner` instance for use during the simulation loop

## 5. Runner — Netting Transformation

- [x] 5.1 Implement `_apply_netting(weights: dict) -> dict` method on `Runner` that computes net exposure per pair, collapses to single-leg positions, and allocates freed weight to cash_ticker or XCASHX
- [x] 5.2 Integrate `_apply_netting()` into `Runner.run()` — call it on the flattened weight dict on every trading day, after `_flatten_weights()` and before the sum-to-one assertion

## 6. Output Assembly

- [x] 6.1 Update column ordering in `Runner.run()` to place netting cash ticker (if non-leaf and used) after DSL leaf columns but before XCASHX

## 7. Tests

- [x] 7.1 Unit tests for netting math: net long (1x), net short (3x inverse), perfectly offset, only one leg present, empty pairs list
- [x] 7.2 Unit tests for semantic validation: pair ticker not in tree, duplicate ticker across pairs, same long/short ticker, netting absent skips validation
- [x] 7.3 Integration test: full strategy compile + run with netting pairs, verify output DataFrame has correct netted weights and column ordering
- [x] 7.4 Run full test suite with `uv run pytest` and verify all tests pass
