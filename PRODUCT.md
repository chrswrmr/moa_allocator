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

- [done] C1 — Node class hierarchy (`BaseNode`, `StrategyNode`, `SecurityNode`, `RootNode`, `Settings`)
  > **Files:** `moa_allocations/engine/node.py`, `moa_allocations/engine/strategy.py`, `moa_allocations/exceptions.py`
  > **Scope:** Create `BaseNode`, `StrategyNode` (holds `children`, `temp`, `perm`, `algo_stack`), `SecurityNode` (holds `ticker`), `RootNode` (holds `settings` + `root`), and `Settings` dataclass — all attributes per the Output Node Class Hierarchy section of `compiler.spec.md`. Also define `DSLValidationError(node_id, node_name, message)` and `PriceDataError(message)` in `exceptions.py`.
  > **Out of scope:** No parsing, no validation, no AlgoStack attachment — pure data structure only.
  > **Depends on:** nothing — this is the foundation for all other changes.

- [done] C2 — JSON Schema validation + top-level structure parsing
  > **Files:** `moa_allocations/compiler/compiler.py`, `moa_allocations/compiler/schema/moa_DSL_schema.json`
  > **Scope:** Implement the first two steps of `compile_strategy(path)`: load JSON from `path`, validate against `moa_DSL_schema.json` using `jsonschema` (Draft-07), parse top-level fields (`id`, `version-dsl`, `settings`, `root_node`). Raise `DSLValidationError(node_id="root", node_name="settings", message=...)` on any schema violation or wrong `version-dsl`. Copy `moa_DSL_schema.json` from `openspec/moa_strategy_DSL/` into `compiler/schema/`.
  > **Out of scope:** Semantic validation (C3), recursive node instantiation (C4).
  > **Depends on:** C1 (`DSLValidationError`).

- [done] C3 — Semantic validation
  > **Files:** `moa_allocations/compiler/compiler.py` (extend)
  > **Scope:** Implement semantic checks that run after JSON Schema validation passes, per the Semantic Validation Rules section of `compiler.spec.md`: UUID uniqueness across all nodes; `custom_weights` keys match child ids exactly and sum to `1.0 ± 0.001`; `select.count >= 1` and `<= len(children)`; lookback required for all metric functions except `current_price`; `start_date < end_date`; `rebalance_threshold` between 0 and 1 if set. Each violation raises `DSLValidationError` with the offending node's `id` and `name`.
  > **Out of scope:** Recursive node instantiation (C4).
  > **Depends on:** C2.

- [done] C4 — Recursive tree instantiation + lookback conversion
  > **Files:** `moa_allocations/compiler/compiler.py` (complete), `moa_allocations/compiler/__init__.py`
  > **Scope:** Implement the final step of `compile_strategy(path)`: recursively walk `root_node` and instantiate the node class hierarchy from C1. Convert all `time_offset` strings to integer trading days (`d×1`, `w×5`, `m×21`) on `Condition` and `sortMetric` objects. Return a fully linked `RootNode` with `settings` attached. Export `compile_strategy` from `compiler/__init__.py`. Never return a partially built tree — any error raises `DSLValidationError`.
  > **Out of scope:** AlgoStack attachment (E1).
  > **Depends on:** C1, C2, C3.

**Phase 2 — Algos + Metrics** `[input: algos.spec.md + metrics.spec.md]`

- [done] A1 — `compute_metric()` + all 9 metric functions
  > **Files:** `moa_allocations/engine/algos/metrics.py`, `moa_allocations/engine/algos/__init__.py`
  > **Scope:** Implement `compute_metric(series: np.ndarray, function: str, lookback: int) -> float` dispatcher and all 9 functions: `current_price`, `cumulative_return`, `sma_price`, `ema_price`, `sma_return`, `max_drawdown`, `rsi` (Wilder smoothing), `std_dev_price`, `std_dev_return`. All use today's close as reference (ADR-003). Returns `np.nan` when series length < minimum required. No side effects, no state. Exact implementations per `metrics.spec.md`.
  > **Out of scope:** Calling `compute_metric` from Algos (A2–A4).
  > **Depends on:** C1 (node structure context only — no hard import dependency).

- [done] A2 — `BaseAlgo` + `SelectAll` + `WeightEqually`
  > **Files:** `moa_allocations/engine/algos/base.py`, `moa_allocations/engine/algos/selection.py`, `moa_allocations/engine/algos/weighting.py`
  > **Scope:** Define `BaseAlgo` with `__call__(self, target: StrategyNode) -> bool` contract. Implement `SelectAll` (writes all child ids to `target.temp['selected']`, always returns `True`) and `WeightEqually` (distributes `1/n` to each selected child, writes to `target.temp['weights']`, always returns `True`). These are the AlgoStack for all `weight/equal` nodes.
  > **Out of scope:** Any Algo that calls `compute_metric` — those are A3/A4.
  > **Depends on:** C1, A1.

- [open] A3 — `SelectTopN` / `SelectBottomN` + `WeightInvVol`
  > **Files:** `moa_allocations/engine/algos/selection.py` (extend), `moa_allocations/engine/algos/weighting.py` (extend)
  > **Scope:** Implement `SelectTopN(n, metric, lookback)` and `SelectBottomN(n, metric, lookback)` — rank children by `compute_metric()` over their NAV/price series, select top/bottom N, write to `target.temp['selected']`. Implement `WeightInvVol(lookback)` — compute `std_dev_return` per selected child, weight inversely, normalise; exclude zero/NaN vol children; return `False` if all are excluded. Used by `filter` and `weight/inverse_volatility` nodes respectively.
  > **Out of scope:** Condition evaluation (A4).
  > **Depends on:** C1, A1, A2.

- [open] A4 — `SelectIfCondition` + `WeightSpecified`
  > **Files:** `moa_allocations/engine/algos/selection.py` (extend), `moa_allocations/engine/algos/weighting.py` (extend)
  > **Scope:** Implement `SelectIfCondition(conditions, logic_mode)` — evaluate each condition's `lhs [comparator] rhs` at every day in the `duration` trailing window; combine with `all`/`any`; write `true_branch.id` or `false_branch.id` to `target.temp['selected']`; always returns `True`. Implement `WeightSpecified(custom_weights)` — assign pre-validated weights from `custom_weights` dict directly to `target.temp['weights']`. Exact duration semantics per `algos.spec.md`.
  > **Out of scope:** AlgoStack construction and attachment (E1).
  > **Depends on:** C1, A1, A2.

**Phase 3 — Engine** `[input: engine.spec.md]`

- [open] E1 — `Runner` init: AlgoStack construction + `pidb_ib` wiring + `PriceDataError`
  > **Files:** `moa_allocations/engine/runner.py`, `moa_allocations/engine/__init__.py`
  > **Scope:** Implement `Runner.__init__(root: RootNode, price_data: pd.DataFrame)`. Traverse the compiled tree and attach the correct `AlgoStack` to each `StrategyNode` based on node type and parameters (per AlgoStack composition table in `algos.spec.md`). Pre-convert all price/NAV series to numpy arrays and store on `node.perm`. Validate all required tickers are present in `price_data.columns` and date range covers `[start_date - max_lookback, end_date]`; raise `PriceDataError` otherwise. Wire `pidb_ib.get_prices(tickers, start, end)` as the price source in `run()`.
  > **Out of scope:** Simulation loop (E2–E4).
  > **Depends on:** C1–C4, A1–A4.

- [open] E2 — Upward Pass: NAV update + rebalance frequency
  > **Files:** `moa_allocations/engine/runner.py` (extend)
  > **Scope:** Implement the Upward Pass for each trading day: update `node.perm['nav']` bottom-up using `nav[t] = nav[t-1] × (1 + weighted_return[t])`, initialised to `1.0` on `start_date`. For `if_else` nodes: update both branches every day; use active branch return only for the node's own NAV. Implement rebalance schedule logic (`daily` / `weekly` / `monthly`) and threshold drift check — on non-rebalance days, skip Downward Pass and carry prior weights forward.
  > **Out of scope:** Downward Pass execution (E3).
  > **Depends on:** E1.

- [open] E3 — Downward Pass: AlgoStack execution + `XCASHX` fallback
  > **Files:** `moa_allocations/engine/runner.py` (extend)
  > **Scope:** Implement the Downward Pass for each rebalance day: reset `node.temp` at start of each day; execute each `StrategyNode`'s `AlgoStack` top-down; normalise `node.temp['weights']` to sum to `1.0` after each stack; if any Algo returns `False` or selection is empty, set `node.temp['weights'] = {'XCASHX': 1.0}`. `XCASHX` is a virtual leaf with return `0.0` — no price series required.
  > **Out of scope:** Weight flattening and output (E4).
  > **Depends on:** E1, E2.

- [open] E4 — Global Weight Vector + output assembly
  > **Files:** `moa_allocations/engine/runner.py` (complete), `moa_allocations/engine/__init__.py`
  > **Scope:** After each Downward Pass, flatten local weights root → leaves: `global_weight(leaf) = ∏ local_weights along path`. Assert all leaf weights sum to `1.0`. Collect daily weight vectors into `pd.DataFrame` with `DATE` as first column, uppercase tickers in DSL leaf order, `XCASHX` last if present. Write to `output/allocations.csv` (create `output/` if absent). Export `Runner` from `engine/__init__.py`.
  > **Out of scope:** `run()` public entry point wiring (I1).
  > **Depends on:** E1, E2, E3.

**Phase 4 — Integration**

- [open] I1 — `run()` public entry point
  > **Files:** `moa_allocations/__init__.py`
  > **Scope:** Implement `run(strategy_path: str) -> pd.DataFrame` — the single public entry point. Call `compile_strategy(strategy_path)`, extract tickers and date range from `RootNode.settings`, fetch prices via `pidb_ib.get_prices(tickers, start, end)`, instantiate `Runner(root, price_data)`, call `runner.run()`, return the allocations DataFrame. This is the only place `pidb_ib` is called.
  > **Out of scope:** `bt_rebalancer` / `iba` integration.
  > **Depends on:** C1–C4, E1–E4.

- [open] I2 — `bt_rebalancer` / `iba` integration (out of scope for this repo)

---

## Open Questions

- [ ] **Non-trading days:** `moa_allocations` will not validate the input index — `pidb_ib` is responsible for delivering clean trading-day-only rows. This must be documented as an explicit invariant in `pidb_ib`'s interface contract.
