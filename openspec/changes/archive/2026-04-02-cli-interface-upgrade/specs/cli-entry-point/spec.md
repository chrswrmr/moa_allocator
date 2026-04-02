## ADDED Requirements

### Requirement: Module entry point via __main__.py

`moa_allocations/__main__.py` SHALL exist so that `python -m moa_allocations` invokes the CLI. It SHALL import and call the `main()` function from `main.py`.

#### Scenario: python -m moa_allocations works

- **WHEN** `python -m moa_allocations --strategy test.json` is run
- **THEN** the behavior SHALL be identical to running `python main.py --strategy test.json`

#### Scenario: __main__.py delegates to main.py

- **WHEN** `moa_allocations/__main__.py` is examined
- **THEN** it SHALL contain an import of `main` from `main` and a call to `main()` — no argument parsing or pipeline logic

---

### Requirement: Explicit exit codes mapped to exception types

`main.py` SHALL catch exceptions from the pipeline and map them to exit codes:
- `DSLValidationError` → `sys.exit(1)`
- `PriceDataError` → `sys.exit(2)`
- Any other `Exception` → `sys.exit(3)`

On success, `main()` SHALL exit with code 0 (implicit return).

#### Scenario: DSLValidationError exits with code 1

- **WHEN** `compile_strategy()` raises `DSLValidationError`
- **THEN** `main()` SHALL exit with code 1

#### Scenario: PriceDataError exits with code 2

- **WHEN** the price fetcher or Runner raises `PriceDataError`
- **THEN** `main()` SHALL exit with code 2

#### Scenario: Unexpected exception exits with code 3

- **WHEN** an unexpected exception (e.g., `RuntimeError`, `TypeError`) is raised during the pipeline
- **THEN** `main()` SHALL exit with code 3

#### Scenario: Successful run exits with code 0

- **WHEN** the full pipeline completes without error
- **THEN** `main()` SHALL exit with code 0

---

### Requirement: stdout/stderr discipline

All logging output (INFO, DEBUG, progress messages) SHALL go to stderr. stdout SHALL contain only the result — JSON when `--json` is active or a query mode is used, the `"Written: ..."` message otherwise.

The `StreamHandler` in `_setup_logging` SHALL explicitly write to `sys.stderr`.

#### Scenario: Logging does not pollute stdout

- **WHEN** `--json` is passed and the pipeline runs with logging enabled
- **THEN** `json.loads(stdout)` SHALL succeed — no log lines, progress text, or warnings SHALL appear on stdout

#### Scenario: Log output goes to stderr

- **WHEN** the pipeline runs with `--debug`
- **THEN** all DEBUG and INFO log lines SHALL appear on stderr

---

### Requirement: Comprehensive --help text

`main.py`'s argparse configuration SHALL produce `--help` output that documents:
- All arguments with descriptions and defaults
- All query modes and their purpose
- JSON output schema for each mode (run, validate, tickers, check-prices, list-indicators)
- Exit codes and their meanings
- Error JSON format

#### Scenario: --help covers all query modes

- **WHEN** `--help` is invoked
- **THEN** the output SHALL mention `--validate`, `--tickers`, `--check-prices`, and `--list-indicators` with descriptions

#### Scenario: --help documents exit codes

- **WHEN** `--help` is invoked
- **THEN** the output SHALL list exit codes 0, 1, 2, 3 with their meanings

---

### Requirement: --debug flag enables DEBUG console output

`--debug` SHALL set the stderr `StreamHandler` to `DEBUG` level. Without `--debug`, the `StreamHandler` SHALL use `INFO` level. The file handler SHALL always use `DEBUG` level regardless.

#### Scenario: Default console level is INFO

- **WHEN** `main.py` is invoked without `--debug`
- **THEN** the stderr console handler SHALL show INFO and above, not DEBUG

#### Scenario: --debug shows DEBUG on console

- **WHEN** `main.py` is invoked with `--debug`
- **THEN** the stderr console handler SHALL show DEBUG and above

## MODIFIED Requirements

### Requirement: CLI accepts --strategy and --output arguments

`main.py` SHALL accept command-line arguments via `argparse`:
- `--strategy <path>` (required, except when `--list-indicators` is used): path to a `.moastrat.json` DSL file.
- `--output <dir>` (optional): directory to write the result CSV. Defaults to `output/`.
- `--db <path>` (optional): path to the pidb_ib SQLite database. Defaults to `C:\py\pidb_ib\data\pidb_ib.db`.
- `--debug` (optional): enable DEBUG-level console output.
- `--json` (optional): produce structured JSON output on stdout for the run mode.

Query mode flags (mutually exclusive):
- `--validate`, `--tickers`, `--check-prices`, `--list-indicators`

#### Scenario: --strategy required, missing raises error

- **WHEN** `main.py` is invoked without `--strategy` and without `--list-indicators`
- **THEN** `argparse` SHALL print a usage error and exit with a non-zero status code

#### Scenario: --list-indicators without --strategy

- **WHEN** `main.py` is invoked with `--list-indicators` and no `--strategy`
- **THEN** the command SHALL succeed and return the indicator list

#### Scenario: --output defaults to output/

- **WHEN** `main.py` is invoked with `--strategy <path>` and no `--output`
- **THEN** the output directory SHALL be `output/`

#### Scenario: --output overrides default

- **WHEN** `main.py` is invoked with `--strategy <path> --output /tmp/results`
- **THEN** the output file SHALL be written inside `/tmp/results/`
