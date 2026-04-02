## Purpose

Defines the `--json` flag behavior for the default run mode and structured error output on stdout.

**Module:** `main.py`
**Introduced:** cli-interface-upgrade

---

## Requirements

### Requirement: --json flag produces structured JSON for run mode

When `--json` is passed with the default run mode (no query flag), `main.py` SHALL output a JSON result on stdout after a successful run, instead of the plain `"Written: {path}"` message.

The JSON SHALL contain:
- `status`: `"ok"`
- `allocations_path`: absolute path to the written CSV file (string)
- `rows`: number of data rows in the allocations DataFrame (integer)
- `traded_tickers`: sorted list of traded tickers (AssetNode leaves, excluding XCASHX)
- `signal_tickers`: sorted list of signal-only tickers (condition tickers not in the traded set)

#### Scenario: Successful run with --json

- **WHEN** `--json` is passed with a valid strategy and the run completes
- **THEN** stdout SHALL contain `{"status": "ok", "allocations_path": "<path>", "rows": <n>, "traded_tickers": [...], "signal_tickers": [...]}` and exit code SHALL be 0

#### Scenario: allocations_path is absolute

- **WHEN** `--json` is passed and the run completes
- **THEN** the `allocations_path` value SHALL be an absolute filesystem path to the written CSV

#### Scenario: rows matches DataFrame length

- **WHEN** `--json` is passed and the engine produces a DataFrame with 252 rows
- **THEN** the `rows` value SHALL be `252`

---

### Requirement: --json run mode errors produce structured JSON

When `--json` is passed and the run fails with a caught exception, `main.py` SHALL output an error JSON on stdout with the appropriate exit code, instead of printing a traceback.

#### Scenario: DSLValidationError with --json

- **WHEN** `--json` is passed and `compile_strategy` raises `DSLValidationError(node_id="abc", node_name="my_node", message="bad config")`
- **THEN** stdout SHALL contain `{"status": "error", "code": 1, "valid": false, "errors": [{"node_id": "abc", "node_name": "my_node", "message": "bad config"}]}` and exit code SHALL be 1

#### Scenario: PriceDataError with --json

- **WHEN** `--json` is passed and a `PriceDataError` is raised
- **THEN** stdout SHALL contain `{"status": "error", "code": 2, "message": "<error message>"}` and exit code SHALL be 2

#### Scenario: Unexpected error with --json

- **WHEN** `--json` is passed and an unexpected exception is raised
- **THEN** stdout SHALL contain `{"status": "error", "code": 3, "message": "<error message>"}` and exit code SHALL be 3

---

### Requirement: Without --json, run mode preserves existing output

When `--json` is NOT passed and no query flag is used, `main.py` SHALL print `"Written: {output_path}"` on success, matching the current behavior. Errors without `--json` SHALL produce tracebacks on stderr as they do today.

#### Scenario: Default run without --json

- **WHEN** the run completes without `--json`
- **THEN** stdout SHALL print `"Written: {output_path}"` and no JSON SHALL be printed
