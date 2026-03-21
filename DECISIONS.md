# Decision Log

Architectural and significant design decisions, recorded in the order they were made.
The purpose is to capture *why* a choice was made, not just what was chosen.
Agents must read this before proposing changes to settled areas.

---

## ADR-001 — bt-inspired architecture with full unitization

**Date:** 2026-03-20
**Status:** Accepted

### Context

`moa_allocations` needs a proven mental model for hierarchical portfolio allocation — nested strategies, regime switching, volatility-based weighting. The `bt` library implements exactly this via its Strategy Tree / AlgoStack pattern and is well understood. However, `bt` ties capital allocation tightly to the root node: dollars flow down the tree, and each node manages actual portfolio value. This is incompatible with the Borg Collective stack, where capital translation and order sizing are handled downstream by `bt_rebalancer` and `iba`.

### Options Considered

1. **Use `bt` directly** — wrap or extend `bt.Strategy` and `bt.Backtest`
2. **Custom re-implementation, capital-aware** — mirror bt's model including dollar-based allocation at the root
3. **Custom re-implementation, fully unitized** — preserve bt's structural concepts but operate entirely in weight space; defer capital translation to `bt_rebalancer`

### Decision

We chose **option 3 — custom re-implementation, fully unitized** because `moa_allocations` has a single responsibility: produce a weight series. Capital management is a separate concern handled downstream. Using `bt` directly would pull in unnecessary capital tracking complexity and couple the engine to bt's internal data model.

### Consequences

- ✅ Clean separation of concerns — `moa_allocations` outputs weights, `bt_rebalancer` handles capital
- ✅ Each node operates identically regardless of its depth in the tree — no special-casing for the root
- ✅ No dependency on `bt` internals; the implementation is fully owned and testable in isolation
- ⚠️ bt's built-in Algos cannot be reused — every Algo must be implemented from scratch
- ⚠️ bt's Backtest runner and reporting are not available — simulation loop and output are custom

### bt Concepts Preserved

The following bt design principles are **non-negotiable invariants** in this implementation:

| Concept | Invariant |
|---|---|
| **Fund of funds** | Every node is a self-contained strategy. It receives a notional allocation and distributes it among its children. It never knows its parent or siblings. |
| **AlgoStack is the only logic gate** | All selection and weighting decisions happen inside Algos. No allocation logic outside of `__call__`. |
| **Strict phase ordering** | The Upward Pass (NAV update) must complete fully before the Downward Pass (allocation) begins — on every single day. |
| **NAV encapsulation** | A node can only observe its direct children's NAV series. It cannot reach into grandchildren or across branches. |
| **Unitized NAV** | Every Strategy node maintains a synthetic price series starting at 1.0. This allows parent nodes to treat sub-strategies as single tickers for metric computation. |
| **Cash fallback** | If an AlgoStack returns `False` or selection is empty, the node's full allocation goes to `XCASHX`. No partial allocation is left unresolved. |

AlgoStack construction deviation: In bt, AlgoStacks are attached at Strategy construction time by the user directly in code. In moa_allocations there is no equivalent user construction step — the tree arrives from the compiler. Runner.__init__() is the substitution for that moment.

## ADR-002 — pandas + numpy + pandas-ta; no polars in moa_allocations

**Date:** 2026-03-20

**Status:** Accepted

### Context

The simulation loop is inherently sequential — day N depends on day N-1 (NAV, weight drift, duration conditions). It cannot be vectorized across time. Performance must therefore come from minimizing per-day cost, not from bulk columnar operations. Polars was initially considered for pre/post ETL, but `moa_allocations` processes at most a few thousand rows × ~60 tickers — a scale where polars offers no meaningful advantage over pandas and adds two format conversion steps (polars → pandas for pandas-ta, pandas → polars for output).

### Options Considered

1. **pandas throughout** — simple, consistent, but per-day `.iloc` access is slow in a tight loop
2. **polars for ETL + pandas for loop** — polars handles input/output, pandas handles the loop; adds complexity without meaningful speedup at this data scale
3. **pandas for I/O + numpy for loop + pandas-ta for indicators** — pre-compute all metric series before the loop; convert to numpy arrays for O(1) daily lookup; use pandas-ta for the full indicator catalogue

### Decision

We chose **option 3**. The simulation loop iterates over numpy arrays with O(1) metric lookups — no rolling window recalculation per day. pandas handles input and output where DatetimeIndex alignment is needed. pandas-ta provides the full indicator catalogue without requiring custom implementations. Polars is excluded entirely — it earns its place elsewhere in the Borg stack (pidb_ib, bt_rebalancer) but adds no value here.

### Consequences

- ✅ Tight simulation loop with minimal per-day overhead
- ✅ Full indicator catalogue via pandas-ta — adding new metrics requires no custom implementation
- ✅ No polars conversion overhead; one less dependency in this module
- ⚠️ pandas-ta is pandas-native — any future move to polars in the loop would require replacing the indicator layer

---

## ADR-003 — Price reference for metric computation: today's close (t)

**Date:** 2026-03-20
**Status:** Accepted

### Context

During the Downward Pass, Algos evaluate metrics (including `current_price`) to make allocation decisions. The question is whether these metrics are computed on today's close `t` or yesterday's close `t-1`. Using `t` introduces a slight lookahead bias — in live trading, today's close is not known before orders are placed. Using `t-1` is stricter but adds a one-day lag to all signals.

### Options Considered

1. **Use `t-1` (yesterday's close)** — no lookahead; decision made on yesterday's data, order executes at today's close
2. **Use `t` (today's close)** — minor lookahead bias; consistent with MOC (Market on Close) order execution where both decision and fill happen at the same close price

### Decision

We use **`t` (today's close)**. Orders are assumed to execute at the closing price, which is the same price used for metric computation. This is standard practice for daily close-to-close backtests and consistent with the Borg Collective's MOC order execution via `iba`.

### Consequences

- ✅ Simpler implementation — single price reference per day, no off-by-one index handling
- ✅ Consistent with MOC execution model in `iba`
- ⚠️ Slight lookahead bias — in practice, close price is unknown at order submission time intraday; acceptable for EOD strategies

---

## ADR-004 — NaN exclusion delegated entirely to pidb_ib

**Date:** 2026-03-21
**Status:** Accepted

### Context

An earlier design included per-day NaN exclusion logic in the engine:
a `nan_excluded` key written by `runner.py` during the Upward Pass and
read by every Algo during the Downward Pass. This created hidden coupling
between the engine and every Algo implementation via an untyped dict key
with no enforcement mechanism.

### Decision

The engine assumes all asset prices are valid floats for every ticker on
every trading day in the backtest window. NaN handling is `pidb_ib`'s
sole responsibility via forward-filling before data is returned. The
engine performs no per-day NaN checks and carries no `nan_excluded` state.

### Rationale

The data quality guarantee already exists in `pidb_ib`'s contract.
Enforcing it there is cleaner than compensating for it in the engine.
The `nan_excluded` approach required four implementation sites across
two modules (`runner.py`, `SelectAll`, `SelectTopN`/`SelectBottomN`,
`WeightSpecified`) with no type safety. Any future Algo that forgot to
check `nan_excluded` would silently produce wrong weights.

Synthetic price histories back to 2005 are constructed specifically to
eliminate genuine data gaps for the current ETF universe. There is no
active requirement for mid-backtest asset entry.

### Consequences

- ✅ Algos are simpler — no `nan_excluded` reads, no re-normalisation paths
- ✅ No hidden engine/Algo coupling via untyped temp dict keys
- ✅ Specs are self-contained — an agent implementing any Algo does not
     need to know about engine internals to implement correctly
- ✅ Failure mode is explicit — bad input from `pidb_ib` produces
     obviously wrong output, not silently adjusted weights
- ⚠️ Engine has no runtime safety net — a `pidb_ib` data quality bug
     produces wrong allocations with no engine-level error thrown

### Extension Point

If partial price histories become a requirement — for example, newly
listed ETFs entering the universe mid-backtest — NaN exclusion should
be re-introduced as a **typed interface on `StrategyNode`**, not as a
`temp` dict key. The correct model at that point is an explicit
`excluded_children: set[str]` attribute reset each Upward Pass, with
Algos receiving it as a typed parameter rather than reading from an
untyped dict.

---

<!-- Add new ADRs above this line, incrementing the number -->


