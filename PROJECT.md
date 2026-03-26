# moa_allocations

> Hierarchical portfolio allocation engine: takes a strategy DSL file and returns a daily ticker weight series.

## What This Is

`moa_allocations` is a pure Python computation library that compiles a `.moastrat.json` strategy definition into a recursive node tree, simulates daily portfolio allocation over a historical price series, and returns a date-indexed DataFrame of ticker weights. It has no UI and no API server. It connects directly to `pidb_ib` to fetch daily price data by ticker. The output is a CSV-compatible allocation table consumed downstream by `bt_rebalancer` and `iba`.

## Document Index

| File | Purpose |
|---|---|
| `PRODUCT.md` | Goals, non-goals, roadmap |
| `ARCHITECTURE.md` | System design, stack, conventions |
| `DECISIONS.md` | Decision log |
| `TESTING.md` | Testing strategy, structure, markers, and reference strategy baseline |
| `claude/rules/` | Agent guardrails and task protocol |
| `claude/skills/` | Reusable agent task instructions |
| `openspec/specs/` | Per-module specs (see Module Index below) |
| `openspec/moa_strategy_DSL/` | The JSON Schema for the strategy DSL, which is the main outside input into moa_allocator |

## Module Index

> Spec links currently point to `openspec/changes/Starting_points/` — draft specs used as input for the first OpenSpec changes. Once each change is implemented and archived, the finalized spec moves to `openspec/specs/` and the link below is updated.

| Module | Description | Spec |
|---|---|---|
| `compiler` | Validates and compiles `.moastrat.json` DSL into a Strategy Tree | [spec](openspec/changes/Starting_points/compiler.spec.md) |
| `engine` | Runs the two-pass daily simulation loop over the Strategy Tree | [spec](openspec/changes/Starting_points/engine.spec.md) |
| `algos` | Catalogue of built-in Selection and Weighting Algos | [spec](openspec/changes/Starting_points/algos.spec.md) |
| `metrics` | Metric function implementations (SMA, RSI, cumulative return, etc.) | [spec](openspec/changes/Starting_points/metrics.spec.md) |

## Running

```bash
# Run a strategy (uses default db path: C:\py\pidb_ib\data\pidb_ib.db)
uv run python main.py --strategy strategies/first.moastrat.json

# Override the database path
uv run python main.py --strategy strategies/spy_sma100.moastrat.json --db "D:\other\pidb_ib.db"

# Override the output directory (default: output/)
uv run python main.py --strategy strategies/spy_sma100.moastrat.json --output my_output/
```

Output is written to `output/<YYYYMMDD_HHMM>_<strategy-stem>.csv`.

> **Note:** `start_date` in the strategy file must be a real trading day, and there must be at least 200 trading days of price history available before it in the database.

---

## Agent Entry Point

Load `claude/rules/` before any task. Then load the relevant spec from the Module Index above.
