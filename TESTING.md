# Testing Strategy

## Philosophy

Tests are the primary correctness guarantee for a library with no UI. The engine must produce identical allocations for identical inputs — every time, on every machine. Tests are written against specs, not against implementation details.

---

## Test Structure

```
tests/
├── unit/
│   ├── test_compiler.py
│   ├── test_metrics.py
│   ├── test_algos.py
│   └── test_engine.py
├── integration/
│   ├── test_pipeline.py       ← full compile → run with synthetic data
│   └── test_reference.py      ← Borg 35r2 gold standard (requires pidb_ib)
└── fixtures/
    ├── borg_35r2.moastrat.json
    ├── borg_35r2_equity_curve.csv
    └── strategies/            ← minimal .moastrat.json files for unit/integration tests
```

---

## pidb_ib in Tests

The engine is decoupled from `pidb_ib` — `Runner` accepts an injected `pd.DataFrame`, not a DB connection. This means most tests need no database access.

| Test layer | Price data source |
|---|---|
| Unit tests (compiler, metrics, algos, engine) | Synthetic `pd.DataFrame` constructed inline |
| Pipeline integration tests | Synthetic `pd.DataFrame` from a `pytest` fixture |
| Reference strategy test | Real `pidb_ib` via `pidb_ib.get_prices()` |

For the `run()` entry point, stub `pidb_ib.get_prices()` using `monkeypatch` or a `pytest` fixture that returns a synthetic DataFrame. The reference strategy test is the only test that calls `pidb_ib` directly and requires a live DB connection.

---

## Test Markers

```python
@pytest.mark.unit          # fast, no I/O, no DB
@pytest.mark.integration   # synthetic data, no DB
@pytest.mark.slow          # requires pidb_ib; not run in CI by default
```

Run subsets:
```bash
uv run pytest -m "not slow"          # all tests except reference strategy
uv run pytest -m slow                # reference strategy only
uv run pytest tests/unit/            # unit tests only
```

---

## Unit Tests

Each module has its own test file. Tests are written against the spec, not the implementation.

### Compiler (`test_compiler.py`)

- Valid DSL compiles without error and returns a `RootNode`
- Each node type instantiates with correct attributes
- `DSLValidationError` raised for each invalid case defined in `compiler.spec.md` (wrong `version-dsl`, duplicate UUIDs, weights not summing to 1.0, etc.)
- Lookback strings convert correctly (`"200d"` → 200, `"4w"` → 20, `"3m"` → 63)

### Metrics (`test_metrics.py`)

Every function is verified against a hand-calculated result on a known series.

| Test case | What to assert |
|---|---|
| Correct value on known series | Each function matches hand-calculated result |
| Insufficient data | Returns `nan` for all lookback-required functions when `len(series) < min_length` |
| Flat price series | `std_dev_price` = 0.0, `max_drawdown` = 0.0, `cumulative_return` = 0.0 |
| All-gain RSI | Returns `100.0` |
| All-loss RSI | Returns `0.0` |
| Monotonically increasing series | `max_drawdown` returns `0.0` |
| Single-element series | `current_price` returns the value; all others return `nan` |

### Algos (`test_algos.py`)

Every Algo is tested against the cases in `algos.spec.md`:

| Test case | What to assert |
|---|---|
| Normal path | Returns `True`; `target.temp['weights']` sums to `1.0` |
| Empty selection | Returns `False`; engine sets node to 100% `XCASHX` |
| Single child | `WeightEqually` assigns `1.0`; `WeightInvVol` handles single-asset case |
| `SelectIfCondition` duration | Condition true for `duration - 1` days → routes to `false_branch` |
| `WeightInvVol` zero vol | Excludes asset; redistributes to remaining |
| `WeightInvVol` all zero vol | Returns `False` → `XCASHX` |

### Engine (`test_engine.py`)

- Upward Pass updates NAV correctly on a known price series
- Downward Pass produces correct weight vectors for each node type
- Rebalance frequency: weights carry forward on non-rebalance days
- Rebalance threshold: rebalance triggered only when drift >= threshold on scheduled days
- `PriceDataError` raised when tickers are missing or date range is insufficient

---

## Property-Based Tests (hypothesis)

Applied where exhaustive case enumeration is impractical.

| Property | What to assert |
|---|---|
| Weight output invariant | For any valid `target.temp['selected']`, all Weighting Algos produce weights summing to `1.0 ± 1e-9` |
| Metric NaN invariant | For any series shorter than `min_length`, `compute_metric()` returns `nan` |
| Leaf weight invariant | After a full Downward Pass on any valid compiled tree, all leaf weights sum to `1.0 ± 1e-9` |
| `WeightInvVol` invariant | For any set of positive vol values, output weights are non-negative and sum to `1.0 ± 1e-9` |

---

## Integration Tests

### Pipeline (`test_pipeline.py`)

Full compile → run using synthetic price data. No `pidb_ib` required.

- Output is a `pd.DataFrame` with a `DATE` column and uppercase ticker columns
- Every row sums to `1.0`
- Row count matches the number of trading days in `[start_date, end_date]`
- `output/allocations.csv` is written on every successful run
- `XCASHX` appears as a column when any AlgoStack halts during the backtest

Covers at minimum: a pure `weight` strategy, a `filter` strategy, an `if_else` strategy, and a nested strategy combining all node types.

### Reference Strategy (`test_reference.py`)

**Requires:** live `pidb_ib` connection + fixtures in `tests/fixtures/`.

Fixture files:
- `borg_35r2.moastrat.json` — the DSL definition of the reference strategy
- `borg_35r2_equity_curve.csv` — daily equity curve from the gold standard tool (considered correct)

Test:
1. Run `moa_allocations.run("tests/fixtures/borg_35r2.moastrat.json")`
2. Compute equity curve from output allocations
3. Assert daily return correlation > 0.999 against gold standard
4. Assert max daily allocation deviation < 0.01%

Marked `@pytest.mark.slow` — not run in CI by default. Run manually before releasing.

---

## Performance

```bash
uv run pytest tests/integration/test_pipeline.py -k "test_performance" -v
```

Assert: full backtest run on a 20-year window (~5000 trading days, ~60 tickers) completes in under 1 second. Measured via `time.perf_counter()` inside the test.

---

## Running Tests

```bash
uv run pytest                        # all tests except slow
uv run pytest -m "not slow"          # explicit exclude
uv run pytest -m slow                # reference strategy only (requires pidb_ib)
uv run pytest --cov=moa_allocations  # with coverage report
```
