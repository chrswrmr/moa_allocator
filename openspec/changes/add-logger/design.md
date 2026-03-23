## Context

The engine has zero diagnostic output. A developer verifying strategy correctness must inspect the output CSV and reverse-engineer which metrics fired, which children were selected, and which branches were taken. The codebase already has the data flowing through `compute_metric`, `_rank_and_select`, `_evaluate_condition_at_day`, and the Runner passes — it just never surfaces it.

Nodes carry both `id` (UUID) and `name` (optional, human-readable from DSL). The algo call sites (`_rank_and_select`, `_evaluate_condition_at_day`, `WeightInvVol.__call__`) have full node context — they know which node, which children, and which metric. `compute_metric()` is a pure function with no node context.

## Goals / Non-Goals

**Goals:**
- Every metric evaluation is traceable: function, lookback, series length, computed value
- Every selection decision is traceable: candidates, ranking, selected, dropped
- Every condition evaluation is traceable: LHS value, RHS value, comparator, result, branch taken — including each sub-day for `duration > 1`
- Every weighting result is traceable: method, per-child weights
- Runs produce a `.txt` log file in `logs/` that captures everything, searchable via grep with keyword anchors
- Structured data (`extra={}`) attached from day one for future JSON formatter swap

**Non-Goals:**
- JSON or structured formatter (future work — the `extra={}` hook enables it later)
- Logging inside `run()` (the library entry point in `__init__.py`) — only the CLI path gets handlers
- Performance-sensitive log gating (the engine is not latency-critical; always-on DEBUG in the file is acceptable)
- Log rotation or cleanup

## Decisions

### D1: Log at algo call sites, not inside `compute_metric()`

`compute_metric()` is a pure function — it has no knowledge of which node called it or why. The call sites (`_rank_and_select`, `_evaluate_condition_at_day`, `WeightInvVol.__call__`) have the full context: node identity, what decision the metric feeds, and the outcome.

**Alternative considered:** Adding a `context` parameter to `compute_metric()` for logging. Rejected: pollutes a clean, stateless function with cross-cutting concerns. The call sites already have all the information needed.

### D2: Node identification — `name` with `id` fallback

Nodes have `name` (human-readable, optional from DSL) and `id` (UUID). Log messages use `node.name or node.id` so logs are readable when names exist but always unambiguous.

### D3: Keyword anchors for grep-based search

Every DEBUG log message begins with an uppercase keyword:

| Keyword     | Emitted by           | Meaning                                      |
|-------------|----------------------|----------------------------------------------|
| `COMPILE`   | `compiler.py`        | Strategy file loaded, node tree built         |
| `REBALANCE` | `runner.py`          | Rebalance triggered on this date              |
| `METRIC`    | `selection.py`       | Single metric computation (node, ticker, value) |
| `SELECT`    | `selection.py`       | Selection result (selected/dropped children)  |
| `CONDITION` | `selection.py`       | Condition evaluation (LHS, RHS, result)       |
| `WEIGHT`    | `weighting.py`       | Weighting result (method, per-child weights)  |
| `NAV`       | `runner.py`          | Node NAV update in upward pass                |
| `ALLOC`     | `runner.py`          | Flattened global weight vector for the day    |

Non-rebalance days emit a single line: `t=2021-03-16  (no rebalance)`.

**Alternative considered:** Structured logging with a JSON formatter from the start. Rejected: the user wants grep-friendly plain text now. The `extra={}` dicts preserve the structured data for a future formatter swap with zero code changes.

### D4: Two handlers — file always captures everything

```
┌──────────────────────────────┐
│         main.py              │
│   logging.basicConfig(...)   │
├──────────────────────────────┤
│                              │
│   FileHandler (logs/*.txt)   │  ← always DEBUG, captures everything
│   StreamHandler (console)    │  ← INFO by default, DEBUG with --debug
│                              │
└──────────────────────────────┘
```

The log file always writes at DEBUG level regardless of the `--debug` flag. This means every run produces a full trace. The `--debug` flag only controls console verbosity.

**Rationale:** The developer's pain point is post-hoc verification ("was this run correct?"). Having the full trace always available avoids re-running with a debug flag.

### D5: Log file naming and location

- Directory: `logs/` (created at runtime, added to `.gitignore`)
- Filename: `<YYYYMMDD_HHMM>_<strategy-stem>_log.txt` — same timestamp and stem as the output CSV, with `_log` suffix
- Example: `logs/20240323_1430_spy_sma200_log.txt`

The timestamp is computed once in `main.py` and shared between the CSV path and log path.

### D6: Logger per module via `__name__`

Each module creates `logger = logging.getLogger(__name__)`. This gives natural hierarchy:

```
moa_allocations.compiler.compiler    → COMPILE events
moa_allocations.engine.runner        → REBALANCE, NAV, ALLOC events
moa_allocations.engine.algos.selection  → METRIC, SELECT, CONDITION events
moa_allocations.engine.algos.weighting  → WEIGHT events
```

`main` (the entry point) configures the root `moa_allocations` logger with both handlers.

### D7: `extra={}` convention for future structured output

Every DEBUG call includes an `extra` dict with the same data as the message. Example:

```python
logger.debug(
    "METRIC  node=%s  ticker=%s  fn=%s  lookback=%d  value=%.6f",
    node_label, ticker, function, lookback, value,
    extra={"node": node_label, "ticker": ticker, "fn": function,
           "lookback": lookback, "value": value}
)
```

The text formatter ignores `extra` fields. A future JSON formatter can read them directly from the LogRecord. No code changes needed to switch.

### D8: `--debug` flag in CLI

`main.py` adds `--debug` to the argparse parser. Default log level for console is INFO. With `--debug`, console switches to DEBUG.

**Alternative considered:** `--verbose` / `-v`. Rejected: `--debug` is more precise — there are exactly two levels, and the flag names the level it activates.

## Risks / Trade-offs

**[Log volume]** A 5-year weekly backtest on a 10-node strategy could produce 50K+ DEBUG lines per run. → Acceptable for a developer debugging tool. Files are small (a few MB). No rotation needed for v1.

**[Performance]** Always-on DEBUG logging adds string formatting overhead on every metric computation. → The engine is a batch backtest, not a real-time system. The overhead is negligible compared to numpy/pandas operations.

**[`extra={}` duplication]** Every DEBUG call duplicates data in the message string and the `extra` dict. → This is the standard Python logging pattern for forward-compatible structured logging. The duplication is in the call site, not in the output.

**[Test isolation]** Logging to files during tests could create stray `.txt` files. → Tests should not configure file handlers. Library code only emits; tests can capture via `caplog` fixture.
