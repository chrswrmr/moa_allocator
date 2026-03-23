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
uv run python main.py --strategy strategies/momentum.moastrat.json
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
