## ADDED Requirements

### Requirement: --validate mode compiles and validates strategy only

When `--validate` is passed, `main.py` SHALL call `validate(strategy_path)` and output the result as JSON on stdout. No price fetch, no engine run, no `--db` or `--output` required.

On success: exit 0 with `{"status": "ok", "valid": true}`.
On `DSLValidationError`: exit 1 with error details (see exit code mapping in cli-entry-point).

#### Scenario: Valid strategy

- **WHEN** `--validate` is passed with a valid `.moastrat.json`
- **THEN** stdout SHALL contain `{"status": "ok", "valid": true}` and exit code SHALL be 0

#### Scenario: Invalid strategy

- **WHEN** `--validate` is passed with an invalid `.moastrat.json` that triggers a DSLValidationError
- **THEN** exit code SHALL be 1 and stdout SHALL contain the error JSON with `node_id`, `node_name`, and `message`

#### Scenario: No price fetch or engine execution

- **WHEN** `--validate` is passed
- **THEN** no price data SHALL be fetched and no engine run SHALL occur, regardless of `--db` or `--output` values

---

### Requirement: --tickers mode extracts traded and signal tickers

When `--tickers` is passed, `main.py` SHALL call `get_tickers(strategy_path)` and output the result as JSON on stdout. No price fetch.

The result SHALL contain:
- `traded_tickers`: sorted list of all leaf AssetNode tickers in the strategy tree, excluding `XCASHX`. These are tickers that can receive allocations and appear as columns in the output CSV.
- `signal_tickers`: sorted list of tickers referenced in `if_else` condition `lhs`/`rhs` `asset` fields that are NOT in the traded set. These need price data but do not receive allocations. Empty list if all condition tickers are also traded.

#### Scenario: Strategy with separate signal tickers

- **WHEN** `--tickers` is passed with a strategy that has asset leaves `SPY`, `TLT`, `GLD` and an if_else condition referencing `VIXY`
- **THEN** stdout SHALL contain `{"status": "ok", "traded_tickers": ["GLD", "SPY", "TLT"], "signal_tickers": ["VIXY"]}`

#### Scenario: Strategy where all condition tickers are also traded

- **WHEN** `--tickers` is passed with a strategy where all if_else condition tickers are also asset leaves
- **THEN** `signal_tickers` SHALL be an empty list `[]`

#### Scenario: Strategy with XCASHX

- **WHEN** `--tickers` is passed with a strategy containing an `XCASHX` asset leaf
- **THEN** `XCASHX` SHALL NOT appear in `traded_tickers` or `signal_tickers`

#### Scenario: Invalid strategy

- **WHEN** `--tickers` is passed with an invalid strategy
- **THEN** exit code SHALL be 1 with the same DSLValidationError JSON format (compilation fails before ticker extraction)

---

### Requirement: --check-prices mode verifies price data availability

When `--check-prices` is passed, `main.py` SHALL call `check_prices(strategy_path, db_path)` and output the result as JSON on stdout. Requires `--db`. This compiles the strategy, collects all tickers (traded + signal), computes the lookback-adjusted date range, and verifies all tickers have data in pidb_ib for that range.

On success: exit 0 with `{"status": "ok", "prices_available": true}`.
On missing data: exit 2 with details.

#### Scenario: All price data available

- **WHEN** `--check-prices` is passed and all tickers have data for the full date range (including lookback)
- **THEN** stdout SHALL contain `{"status": "ok", "prices_available": true}` and exit code SHALL be 0

#### Scenario: Missing tickers

- **WHEN** `--check-prices` is passed and some tickers have no data at all in pidb_ib
- **THEN** exit code SHALL be 2 and stdout SHALL contain `{"status": "error", "code": 2, "prices_available": false, "missing_tickers": ["XYZ"]}` listing the missing tickers

#### Scenario: Missing dates for a ticker

- **WHEN** `--check-prices` is passed and a ticker exists but has gaps in the requested date range
- **THEN** exit code SHALL be 2 and stdout SHALL contain `{"status": "error", "code": 2, "prices_available": false, "missing_dates": {"SPY": ["2024-01-02"]}}` listing the affected tickers and missing dates

#### Scenario: Invalid strategy

- **WHEN** `--check-prices` is passed with an invalid strategy
- **THEN** exit code SHALL be 1 (DSLValidationError), not exit 2

---

### Requirement: --list-indicators mode lists supported indicator functions

When `--list-indicators` is passed, `main.py` SHALL call `list_indicators()` and output the result as JSON on stdout. No `--strategy` is required.

The result SHALL list every metric function registered in the engine's `_DISPATCH` table, with a `requires_lookback` boolean indicating whether the function needs a lookback window.

#### Scenario: List all indicators

- **WHEN** `--list-indicators` is passed (no `--strategy`)
- **THEN** stdout SHALL contain `{"status": "ok", "indicators": [...]}` where each entry has `name` (string) and `requires_lookback` (boolean), and exit code SHALL be 0

#### Scenario: current_price does not require lookback

- **WHEN** `--list-indicators` is passed
- **THEN** the indicator with `"name": "current_price"` SHALL have `"requires_lookback": false`

#### Scenario: sma_price requires lookback

- **WHEN** `--list-indicators` is passed
- **THEN** the indicator with `"name": "sma_price"` SHALL have `"requires_lookback": true`

#### Scenario: Indicator list matches engine dispatch table

- **WHEN** `--list-indicators` is called
- **THEN** the returned indicator names SHALL exactly match the keys of `_DISPATCH` in `moa_allocations.engine.algos.metrics` — no hardcoded list

---

### Requirement: Query modes are mutually exclusive

`--validate`, `--tickers`, `--check-prices`, and `--list-indicators` SHALL be mutually exclusive. argparse SHALL reject invocations with more than one query flag.

#### Scenario: Two query flags

- **WHEN** `--validate` and `--tickers` are both passed
- **THEN** argparse SHALL print a usage error and exit with a non-zero status

---

### Requirement: Query modes imply JSON output

All query modes (`--validate`, `--tickers`, `--check-prices`, `--list-indicators`) SHALL always produce JSON on stdout. The `--json` flag is implied and does not need to be passed.

#### Scenario: Query mode without --json flag

- **WHEN** `--validate` is passed without `--json`
- **THEN** stdout SHALL still contain valid JSON output
