## Purpose

Defines `main.py` as the runnable CLI entry point for `moa_allocations`. Accepts a strategy DSL file path and optional flags, runs the allocation engine or query modes, and writes the result as a timestamped CSV or JSON output.

**Module:** `main.py`, `moa_allocations/__main__.py`
**Introduced:** add-io-dirs
**Modified:** cli-interface-upgrade

---

## Requirements

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

---

### Requirement: Output filename is YYYYMMDD_HHMM_<stem>.csv

The output file SHALL be named `<YYYYMMDD>_<HHMM>_<stem>.csv` where:
- `YYYYMMDD_HHMM` is the local wall-clock timestamp at the moment `main.py` begins execution.
- `<stem>` is the filename stem of the `--strategy` argument (the filename without path or any extensions).

#### Scenario: Filename from strategy stem and run time

- **WHEN** `--strategy strategies/momentum.moastrat.json` is given and the run starts at 2026-03-22 14:35 local time
- **THEN** the output file SHALL be `<output_dir>/20260322_1435_momentum.csv`

#### Scenario: Strategy path contains directories

- **WHEN** `--strategy /some/deep/path/my_strat.moastrat.json` is given
- **THEN** the stem used SHALL be `my_strat` (only the filename portion, no directories, no extensions)

---

### Requirement: Output directory is created if absent

`main.py` SHALL create the output directory (and any missing parents) if it does not exist before writing the CSV.

#### Scenario: Output directory does not exist

- **WHEN** `--output /tmp/new_dir` is given and `/tmp/new_dir` does not exist
- **THEN** the directory SHALL be created and the CSV SHALL be written into it

#### Scenario: Output directory already exists

- **WHEN** the output directory already exists
- **THEN** `main.py` SHALL write the CSV without error

---

### Requirement: main.py invokes the lower-level engine API

`main.py` SHALL call `compile_strategy(strategy_path)` to obtain a `RootNode`, construct a `Runner(root, price_data)`, call `runner.run()` to obtain the allocations `DataFrame`, and write that DataFrame to the output CSV (`index=False`).

`main.py` SHALL NOT call `moa_allocations.run()` — it uses the lower-level API directly to control output path and naming.

#### Scenario: Successful end-to-end run

- **WHEN** `--strategy` points to a valid DSL file and price data is available
- **THEN** `main.py` SHALL write a CSV with columns `DATE, <ticker>, ...` to the output directory and exit with status 0

---

### Requirement: strategies/ directory exists as a conventional input location

The project SHALL contain a `strategies/` directory at the repository root. It is the conventional location for `.moastrat.json` input files. Its presence is a convention, not enforced by `main.py` — the `--strategy` flag accepts any path.

#### Scenario: strategies/ directory present in repository

- **WHEN** the repository is cloned
- **THEN** `strategies/` SHALL exist (tracked via `.gitkeep`)

---

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
