# moa_allocator

Hierarchical portfolio allocation engine. Compiles a strategy DSL file into a daily ticker weight series.

## Usage

### 1. Add a strategy

Place your `.moastrat.json` file in the `strategies/` folder:

```
strategies/
  momentum.moastrat.json
```

### 2. Run

```bash
uv run python main.py --strategy strategies/risk_switch_daily.moastrat.json
```

The output CSV is written to `output/` by default:

```
output/20260322_1435_momentum.csv
```

`moa_allocator` fetches prices from a `pidb_ib` database. The default path is `C:\py\pidb_ib\data\pidb_ib.db`. Override it with `--db`:

```bash
uv run python main.py --strategy strategies/momentum.moastrat.json --db "D:\other\pidb_ib.db"
```

Use `--output` to write elsewhere:

```bash
uv run python main.py --strategy strategies/momentum.moastrat.json --output /tmp/results
```

### Output format

The CSV has one row per trading day with columns `DATE, TICKER1, TICKER2, ...`. Each row sums to `1.0`.

```
DATE,SPY,IWM
2024-01-02,0.5,0.5
2024-01-03,0.5,0.5
...
```

## Metrics

All metrics treat `series[-1]` as today's close. `lookback` is the trailing window in trading days. If the series is too short for the requested lookback, the metric returns `NaN` (which fails the condition and routes to the false branch).

| Metric | Formula | Notes |
|--------|---------|-------|
| `current_price` | `series[-1]` | No lookback required |
| `cumulative_return` | `series[-1] / series[-lookback] - 1` | Fractional return over the window |
| `sma_price` | `mean(series[-lookback:])` | Simple moving average of prices |
| `ema_price` | EWM with `span=lookback` | Exponential moving average; more weight on recent prices |
| `sma_return` | `mean(daily_returns[-lookback:])` | Average of daily percentage returns |
| `max_drawdown` | `min((price - running_peak) / running_peak)` over window | Negative value; e.g. `-0.10` = 10% drawdown |
| `rsi` | Wilder RSI | 0–100; above 70 overbought, below 30 oversold |
| `std_dev_price` | `std(series[-lookback:], ddof=1)` | Price standard deviation in currency units |
| `std_dev_return` | `std(daily_returns[-lookback:], ddof=1)` | Daily return standard deviation (fractional) |
