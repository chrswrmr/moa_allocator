# compute-metric

**Module:** `moa_allocations/engine/algos/metrics.py`

Pure metric computation functions for the MoA allocation engine. Provides `compute_metric()` as the single public entry point, dispatching to 9 metric implementations. All functions are stateless with no side effects. Used by selection algos (condition evaluation, filter ranking) and weighting algos (inverse volatility).

---

## Requirements

### Requirement: compute_metric dispatcher
The module SHALL expose a single public function `compute_metric(series: np.ndarray, function: str, lookback: int) -> float` that dispatches to the correct metric implementation based on the `function` string. The dispatcher SHALL support exactly 9 function names: `current_price`, `cumulative_return`, `sma_price`, `ema_price`, `sma_return`, `max_drawdown`, `rsi`, `std_dev_price`, `std_dev_return`.

#### Scenario: Valid function name dispatches correctly
- **WHEN** `compute_metric` is called with `function="sma_price"`, a valid series, and `lookback=10`
- **THEN** it SHALL return the result of the `sma_price` implementation for that series and lookback

#### Scenario: Invalid function name raises error
- **WHEN** `compute_metric` is called with `function="unknown_metric"`
- **THEN** it SHALL raise a `ValueError` (not return `np.nan`)

#### Scenario: NaN returned for insufficient data
- **WHEN** `compute_metric` is called and `len(series)` is less than the minimum required for the given function
- **THEN** it SHALL return `np.nan` without calling the metric implementation

---

### Requirement: current_price returns today's close
The `current_price` function SHALL return `series[-1]` — the most recent closing price.

#### Scenario: Normal series
- **WHEN** `series = [100.0, 101.0, 102.0]` and any lookback
- **THEN** `compute_metric(series, "current_price", 0)` SHALL return `102.0`

#### Scenario: Single-element series
- **WHEN** `series = [50.0]`
- **THEN** it SHALL return `50.0`

#### Scenario: Empty series
- **WHEN** `series` is empty (`len(series) == 0`)
- **THEN** it SHALL return `np.nan`

---

### Requirement: cumulative_return over lookback window
The `cumulative_return` function SHALL compute `(series[-1] / series[-lookback]) - 1.0`.

#### Scenario: Known values
- **WHEN** `series = [100.0, 110.0, 105.0, 115.0]` and `lookback=3`
- **THEN** it SHALL return `(115.0 / 110.0) - 1.0` ≈ `0.04545`

#### Scenario: Insufficient data
- **WHEN** `len(series) < lookback`
- **THEN** it SHALL return `np.nan`

#### Scenario: Flat series
- **WHEN** all prices are identical
- **THEN** it SHALL return `0.0`

---

### Requirement: sma_price over lookback window
The `sma_price` function SHALL compute `np.mean(series[-lookback:])`.

#### Scenario: Known values
- **WHEN** `series = [10.0, 20.0, 30.0, 40.0, 50.0]` and `lookback=3`
- **THEN** it SHALL return `np.mean([30.0, 40.0, 50.0])` = `40.0`

#### Scenario: Insufficient data
- **WHEN** `len(series) < lookback`
- **THEN** it SHALL return `np.nan`

---

### Requirement: ema_price using pandas EWM
The `ema_price` function SHALL compute the exponential moving average using `pd.Series(series).ewm(span=lookback, adjust=False).mean().iloc[-1]`.

#### Scenario: Known values
- **WHEN** `series = [10.0, 20.0, 30.0, 40.0]` and `lookback=3`
- **THEN** it SHALL return the pandas EWM result with `span=3, adjust=False` evaluated at the last element

#### Scenario: Series shorter than span
- **WHEN** `len(series) < lookback` but `len(series) >= 1`
- **THEN** it SHALL still return a value (EMA computes with whatever data is available)

#### Scenario: Empty series
- **WHEN** `series` is empty
- **THEN** it SHALL return `np.nan`

---

### Requirement: sma_return over lookback window
The `sma_return` function SHALL compute daily returns as `np.diff(series) / series[:-1]`, then return `np.mean(returns[-lookback:])`.

#### Scenario: Known values
- **WHEN** `series = [100.0, 110.0, 105.0, 115.0]` and `lookback=2`
- **THEN** daily returns are `[0.1, -0.04545, 0.09524]`; it SHALL return `np.mean([-0.04545, 0.09524])` ≈ `0.02489`

#### Scenario: Insufficient data
- **WHEN** `len(series) < lookback + 1`
- **THEN** it SHALL return `np.nan`

---

### Requirement: max_drawdown over lookback window
The `max_drawdown` function SHALL compute the maximum peak-to-trough drawdown over `series[-lookback:]` using cumulative peak tracking. The result SHALL be negative or zero.

#### Scenario: Known drawdown
- **WHEN** `series = [100.0, 120.0, 90.0, 110.0]` and `lookback=4`
- **THEN** peak accumulates as `[100, 120, 120, 120]`, drawdowns are `[0.0, 0.0, -0.25, -0.0833]`; it SHALL return `-0.25`

#### Scenario: Monotonically increasing series
- **WHEN** series is strictly increasing
- **THEN** it SHALL return `0.0`

#### Scenario: Flat series
- **WHEN** all prices are identical
- **THEN** it SHALL return `0.0`

#### Scenario: Insufficient data
- **WHEN** `len(series) < lookback`
- **THEN** it SHALL return `np.nan`

---

### Requirement: rsi with Wilder smoothing
The `rsi` function SHALL compute RSI using Wilder's smoothing method over `lookback` returns derived from `series[-lookback - 1:]`. The result SHALL be in the range `[0, 100]`.

#### Scenario: Known values
- **WHEN** a series with known gains and losses is provided with `lookback=14`
- **THEN** it SHALL return the RSI computed via iterative Wilder smoothing: `avg_gain = (avg_gain * (lookback-1) + gain) / lookback` for each step

#### Scenario: All gains (no losses)
- **WHEN** every return is positive (`avg_loss == 0`)
- **THEN** it SHALL return `100.0`

#### Scenario: All losses (no gains)
- **WHEN** every return is negative (`avg_gain == 0`)
- **THEN** it SHALL return `0.0`

#### Scenario: Insufficient data
- **WHEN** `len(series) < lookback + 1`
- **THEN** it SHALL return `np.nan`

---

### Requirement: std_dev_price with sample standard deviation
The `std_dev_price` function SHALL compute `np.std(series[-lookback:], ddof=1)`.

#### Scenario: Known values
- **WHEN** `series = [10.0, 20.0, 30.0]` and `lookback=3`
- **THEN** it SHALL return `np.std([10.0, 20.0, 30.0], ddof=1)` = `10.0`

#### Scenario: Flat series
- **WHEN** all prices are identical
- **THEN** it SHALL return `0.0`

#### Scenario: Insufficient data
- **WHEN** `len(series) < lookback`
- **THEN** it SHALL return `np.nan`

---

### Requirement: std_dev_return with sample standard deviation
The `std_dev_return` function SHALL compute daily returns as `np.diff(series) / series[:-1]`, then return `np.std(returns[-lookback:], ddof=1)`.

#### Scenario: Known values
- **WHEN** `series = [100.0, 110.0, 105.0, 115.0]` and `lookback=3`
- **THEN** daily returns are `[0.1, -0.04545, 0.09524]`; it SHALL return `np.std([0.1, -0.04545, 0.09524], ddof=1)`

#### Scenario: Insufficient data
- **WHEN** `len(series) < lookback + 1`
- **THEN** it SHALL return `np.nan`

---

### Requirement: All metrics use today's close as reference
Every metric function SHALL treat `series[-1]` as today's close (`t`). The lookback window is `[t - lookback, t]` inclusive. No metric SHALL look beyond the end of the provided series.

#### Scenario: Lookback window alignment
- **WHEN** `series` has 200 elements and `lookback=50`
- **THEN** the metric SHALL operate on `series[-50:]` (the last 50 elements, ending at today's close)

---

### Requirement: Pure functions with no side effects
All metric functions and `compute_metric` SHALL be pure — no mutation of input arrays, no module-level state, no disk/network I/O, no imports from `compiler/` or engine runtime modules.

#### Scenario: Input array unchanged
- **WHEN** `compute_metric` is called with a series array
- **THEN** the original array SHALL not be modified

#### Scenario: No module-level state
- **WHEN** `compute_metric` is called twice with identical arguments
- **THEN** both calls SHALL return identical results regardless of prior calls
