# moa_allocator

Hierarchical portfolio allocation engine. Compiles a strategy DSL file into a daily ticker weight series.

## Usage

### 1. Add a strategy

Place your `.moastrat.json` file in the `strategies/` folder:

```
strategies/
  momentum.moastrat.json
```

### 2. Set the price data source

`moa_allocator` fetches historical prices from a `pidb_ib` database. Set the path before running:

```bash
export PIDB_IB_DB_PATH=/path/to/pidb_ib.db
```

### 3. Run

```bash
uv run python main.py --strategy strategies/momentum.moastrat.json
```

The output CSV is written to `output/` by default:

```
output/20260322_1435_momentum.csv
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
