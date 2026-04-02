## Why

The CLI is becoming the primary interface contract for all callers — moa_shell backend, future AI agents, and humans. Today it only supports a single "run" mode with no structured output, no explicit exit codes, and no `python -m` entry point. Every new caller has to guess the output format and parse unstructured stdout. Adding query modes and JSON output now means callers get a stable, machine-readable contract before the consumer base grows.

## What Changes

- Add `moa_allocations/__main__.py` so `python -m moa_allocations` works
- Add `--json` flag: structured JSON output on stdout for the run mode
- Add `--validate` query mode: compile and validate a strategy without running the engine
- Add `--tickers` query mode: extract traded and signal tickers from a compiled strategy
- Add `--check-prices` query mode: verify all required tickers exist in pidb_ib for the date range
- Add `--list-indicators` query mode: list all indicator functions the engine supports (no `--strategy` needed)
- Add `--debug` flag: enable DEBUG-level console output on stderr
- Enforce stdout/stderr discipline: stdout is result-only (JSON when `--json`), all logging goes to stderr
- Map exception types to explicit exit codes: `DSLValidationError` → 1, `PriceDataError` → 2, unexpected → 3
- Back each query mode with a public function in `moa_allocations/__init__.py` (`validate`, `get_tickers`, `check_prices`, `list_indicators`)
- Comprehensive `--help` that documents inputs, outputs, errors, and exit codes

## Capabilities

### New Capabilities

- `cli-query-modes`: The four query modes (`--validate`, `--tickers`, `--check-prices`, `--list-indicators`) — argument parsing, mutual exclusivity, JSON output schemas, exit code mapping, and the public API functions that back them
- `cli-json-output`: The `--json` flag for the default run mode — structured JSON result on stdout with `status`, `allocations_path`, `rows`, `traded_tickers`, `signal_tickers`

### Modified Capabilities

- `cli-entry-point`: Adding `__main__.py` module entry point, `--debug` flag, `--json` flag routing, stdout/stderr discipline, exit code mapping, and comprehensive `--help` text
- `run-entry-point`: Adding public API functions (`validate`, `get_tickers`, `check_prices`, `list_indicators`) alongside the existing `run()` function

## Impact

- **Code**: `main.py`, `moa_allocations/__init__.py` (new public functions), new `moa_allocations/__main__.py`
- **APIs**: New public functions become importable API surface — signature stability matters
- **Dependencies**: No new external dependencies. `pidb_ib` already used by the default price fetcher; `--check-prices` reuses the same path
- **Systems**: moa_shell backend will consume the JSON output contract — changes to JSON schemas after this ships are breaking for that caller
