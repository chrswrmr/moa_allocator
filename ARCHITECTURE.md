# Architecture

## System Overview

`moa_allocations` is a pure Python library with two internal stages: a **Compiler** that validates a `.moastrat.json` file against the DSL JSON Schema and instantiates a recursive Strategy Tree, and an **Engine** that simulates daily portfolio evolution over that tree using a two-pass (upward/downward) execution model. Price data is fetched directly from `pidb_ib` by ticker and date range. The single output is a date × ticker weight DataFrame written to both memory and CSV.

## Component Map

```
┌─────────────────────────────────────────┐
│              run()  [__init__.py]        │  ← public entry point
└────────────┬────────────────────────────┘
             │  fetch prices by ticker + date range
             ▼
       [ pidb_ib DB ]
             │
     ┌───────▼────────┐
     │   compiler/    │  .moastrat.json → Strategy Tree (RootNode)
     └───────┬────────┘
             │
     ┌───────▼────────┐
     │   engine/      │  Strategy Tree + price_data → daily weight vectors
     │   runner.py    │
     │   algos/       │
     └───────┬────────┘
             │
     ┌───────▼──────────────────┐
     │  allocations: DataFrame  │  DATE, SPY, BND, XCASHX, ...
     │  output/allocations.csv  │
     └──────────────────────────┘
```

## Components & Interfaces

### `compiler`

**Responsibility:** Parse, validate, and instantiate a `.moastrat.json` DSL file into a live Strategy Tree.  
**Consumes:** Path to `.moastrat.json` file; canonical `moa_DSL_schema.json` (version `1.0.0`); human-readable DSL reference `moa_Req_to_DSL.md`  
**Produces:** `RootNode` instance with fully linked child nodes  
**Boundary:** `compile_strategy(path: str) -> RootNode`  
**Errors:** `DSLValidationError(node_id, node_name, message)` on any schema or semantic violation

### `engine/runner`

**Responsibility:** Drive the daily simulation loop over a compiled Strategy Tree.  
**Consumes:** `RootNode` from compiler; `price_data: pd.DataFrame` from caller  
**Produces:** `allocations: pd.DataFrame` (DATE × ticker weights, rows sum to 1.0)  
**Boundary:** `Runner(root: RootNode, price_data: pd.DataFrame).run() -> pd.DataFrame`  
**Errors:** `PriceDataError` if required tickers are missing or date range is insufficient

### `engine/algos`

**Responsibility:** Atomic, callable units of selection and weighting logic executed per node per day. See [`algos.spec.md`](openspec/changes/Starting_points/algos.spec.md).

### `engine/metrics`

**Responsibility:** Compute time-series metrics (SMA, EMA, RSI, cumulative return, etc.) over price or NAV series. See [`metrics.spec.md`](openspec/changes/Starting_points/metrics.spec.md).

### `pidb_ib` (database dependency)

**Responsibility:** Supply total-return adjusted price history for all tickers in the strategy.  
**Called by:** `engine/runner.py` — fetches prices by ticker and date range at initialisation  
**Contract:** Returns `pd.DataFrame` with `DatetimeIndex`, uppercase ticker columns, float values, no NaN gaps within the backtest window, date range covering at least `[start_date - max_lookback, end_date]`  
**Boundary:** `pidb_ib.get_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame`

**documentation** [pidb_ib_API_access.md](helpful_docs\pidb_ib_API_access.md)

## Design Principles

`moa_allocations` is modelled on the `bt` library's "fund of funds" concept but implemented as a fully unitized custom engine. The following principles are architectural guardrails — any implementation that violates them is incorrect regardless of whether tests pass. See `DECISIONS.md` ADR-001 for the full rationale.

**P1 — Nodes are capital-blind**
No node knows the total invested capital or its own dollar value. Every node operates purely in weight space (0.0–1.0). Capital translation is deferred entirely to `bt_rebalancer`.

**P2 — Nodes are context-blind**
A node knows only its own children. It cannot access its parent, its siblings, or any other part of the tree. The only interface is `target` (the node itself).

**P3 — AlgoStack is the only logic gate**
All selection and weighting decisions happen inside Algos via `__call__`. No allocation logic lives outside of an Algo.

**P4 — Phase ordering is strict**
The Upward Pass must complete fully before the Downward Pass begins — on every day, without exception. No interleaving.

**P5 — NAV encapsulation**
A node may only observe its direct children's Unitized NAV series. It cannot reach into grandchildren or across branches.

**P6 — No unresolved allocation**
If an AlgoStack halts (`False`) or selection is empty, 100% of the node's allocation goes to `XCASHX`. Partial or null allocations are not permitted.

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.13+ | Ecosystem fit; `pandas` / `numpy` / `pandas-ta` all Python-native |
| Input / output | `pandas` | DatetimeIndex alignment; native input format from `pidb_ib`; CSV output |
| Simulation loop | `numpy` | Pre-computed metric arrays; tight day-by-day iteration with O(1) lookups |
| Technical indicators | `pandas-ta` | Full indicator catalogue (RSI, SMA, EMA, MACD, Bollinger etc.); pure pandas/numpy under the hood |
| Schema validation | `jsonschema` | Draft-07 compliance; validates against `moa_DSL_schema.json` |
| Packaging | `uv` | Consistent with the rest of the Borg Collective stack |
| Testing | `pytest` | Standard; pairs with `hypothesis` for property-based Algo edge case testing |

## Data Flow

1. **Compile** — `compile_strategy(path)` validates `.moastrat.json` against the JSON Schema and instantiates the Strategy Tree
2. **Pre-compute metrics** — before the loop, compute all required metric series (SMA, RSI, EMA, etc.) for all tickers upfront using `pandas-ta`; convert to numpy arrays for O(1) daily lookup
3. **Simulation loop — Upward Pass** — for each trading day, update Unitized NAV for every Strategy node bottom-up (leaves → root)
4. **Simulation loop — Downward Pass** — trigger each node's AlgoStack top-down (root → leaves); Algos look up pre-computed metrics, determine selection and weights, halting to `XCASHX` if the stack returns `False`
5. **Global Weight Vector** — flatten local weights along root → leaf paths; aggregate by ticker
6. **Output assembly** — collect daily weight vectors into `pd.DataFrame`; write to `output/allocations.csv`

---

## DSL Reference

| File | Purpose |
|---|---|
| `moa_allocations/compiler/schema/moa_DSL_schema.json` | Canonical JSON Schema (Draft-07, version `1.0.0`). Machine-readable source of truth for all node types, field names, types, and constraints. The compiler validates every `.moastrat.json` against this file. Do not modify without an ADR. |
| `moa_allocations/compiler/schema/moa_Req_to_DSL.md` | Human-readable DSL building blocks reference. Describes each node type, its parameters, position rules, and annotated examples. Use this to understand intent; use the JSON Schema to enforce it. |

---

## Conventions

### Folder Structure

```
moa_allocations/
├── claude/
│   ├── CLAUDE.md
│   ├── rules/
│   └── skills/
├── openspec/
│   ├── config.yaml
│   ├── moa_strategy_DSL/
│   │   ├── moa_DSL_schema.json
│   │   └── moa_Req_to_DSL.md
│   └── changes/
│       └── Starting_points/       ← draft specs; input for first changes; removed after each change is archived
│           ├── compiler.spec.md
│           ├── engine.spec.md
│           ├── algos.spec.md
│           └── metrics.spec.md
├── PROJECT.md
├── PRODUCT.md
├── ARCHITECTURE.md
├── DECISIONS.md
├── moa_allocations/
│   ├── __init__.py               ← run() entry point
│   ├── exceptions.py
│   ├── compiler/
│   │   ├── __init__.py
│   │   ├── compiler.py
│   │   └── schema/
│   │       └── moa_DSL_schema.json
│   └── engine/
│       ├── __init__.py
│       ├── node.py
│       ├── strategy.py
│       ├── asset.py
│       ├── runner.py
│       └── algos/
│           ├── __init__.py
│           ├── base.py
│           ├── selection.py
│           ├── weighting.py
│           └── metrics.py
└── tests/
    ├── unit/
    └── integration/
```

### Naming Conventions

- **Files:** `snake_case` for Python, `kebab-case` for config/docs
- **Specs:** `{module-name}.spec.md`
- **Classes:** `PascalCase`
- **Functions/variables:** `snake_case`
- **Constants:** `UPPER_SNAKE_CASE`
- **Tickers:** always uppercase strings (`"SPY"`, `"BND"`) — in DSL, in code, in output
- **Cash Sentinel:** `XCASHX_SENTINEL = "XCASHX"` — used when no asset is selected or an AlgoStack halts. Referenced by all specs.

### OpenSpec Workflow

**Core rule: no code without a spec.** If a spec does not exist, create it first.

#### Exploration
- `opsx-explore` — think through a new idea, no artifacts, no code

#### Planning
> No code — strictly thinking, writing, deciding.  
> Sequential — complete and review each step before starting the next.

- `opsx-new` — open a new change
- `opsx-proposal` — what and why
- `opsx-design` — how, architecture and interface decisions
- `opsx-specs` — detailed module specs, one spec at a time
- `opsx-tasks` — concrete agent tasks, one task list at a time

#### Execution
- `opsx-apply` — agent implements against tasks and specs
- → manual review, iterate back into proposal/design/specs/tasks if needed

#### Validation
- `tests` — run tests, iterate if needed
- `opsx-verify` — acceptance criteria check, iterate if needed

#### Closing
- `opsx-sync` — update `PROJECT.md`, `ARCHITECTURE.md`, `DECISIONS.md`
- `opsx-archive` — close the change, move artifacts
- `git commit` — done

### Commands

| Action | Command |
|---|---|
| Install | `uv sync` |
| Run | `uv run python -m moa_allocations` |
| Tests | `uv run pytest` |
| Lint | `uv run ruff check .` |

### Testing

- Unit tests in `tests/unit/`, integration tests in `tests/integration/`
- Each module has its own test file: `test_{module}.py`
- Agent testing rules are defined in `claude/rules/`

### Environment & Configuration

- No secrets — `moa_allocations` makes no network calls
- Output directory `output/` is created at runtime if absent — do not commit it
