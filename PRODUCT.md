# Product

## Problem Statement

Systematic ETF strategies require frequent rebalancing decisions driven by market signals — moving averages, momentum, volatility regimes. Today these decisions are either hardcoded in ad-hoc scripts or managed in visual tools like Composer.trade that lack programmatic control and deep backtesting transparency. There is no clean, local, spec-driven engine that takes a declarative strategy definition and returns verifiable daily allocations as a plain data structure.

## Goals

- **G1** — Accept any valid `.moastrat.json` strategy definition and return a complete daily allocation series without manual intervention
- **G2** — Fetch price data directly via the `pidb_ib` interface; the caller provides only the strategy file path
- **G3** — Support the full DSL node set: `settings`, `if_else`, `weight`, `filter`, `asset` — including nested regime sleeves and sub-strategy Unitized NAV
- **G4** — Produce output that `bt_rebalancer` and `iba` can consume directly without transformation

## Non-Goals

- Not a UI or visual strategy editor — that belongs to MoaEdge (Dark Matter shell)
- Not responsible for order generation or live trading — that is `iba`
- Not responsible for performance reporting — that is `bt_rebalancer` / QuantStats
- Not a data provider — price history is fetched from `pidb_ib`; `moa_allocations` does not store or cache price data across sessions (intra-backtest caching within a single `run()` call is permitted); the caller never prepares or passes price data.
- Will not support intraday resolution in this phase — daily bars only
- Not responsible for market calendar validation — `pidb_ib` guarantees every row is a valid trading day; `moa_allocations` trusts the input index and performs no holiday or weekend checks

## User

Single internal user: the Borg Collective trading system. `moa_allocations` is called programmatically — either from a CLI runner, from `bt_rebalancer` for backtesting, or from `iba` for live allocation decisions. There is no human interacting with this module directly.

## Success Criteria

- [ ] `run(strategy_path: str)` returns a correct `pd.DataFrame` for all five DSL node types including `settings`
- [ ] Output rows sum to `1.0` on every trading day; `XCASHX` (see [ARCHITECTURE.md](file:///c:/py/moa_allocator/ARCHITECTURE.md)) is used as the cash sentinel when no asset is selected (not invested)
- [ ] `DSLValidationError` is raised with node `id` and `name` for any invalid strategy definition
- [ ] `PriceDataError` is raised when required tickers are missing from the fetched price data
- [ ] All built-in Algos have unit tests covering: normal path, empty selection (`XCASHX` fallback), NaN exclusion
- [ ] A reference strategy (Borg 35r2 equivalent) produces allocations matching a known-good baseline
- [ ] Full backtest run completes in under 1 second (measured on a standard 20-year window, ~60 tickers)
- [ ] Output is written to `output/allocations.csv` on every successful `run()` call

---

## Roadmap

Each change is one OpenSpec unit. Starting point specs (in `openspec/changes/Starting_points/`) are fed into the first change of each phase as input and refined into finalized specs before implementation begins.

**Phase 1 — Compiler** `[input: compiler.spec.md]`
- [open] C1 — Node class hierarchy (`BaseNode`, `StrategyNode`, `SecurityNode`, `RootNode`, `Settings`)
- [open] C2 — JSON Schema validation + top-level structure parsing
- [open] C3 — Semantic validation (UUID uniqueness, weight sums, filter bounds, lookback rules)
- [open] C4 — Recursive tree instantiation + `DSLValidationError` + lookback conversion

**Phase 2 — Algos + Metrics** `[input: algos.spec.md + metrics.spec.md]`
- [open] A1 — `compute_metric()` + all 9 metric functions
- [open] A2 — `BaseAlgo` + `SelectAll` + `WeightEqually`
- [open] A3 — `SelectTopN` / `SelectBottomN` + `WeightInvVol`
- [open] A4 — `SelectIfCondition` + `WeightSpecified`

**Phase 3 — Engine** `[input: engine.spec.md]`
- [open] E1 — `Runner` init: AlgoStack construction, `pidb_ib` wiring, `PriceDataError`
- [open] E2 — Upward Pass: NAV update, rebalance frequency
- [open] E3 — Downward Pass: AlgoStack execution, `XCASHX` fallback
- [open] E4 — Global Weight Vector + output assembly (`DataFrame` + CSV)

**Phase 4 — Integration**
- [open] I1 — `run()` public entry point wiring compiler → engine → output
- [open] I2 — `bt_rebalancer` / `iba` integration (out of scope for this repo)

---

## Open Questions

- [ ] **Non-trading days:** `moa_allocations` will not validate the input index — `pidb_ib` is responsible for delivering clean trading-day-only rows. This must be documented as an explicit invariant in `pidb_ib`'s interface contract.
