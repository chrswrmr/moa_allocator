## 1. Implementation

- [x] 1.1 In `collect_tickers()` (`moa_allocations/engine/runner.py`), add a guard so that `cash_ticker` is only added to the ticker set when `cash_ticker.upper() != "XCASHX"`

## 2. Spec Sync

- [x] 2.1 In `openspec/specs/runner-init/spec.md`, update the "Ticker collection from tree" requirement body to include the sentinel exception and add the three new scenarios from the delta spec

## 3. Tests

- [x] 3.1 Add a test in `tests/unit/test_runner_init.py`: `Runner` instantiates without error when `netting.cash_ticker == "xcashx"` and real asset tickers are present in `price_data`
- [x] 3.2 Add a test for uppercase variant: `cash_ticker == "XCASHX"` also excluded from required tickers
- [x] 3.3 Verify existing test for `cash_ticker == "SHV"` (real asset) still passes — sentinel guard must not affect real tickers

## 4. Verification

- [x] 4.1 Run `uv run pytest` — all tests pass
- [x] 4.2 Run `uv run python main.py --strategy strategies/risk_switch.moastrat.json` — simulation completes without `PriceDataError`
