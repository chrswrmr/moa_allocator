# metrics.spec.md

> ⚠️ Draft — created as a starting point. Finalize during the first OpenSpec change before implementing.

**Module:** `moa_allocations/engine/algos/metrics.py`  
**Version:** 1.0.0

---

## Responsibility

Compute time-series metrics over price or NAV series. Used by Selection Algos (condition evaluation, filter ranking) and Weighting Algos (inverse volatility). All functions are pure — no side effects, no state.

---

## Price Reference Convention

**All metrics use today's close (`t`) as the reference day.** The lookback window is `[t - lookback, t]` inclusive — `t` is always the most recent data point. This applies to every metric and indicator in this module without exception. See `DECISIONS.md` ADR-003 for rationale.

```
lookback window:  [t - lookback  ...  t-1  t]
                                          ↑
                                    always today's close
```

---

## Public Interface

```python
from moa_allocations.engine.algos.metrics import compute_metric

value: float = compute_metric(
    series: np.ndarray,   # price or return series, chronological order
    function: str,        # DSL metric function name
    lookback: int,        # trailing window in trading days
)
```

Returns a single `float` representing the metric value at the most recent point (today). Returns `np.nan` if insufficient data for the lookback window.

---

## Lookback Conversion

Lookback strings from the DSL are converted to integer trading days by the compiler before being passed to metrics:

| DSL suffix | Multiplier |
|---|---|
| `d` | × 1 |
| `w` | × 5 |
| `m` | × 21 |

Examples: `"200d"` → `200`, `"4w"` → `20`, `"3m"` → `63`.

---

## Metric Functions

### `current_price`

Today's closing price (`t`).

```python
return series[-1]  # price_data.loc[t, ticker]
```

**Lookback:** not used.  
**Returns `nan` if:** series is empty.

---

### `cumulative_return`

Total return over the lookback window.

```python
return (series[-1] / series[-lookback]) - 1.0
```

**Lookback:** required. Window = last `lookback` prices (inclusive of today).  
**Returns `nan` if:** `len(series) < lookback`.

---

### `sma_price`

Simple moving average of price over the lookback window.

```python
return np.mean(series[-lookback:])
```

**Lookback:** required.  
**Returns `nan` if:** `len(series) < lookback`.

---

### `ema_price`

Exponential moving average of price. Span = lookback days.

```python
# Uses pandas ewm for consistency with the rest of the stack
s = pd.Series(series)
return s.ewm(span=lookback, adjust=False).mean().iloc[-1]
```

**Lookback:** required (used as `span`).  
**Returns `nan` if:** series is empty.  
**Note:** EMA can be computed with fewer bars than `lookback`; returns a value as soon as any data exists. Only returns `nan` on empty input.

---

### `sma_return`

Simple moving average of daily returns over the lookback window.

```python
returns = np.diff(series) / series[:-1]   # daily % returns
return np.mean(returns[-lookback:])
```

**Lookback:** required. Window = last `lookback` daily returns.  
**Returns `nan` if:** `len(series) < lookback + 1` (need at least `lookback + 1` prices to compute `lookback` returns).

---

### `max_drawdown`

Maximum peak-to-trough drawdown over the lookback window. Returns a negative float.

```python
window = series[-lookback:]
peak = np.maximum.accumulate(window)
drawdowns = (window - peak) / peak
return float(np.min(drawdowns))
```

**Lookback:** required.  
**Returns `nan` if:** `len(series) < lookback`.  
**Sign convention:** always negative or zero (e.g. `-0.15` = 15% drawdown).

---

### `rsi`

Wilder's Relative Strength Index over the lookback window. Returns a value in `[0, 100]`.

```python
# Wilder smoothing (exponential with alpha = 1/lookback)
returns = np.diff(series[-lookback - 1:])
gains = np.where(returns > 0, returns, 0.0)
losses = np.where(returns < 0, -returns, 0.0)
avg_gain = gains[0]
avg_loss = losses[0]
for g, l in zip(gains[1:], losses[1:]):
    avg_gain = (avg_gain * (lookback - 1) + g) / lookback
    avg_loss = (avg_loss * (lookback - 1) + l) / lookback
if avg_loss == 0:
    return 100.0
rs = avg_gain / avg_loss
return 100.0 - (100.0 / (1.0 + rs))
```

**Lookback:** required. Needs `lookback + 1` prices to compute `lookback` returns.  
**Returns `nan` if:** `len(series) < lookback + 1`.

---

### `std_dev_price`

Rolling standard deviation of price over the lookback window.

```python
return float(np.std(series[-lookback:], ddof=1))
```

**Lookback:** required.  
**Returns `nan` if:** `len(series) < lookback`.  
**ddof:** 1 (sample standard deviation).

---

### `std_dev_return`

Rolling standard deviation of daily returns over the lookback window.

```python
returns = np.diff(series) / series[:-1]
return float(np.std(returns[-lookback:], ddof=1))
```

**Lookback:** required. Window = last `lookback` daily returns.  
**Returns `nan` if:** `len(series) < lookback + 1`.  
**ddof:** 1 (sample standard deviation).

---

## Summary Table

| `function` | Lookback required | Min series length | Output range |
|---|---|---|---|
| `current_price` | No | 1 | any float |
| `cumulative_return` | Yes | `lookback` | (-1, ∞) |
| `sma_price` | Yes | `lookback` | any float |
| `ema_price` | Yes (as span) | 1 | any float |
| `sma_return` | Yes | `lookback + 1` | (-1, ∞) |
| `max_drawdown` | Yes | `lookback` | [-1, 0] |
| `rsi` | Yes | `lookback + 1` | [0, 100] |
| `std_dev_price` | Yes | `lookback` | [0, ∞) |
| `std_dev_return` | Yes | `lookback + 1` | [0, ∞) |

---

## NaN Propagation

- If `compute_metric` returns `nan`, the calling Algo treats the asset as excluded for that day
- Partial lookback windows (series shorter than required) always return `nan` — no partial computation
- Exception: `ema_price` computes with whatever data is available (EMA by design)

---

## Testing Requirements

| Test case | What to assert |
|---|---|
| Correct value on known series | Verify each function against a hand-calculated result |
| Insufficient data | Returns `nan` for all functions requiring lookback when `len(series) < min_length` |
| Flat price series | `std_dev_price` = 0.0; `max_drawdown` = 0.0; `cumulative_return` = 0.0 |
| All-gain RSI | Returns `100.0` |
| All-loss RSI | Returns `0.0` |
| `max_drawdown` on monotonically increasing series | Returns `0.0` |
| Single-element series | `current_price` returns the value; all others return `nan` |
