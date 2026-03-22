## 1. Expose engine tree-inspection utilities

- [x] 1.1 Rename `_collect_tickers` → `collect_tickers` and `_compute_max_lookback` → `compute_max_lookback` in `moa_allocations/engine/runner.py` (drop underscore prefix)
- [x] 1.2 Update all internal call sites in `Runner.__init__()` to use the new names
- [x] 1.3 Export `collect_tickers` and `compute_max_lookback` from `moa_allocations/engine/__init__.py` (add to imports and `__all__`)
- [x] 1.4 Run existing engine tests to confirm rename didn't break anything

## 2. Default price fetcher

- [x] 2.1 Implement `_default_price_fetcher(tickers, start_date, end_date)` in `moa_allocations/__init__.py` — reads `PIDB_IB_DB_PATH` env var, raises `ValueError` if unset
- [x] 2.2 Add pidb_ib call: `PidbReader(db_path).get_matrix(symbols=tickers, columns=["close_d"], start=start_date, end=end_date)` with lazy import of `pidb_ib` inside the function body
- [x] 2.3 Add Polars-to-pandas conversion: `date` string column → `DatetimeIndex`, preserve uppercase ticker columns, ensure `float64` values

## 3. `run()` function

- [x] 3.1 Define `PriceFetcher` type alias: `Callable[[list[str], str, str], pd.DataFrame]`
- [x] 3.2 Implement `run(strategy_path: str, price_fetcher: PriceFetcher | None = None) -> pd.DataFrame` in `moa_allocations/__init__.py`
- [x] 3.3 Pipeline step 1: call `compile_strategy(strategy_path)`
- [x] 3.4 Pipeline step 2: call `collect_tickers(root)` and `compute_max_lookback(root)`
- [x] 3.5 Pipeline step 3: compute lookback-adjusted fetch start — `ceil(max_lookback * 7 / 5) + 10` calendar days before `settings.start_date`
- [x] 3.6 Pipeline step 4: call `price_fetcher(sorted_tickers, fetch_start_iso, end_date_iso)` (default to `_default_price_fetcher` if None)
- [x] 3.7 Pipeline steps 5–7: `Runner(root, price_data)` → `runner.run()` → return DataFrame

## 4. Tests

- [ ] 4.1 Test `run()` end-to-end with a custom `price_fetcher` (mock that returns a valid `pd.DataFrame`) — verify full pipeline executes and returns allocations
- [ ] 4.2 Test lookback date calculation: `max_lookback=200` → `ceil(200*7/5)+10 = 290` calendar days subtracted
- [ ] 4.3 Test lookback date calculation: `max_lookback=0` → 10 calendar days subtracted (buffer only)
- [ ] 4.4 Test ticker extraction: verify sorted uppercase list passed to fetcher
- [ ] 4.5 Test custom fetcher is used when provided (pidb_ib not imported)
- [ ] 4.6 Test error propagation: `DSLValidationError` from compiler passes through
- [ ] 4.7 Test error propagation: `PriceDataError` from Runner passes through
- [ ] 4.8 Test default fetcher raises `ValueError` when `PIDB_IB_DB_PATH` is unset
- [ ] 4.9 Run full test suite (`uv run pytest`)
