## Context

Phase 2 introduces algos and metrics. Selection algos (`IfCondition`, `TopN`, `BottomN`) and the inverse-volatility weighting algo all need to evaluate time-series metrics. This change (A1) builds the metric computation layer — a pure-function module with no engine dependencies — so that A2–A4 can call `compute_metric()` without implementing math inline.

The `moa_allocations/engine/algos/` package does not exist yet. This change creates it with `metrics.py` as the first module; subsequent changes (A2–A4) will add algo classes alongside it.

## Goals / Non-Goals

**Goals:**
- Implement `compute_metric(series, function, lookback) -> float` as the single entry point for all metric evaluation
- Implement all 9 metric functions per `metrics.spec.md` with exact formulas
- Return `np.nan` for insufficient data — no partial computation, no exceptions
- Keep all functions pure: no side effects, no state, no imports from `engine` or `compiler`

**Non-Goals:**
- Wiring `compute_metric` into algos (A2–A4)
- Caching or memoization of metric results (premature at this stage)
- Supporting custom/user-defined metric functions
- Lookback string parsing (`"200d"` → `200`) — that's the compiler's job

## Decisions

### D1: Dictionary dispatcher over match/case or class hierarchy

`compute_metric` will use a `dict[str, Callable]` mapping DSL function names to implementation functions.

**Why over match/case:** Dict lookup is O(1), trivially extensible, and avoids a long if/elif chain. Match/case (Python 3.10+) offers no real advantage here since the dispatch key is a plain string, not a structured pattern.

**Why over class hierarchy:** Each metric is a pure function with 1–3 lines of logic. Wrapping them in classes adds boilerplate with no benefit — there's no state, no polymorphic behavior, and no shared base logic worth inheriting.

### D2: Private functions, single public entry point

Each metric is a module-level `_function_name(series, lookback)` function. Only `compute_metric` is public.

**Why:** Callers should never bypass the dispatcher — it handles the NaN guard and name validation. Private functions also signal that internal signatures may change without notice.

### D3: pandas only for EMA, numpy for everything else

`ema_price` uses `pd.Series.ewm(span=..., adjust=False)` per the spec. All other functions use only numpy.

**Why:** EMA with Wilder-style smoothing is non-trivial to implement correctly with pure numpy (seed value handling, recursive smoothing). `pandas.ewm` is battle-tested and already a project dependency. The other 8 functions are simple numpy one-liners — adding pandas overhead there would be gratuitous.

### D4: NaN guard at dispatcher level

`compute_metric` checks `len(series) < min_required` and returns `np.nan` before calling the metric function. Each function documents its minimum but doesn't re-check.

**Why:** Centralizing the guard eliminates 9 copies of the same check and makes the NaN contract testable in one place. The per-function minimum is stored in a parallel dict or as a helper.

### D5: Invalid function name raises KeyError

If `function` is not in the dispatch dict, let the `KeyError` propagate (or wrap in `ValueError`). This is a programming error — the compiler validates DSL metric names at parse time, so an unknown name at runtime means a bug.

**Why not return NaN:** Silent failure would mask bugs in the compiler or DSL. Fail-fast is correct here.

## Risks / Trade-offs

- **[Floating-point precision]** → Mitigated by using numpy/pandas primitives and `ddof=1` consistently. Not writing custom accumulators. Tests will use `np.isclose` / `pytest.approx`.
- **[pandas import cost for one function]** → Acceptable; pandas is already a dependency for the broader engine. If profiling later shows import overhead matters, EMA can be rewritten in numpy.
- **[RSI Wilder smoothing is a loop]** → The loop over `lookback` returns is inherently sequential (each step depends on the prior). For typical lookbacks (14–200 days), this is negligible. Vectorization would require a full series warmup which is out of scope.
