## Context

`main.py` is the only CLI entry point. It uses the lower-level compiler/engine API directly (not `run()`), has no structured output, and crashes with unhandled exceptions on failure. The package cannot be invoked via `python -m moa_allocations`. The public API in `__init__.py` exposes only `run()`.

The CLI needs to become a stable, machine-readable interface for moa_shell and future callers, while keeping backward compatibility with `main.py` and the existing `run()` function.

## Goals / Non-Goals

**Goals:**

- Make `python -m moa_allocations` work via `__main__.py`
- Add query modes (`--validate`, `--tickers`, `--check-prices`, `--list-indicators`) backed by public functions
- Structured JSON output on stdout when `--json` is passed
- Explicit exit codes mapped to exception types
- stdout/stderr separation: stdout = result only, stderr = all logging

**Non-Goals:**

- Changing the `run()` function signature (extend only)
- Changing the CSV output format
- Adding a REST/HTTP interface
- Batch validation (error array is length 1 today, array for forward compat)
- Adding check/validation APIs to pidb_ib itself

## Decisions

### D1: `__main__.py` delegates to `main.py`

`moa_allocations/__main__.py` imports and calls the `main()` function from `main.py`. All argument parsing and dispatch logic stays in `main.py`.

**Why:** `main.py` already has all the wiring. `__main__.py` is just the two-line bridge that makes `python -m` work. No code duplication.

**Alternative:** Move everything into `__main__.py` and make `main.py` import from it. Rejected — unnecessary churn, and `main.py` at the repo root is a clear convention.

### D2: `main.py` catches exceptions and maps to exit codes

Wrap the pipeline in `main()` with a top-level try/except that catches `DSLValidationError` → exit 1, `PriceDataError` → exit 2, `Exception` → exit 3. When `--json` is active, error details are written to stdout as JSON. When not, the existing crash behavior is preserved (traceback to stderr).

**Why:** Exit codes must be deterministic for programmatic callers. The mapping is simple and flat — no need for middleware or an error-handling framework.

**Alternative:** Decorator-based error handler. Rejected — over-engineering for three exception types.

### D3: Query modes are mutually exclusive argparse group

Add `--validate`, `--tickers`, `--check-prices`, `--list-indicators` as a mutually exclusive group in argparse. Query modes always produce JSON on stdout (`--json` is implied). The default (no flag) runs the full pipeline.

**Why:** argparse enforces mutual exclusivity natively. Implying `--json` for query modes avoids forcing callers to pass two flags for every query.

### D4: Separate `collect_traded_tickers` and `collect_signal_tickers` from existing `collect_tickers`

The existing `collect_tickers()` returns all tickers as a flat set. The `--tickers` mode needs to distinguish traded (asset leaf nodes) from signal (condition-only tickers). Add two new functions:

- `collect_traded_tickers(root) -> set[str]` — only AssetNode leaves (excluding XCASHX)
- `collect_signal_tickers(root) -> set[str]` — tickers in conditions/filters that are NOT in the traded set

Keep existing `collect_tickers()` unchanged — it returns the union and is used by `run()` and `Runner`.

**Why:** The distinction is a property of the compiled tree, so it belongs in `engine/runner.py` alongside `collect_tickers`. Breaking it into two functions avoids entangling the new logic with the existing one.

**Alternative:** Single function returning a dict `{"traded": [...], "signal": [...]}`. Rejected — two focused functions are more composable and the existing callers don't need the split.

### D5: Public API functions in `__init__.py` are thin wrappers

Each new function (`validate`, `get_tickers`, `check_prices`, `list_indicators`) lives in `__init__.py` alongside `run()`. They call the compiler and/or engine internals, then return simple Python types (bool, dict, list). They do NOT produce JSON — that's the CLI's job.

**Why:** Keeps the functions usable as a library API. JSON serialization is a presentation concern for the CLI layer only.

### D6: `--check-prices` reuses `_default_price_fetcher` with error inspection

`check_prices()` compiles the strategy, collects all tickers (traded + signal), computes the lookback-adjusted date range, and attempts a `get_matrix` call. It inspects the result for missing tickers and date gaps rather than doing a separate query.

**Why:** pidb_ib has no "check coverage" API — `get_matrix` is the only query surface. Doing a lightweight fetch and inspecting the result is the simplest correct approach. The fetch is cheap (single column, typically small date range).

### D7: `--list-indicators` reads from `_DISPATCH` in `metrics.py`

`list_indicators()` imports `_DISPATCH`, `_NEEDS_LOOKBACK_PRICES`, and `_NEEDS_LOOKBACK_RETURNS` from `moa_allocations.engine.algos.metrics` and builds the indicator list. A function requires lookback if it's in either lookback set.

**Why:** Single source of truth — the dispatch table already defines what the engine supports. No hardcoded list to keep in sync.

**Alternative:** Add a `list_indicators()` function inside `metrics.py`. Possible, but the logic is trivial (iterate `_DISPATCH`, check membership in lookback sets) and doesn't warrant adding public API surface to the metrics module.

### D8: Logging goes to stderr, stdout is result-only

Reconfigure `_setup_logging` so the `StreamHandler` writes to `sys.stderr` instead of the default `sys.stdout`. This is actually the default for `StreamHandler()`, but we make it explicit. File handler behavior is unchanged.

**Why:** stdout must be parseable by `json.loads()` when `--json` is passed. Any log line on stdout would break JSON parsing for callers.

## Risks / Trade-offs

**[Risk] `_DISPATCH` and lookback sets are private** → These are implementation details of `metrics.py`. If they get renamed or restructured, `list_indicators()` breaks. Mitigation: the metrics module is stable and internal — we control both sides. If it ever changes, `list_indicators()` is a one-line fix.

**[Risk] `--check-prices` does a real fetch, not a metadata query** → For large date ranges with many tickers, this could be slow. Mitigation: it fetches only `close_d` (one column) and the typical ticker count is small (3–10). If it becomes a problem, pidb_ib can later add a coverage-check API.

**[Risk] JSON output contract becomes hard to change** → Once moa_shell depends on the JSON schemas, any field rename or removal is breaking. Mitigation: start with the minimal fields specified in the proposal. The `status` field and error format are simple enough to be stable.

**[Trade-off] `main.py` grows in complexity** → It goes from a linear script to a dispatcher with error handling. Acceptable — the logic is still straightforward (parse args → dispatch to function → format output → set exit code).
