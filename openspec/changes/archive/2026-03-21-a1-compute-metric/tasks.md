## 1. Package scaffold

- [x] 1.1 Create `moa_allocations/engine/algos/` package with `__init__.py`
- [x] 1.2 Create `moa_allocations/engine/algos/metrics.py` with module docstring and imports (`numpy`, `pandas`)

## 2. Dispatcher and NaN guard

- [x] 2.1 Implement the `_MIN_LENGTH` dict mapping each function name to its minimum series length (per spec summary table)
- [x] 2.2 Implement the `_DISPATCH` dict mapping each function name to its private implementation function
- [x] 2.3 Implement `compute_metric(series, function, lookback)` — NaN guard check, dispatch lookup, `ValueError` on unknown name

## 3. Metric functions (no-lookback)

- [x] 3.1 Implement `_current_price(series, lookback)` — return `series[-1]`

## 4. Metric functions (price-based, lookback required)

- [x] 4.1 Implement `_cumulative_return(series, lookback)` — `(series[-1] / series[-lookback]) - 1.0`
- [x] 4.2 Implement `_sma_price(series, lookback)` — `np.mean(series[-lookback:])`
- [x] 4.3 Implement `_ema_price(series, lookback)` — `pd.Series(series).ewm(span=lookback, adjust=False).mean().iloc[-1]`
- [x] 4.4 Implement `_max_drawdown(series, lookback)` — cumulative peak, min drawdown ratio
- [x] 4.5 Implement `_std_dev_price(series, lookback)` — `np.std(series[-lookback:], ddof=1)`

## 5. Metric functions (return-based, lookback required)

- [x] 5.1 Implement `_sma_return(series, lookback)` — daily returns then `np.mean(returns[-lookback:])`
- [x] 5.2 Implement `_rsi(series, lookback)` — Wilder smoothing loop over `series[-lookback-1:]`
- [x] 5.3 Implement `_std_dev_return(series, lookback)` — daily returns then `np.std(returns[-lookback:], ddof=1)`

## 6. Export

- [x] 6.1 Add `compute_metric` to `moa_allocations/engine/algos/__init__.py` re-export

## 7. Tests

- [x] 7.1 Create `tests/test_metrics.py` with test fixtures (known series, expected values)
- [x] 7.2 Test each metric function against hand-calculated expected values (`pytest.approx`)
- [x] 7.3 Test NaN return for insufficient data on every function
- [x] 7.4 Test edge cases: empty series, single element, flat series, all-gain RSI (`100.0`), all-loss RSI (`0.0`), monotonically increasing max_drawdown (`0.0`)
- [x] 7.5 Test `ValueError` on invalid function name
- [x] 7.6 Test input array is not mutated after `compute_metric` call
- [x] 7.7 Run `uv run pytest` — all tests pass
