## Context

`Runner.run()` currently executes the Upward Pass (NAV update) and Downward Pass (AlgoStack execution) for each trading day but produces no output. After the Downward Pass, each `StrategyNode` holds `temp['weights']` — a dict mapping child IDs to local weight fractions. These local weights must be flattened into global leaf-level weights and assembled into a DataFrame.

The existing `run()` method iterates `_sim_dates`, calls `_upward_pass()`, and executes the Downward Pass on rebalance days. The flattening step slots in immediately after the Downward Pass within the same day loop. On non-rebalance days, prior weights carry forward — this means the prior day's global weight vector is reused.

## Goals / Non-Goals

**Goals:**
- Flatten local `temp['weights']` from root to leaves into a single global weight vector per day
- Assert leaf weights sum to `1.0` on every trading day
- Return a `pd.DataFrame` from `run()` with columns in DSL leaf order, `XCASHX` last
- Write the DataFrame to `output/allocations.csv`

**Non-Goals:**
- Wiring `run()` as a public entry point with `compile_strategy` and `pidb_ib` (that is I1)
- Performance optimisation beyond what the spec requires (< 1s for 20-year, ~60 tickers)
- Handling `XCASHX` as a real ticker with price data — it remains virtual with return `0.0`

## Decisions

### 1. Flatten via recursive DFS, not BFS

**Choice:** DFS walk from `root.root`, multiplying parent's global weight by each child's local weight as we descend. Leaf nodes accumulate into a flat `dict[str, float]`.

**Why over BFS:** DFS naturally carries the cumulative product down each path. BFS would require storing partial products per node and a second pass. DFS is simpler and matches the tree's top-down semantics.

**`if_else` handling:** Only the selected branch (the single ID in `temp['selected']`) receives weight. The unselected branch gets `0.0` — its children do not appear in the output (or appear with weight `0.0`).

**`XCASHX` handling:** When `temp['weights']` contains `{'XCASHX': 1.0}`, the DFS adds `1.0 × parent_global_weight` to the `XCASHX` accumulator. `XCASHX` is not a tree node — it is accumulated as a special key.

### 2. DSL leaf order determined once at init

**Choice:** Collect leaf tickers in DSL order (left-to-right DFS of the compiled tree) once during `__init__` and store as `self._leaf_order: list[str]`. `XCASHX` is appended at the end if it ever appears during the simulation.

**Why:** The spec requires uppercase tickers in DSL leaf order with `XCASHX` last. Computing this once avoids re-traversal each day.

### 3. Carry forward via copying the prior global vector

**Choice:** On non-rebalance days, copy the previous day's global weight vector directly. No flattening runs — there is no Downward Pass, so `temp['weights']` is stale.

**Why:** The Upward Pass still runs (NAV updates), but weights are frozen until the next rebalance. Copying the prior vector is both correct and avoids unnecessary computation.

### 4. Sum-to-one assertion with tolerance

**Choice:** `assert abs(sum(weights.values()) - 1.0) < 1e-9` after flattening each day.

**Why:** Floating-point multiplication across tree depth can introduce drift. A tight tolerance (`1e-9`) catches real bugs while allowing for IEEE 754 rounding.

### 5. DataFrame assembly after the loop

**Choice:** Collect daily weight vectors into a list of dicts during the simulation loop. After the loop completes, construct a single `pd.DataFrame` from the list with column order `['DATE'] + leaf_order`.

**Why:** Building the DataFrame row-by-row inside the loop is slow (`O(n²)` DataFrame concat). Collecting dicts and constructing once is `O(n)`.

### 6. CSV write with `output/` directory creation

**Choice:** Use `pathlib.Path("output").mkdir(exist_ok=True)` then `df.to_csv("output/allocations.csv", index=False)`.

**Why:** Simple, idempotent. No external dependencies. The path is relative to CWD, matching the spec.

## Risks / Trade-offs

- **[Deep trees amplify float drift]** → Each multiplication introduces ~`1e-16` error (machine epsilon). Even at depth 1000 the cumulative drift is ~`1e-13`, well within the `1e-9` tolerance. Not a practical concern.
- **[`XCASHX` column presence is dynamic]** → `XCASHX` only appears if at least one day routes weight to it. If no day ever triggers `XCASHX`, the column is absent. This matches the spec ("if present").
- **[CWD-relative output path]** → `output/allocations.csv` is relative to CWD, not to the project root. This is by spec design and matches how `bt_rebalancer` expects to find it.
