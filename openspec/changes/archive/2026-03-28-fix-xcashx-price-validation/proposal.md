## Why

When `settings.netting.cash_ticker` is set to `"xcashx"` (the synthetic cash sentinel), the runner's ticker-collection step treats it as a real asset and demands price data for it — which doesn't exist, causing a `PriceDataError` at startup. The sentinel `XCASHX` is already handled throughout the engine without price data (hardcoded 0% return, dynamic injection), so requiring prices for it is incorrect behaviour.

## What Changes

- `collect_tickers()` SHALL skip adding `cash_ticker` to the required-ticker set when its value is the synthetic cash sentinel (`"xcashx"`, case-insensitive).
- The runner's missing-ticker validation therefore never fires for the sentinel, matching how `XCASHX` is handled everywhere else in the engine.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `runner-init`: The requirement that `netting.cash_ticker` is unconditionally added to the collected ticker set must gain an exception: if the value equals `"xcashx"` (case-insensitive), it SHALL be excluded from the set and treated as the built-in synthetic sentinel.

## Impact

- `moa_allocations/engine/runner.py` — `collect_tickers()` function (single guard added)
- `openspec/specs/runner-init/spec.md` — updated requirement + new scenario for the sentinel case
- No DSL schema changes, no breaking changes to existing strategy files
