# Change Proposal Input: moa_allocator CLI Interface Upgrade

> Paste this into `/opsx:new` in the moa_allocator project.

## Prompt

Upgrade the CLI to serve as the primary interface contract for all callers (moa_shell backend, future AI agents, humans). The CLI `--help` must fully document inputs, outputs, errors, and exit codes.

## Current State

- Entry point: `main.py` (not `__main__.py` — cannot run via `python -m moa_allocator`)
- argparse with `--strategy`, `--output`, `--db`, `--debug`
- No structured stdout — only prints `"Written: {output_path}"` on success
- No explicit exit codes beyond 0/crash
- Output: CSV file written to disk, path printed to stdout
- No JSON output mode for programmatic consumption

## Required Changes

### 1. Module entry point

Add `moa_allocations/__main__.py` so `python -m moa_allocations` works (or `uv run python -m moa_allocations`). Keep `main.py` as a convenience wrapper if desired.

### 2. Comprehensive `--help`

The help text must cover everything a caller needs. Structure:

```
moa_allocations — Compile a .moastrat.json strategy and produce daily target weight allocations.

Usage:
  uv run python -m moa_allocations --strategy <path> [options]

Arguments:
  --strategy PATH          Path to .moastrat.json DSL file (required, except --list-indicators)
  --output DIR             Output directory for allocations CSV (default: output/)
  --db PATH                Path to pidb_ib SQLite database (default: C:/py/pidb_ib/data/pidb_ib.db)
  --debug                  Enable DEBUG-level console output
  --json                   Write result to stdout as JSON (only needed for run mode)

Query Modes (mutually exclusive, always output JSON — --json is implied):
  --validate           Validate DSL only — schema + semantic checks, no price fetch, no engine
  --tickers            Extract traded tickers and signal tickers from strategy tree
  --check-prices       Validate + verify all tickers exist in pidb_ib for date range (requires --db)
  --list-indicators    List all indicator functions the engine supports (no --strategy needed)

Default (no query flag): Run full pipeline — compile → fetch prices → engine → write CSV

Output (JSON on stdout):
  Run:               {"status": "ok", "allocations_path": "<path>", "rows": <n>, "traded_tickers": [...], "signal_tickers": [...]}
  --validate:        {"status": "ok", "valid": true}
  --tickers:         {"status": "ok", "traded_tickers": ["SPY", "TLT"], "signal_tickers": ["VIXY"]}
  --check-prices:    {"status": "ok", "prices_available": true}
  --list-indicators: {"status": "ok", "indicators": [{"name": "current_price", "requires_lookback": false}, ...]}

Exit Codes:
  0    Success
  1    DSL validation error (invalid .moastrat.json)
  2    Price data error (missing tickers or date range in pidb_ib)
  3    Unexpected error

Errors (with --json):
  {
    "status": "error",
    "code": 1,
    "valid": false,
    "errors": [
      {"node_id": "<id>", "node_name": "<name>", "message": "<text>"}
    ]
  }

  DSLValidationError carries node_id, node_name, message.
  Compiler raises on first error — errors array is always length 1 today.
  Array for forward compatibility (batch validation later).
```

### 3. Explicit exit codes

Map exception types to exit codes:
- `DSLValidationError` → exit 1
- `PriceDataError` → exit 2
- Any other exception → exit 3

### 4. Query modes

All query modes compile the strategy first (except `--list-indicators`). If compilation fails, they all return exit 1 with the same `DSLValidationError` format.

#### `--validate`

Compile and validate only. Runs JSON Schema validation and semantic checks via `compile_strategy(path)`. No price fetch, no engine.

- Exit 0 + `{"status": "ok", "valid": true}`. No additional metadata.
- Exit 1 + error details on invalid strategy
- No `--db` or `--output` required

This is what the moa_shell strategy editor calls before triggering a backtest.

#### `--tickers`

Extract strategy metadata from the compiled tree. No price fetch.

- `traded_tickers`: All leaf `asset` nodes in the strategy tree (under weight, filter, or if_else branches). These are the tickers that can receive allocations and appear as columns in the allocations CSV. Excludes `XCASHX`.
- `signal_tickers`: Tickers in `if_else` condition `lhs`/`rhs` and `filter` `sort_by` that are NOT also traded. Need price data but don't receive allocations. Empty array if all condition tickers are also traded.

```json
{"status": "ok", "traded_tickers": ["SPY", "TLT", "GLD"], "signal_tickers": ["VIXY"]}
```

#### `--check-prices`

Validate strategy + verify all tickers (traded + signal) exist in pidb_ib for the required date range including lookback. Requires `--db`. Pre-flight before a full run.

- Exit 0 + `{"status": "ok", "prices_available": true}` if all data present
- Exit 2 if data missing:

```json
{"status": "error", "code": 2, "prices_available": false, "missing_tickers": ["XYZ"], "missing_dates": {"SPY": ["2024-01-02", "2024-01-03"]}}
```

#### `--list-indicators`

List all indicator functions the engine supports. Static query — no `--strategy` needed.

Used by the strategy editor to populate dropdowns for conditions and filters. Keeps editor in sync with the engine without hardcoding.

```json
{
  "status": "ok",
  "indicators": [
    {"name": "current_price", "requires_lookback": false},
    {"name": "sma_price", "requires_lookback": true},
    {"name": "cumulative_return", "requires_lookback": true},
    {"name": "relative_strength_index", "requires_lookback": true},
    {"name": "standard_deviation", "requires_lookback": true},
    {"name": "moving_average", "requires_lookback": true}
  ]
}
```

### 5. stdout / stderr discipline

| Stream | Content | Example |
|--------|---------|---------|
| **stdout** | Result only — JSON when `--json`, human-readable path otherwise | `{"status": "ok", "valid": true}` |
| **stderr** | All log output (INFO, DEBUG), progress messages, unstructured error traces | `2026-04-02 INFO Compiling strategy...` |
| **file** | Detailed log (always DEBUG level) | `logs/<timestamp>_<strategy>_log.txt` |

Rule: stdout must be parseable by `json.loads()` when `--json` is passed. No log lines, no progress text, no warnings — only the result JSON. Everything else goes to stderr or log file.

### 6. DSLValidationError reference

`DSLValidationError` already exists in `moa_allocations/exceptions.py` with `(node_id, node_name, message)`. No changes to the exception class needed. Real messages produced by the compiler:

**File/parse errors** (node_id: `"root"`, node_name: `"settings"`):
- `"file not found: /path/to/strat.json"`
- `"invalid JSON: <parse error>"`
- `"missing required field 'version-dsl'"`
- `"unsupported version-dsl '2.0.0', expected '1.0.0'"`

**Settings validation** (node_id: `"root"`, node_name: `"settings"`):
- `"start_date (2025-12-31) must be before end_date (2025-01-02)"`
- `"rebalance_threshold must be between 0 and 1 (exclusive), got 1.5"`
- `"netting pair long_ticker and short_ticker are the same: 'SPY'"`
- `"netting pair ticker 'XYZ' is not a leaf in the strategy tree"`

**Node validation** (node_id: actual UUID, node_name: from DSL):
- `"custom_weights keys do not match children ids — missing keys: ['a-003']"`
- `"custom_weights sum to 0.800000, expected 1.0 ± 0.001"`
- `"select.count (5) exceeds children count (3)"`
- `"metric function 'sma_price' requires 'lookback' (condition lhs)"`

### 7. Public API functions

Each query mode must be backed by a public function in `moa_allocations/__init__.py`. The CLI is a thin wrapper — it parses args, calls the function, formats the output. The functions are the real interface; the CLI is one consumer.

```python
# moa_allocations/__init__.py

def run(strategy_path: str, ...) -> pd.DataFrame         # existing — unchanged
def validate(strategy_path: str) -> bool                  # raises DSLValidationError on failure
def get_tickers(strategy_path: str) -> dict               # {"traded_tickers": [...], "signal_tickers": [...]}
def check_prices(strategy_path: str, db_path: str) -> dict  # {"prices_available": True} or raises PriceDataError
def list_indicators() -> list[dict]                       # [{"name": "...", "requires_lookback": True}, ...]
```

This keeps the door open: if the CLI subprocess overhead ever becomes a problem, callers can import these directly. All logic lives here — the CLI just calls them and serializes to JSON.

## What NOT to change

- The existing `run()` function signature — extend, don't break
- The CSV output format
- The logging to file
- argparse library choice

## Acceptance Criteria

- `uv run python -m moa_allocations --help` prints full interface documentation
- `uv run python -m moa_allocations --strategy test.json --json` returns run result JSON with `traded_tickers` and `signal_tickers`
- `uv run python -m moa_allocations --strategy test.json --validate --json` returns `{"status": "ok", "valid": true}`
- `uv run python -m moa_allocations --strategy invalid.json --validate --json` returns exit 1 with error details
- `uv run python -m moa_allocations --strategy test.json --tickers --json` returns both ticker lists
- `uv run python -m moa_allocations --strategy test.json --check-prices --db path/to/db --json` returns prices_available or exit 2
- `uv run python -m moa_allocations --list-indicators --json` returns indicator list without `--strategy`
- All existing tests still pass
- `main.py` still works as before (backward compatible)
