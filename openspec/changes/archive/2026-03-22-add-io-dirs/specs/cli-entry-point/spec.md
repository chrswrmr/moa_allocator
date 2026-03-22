## Purpose

Defines `main.py` as the runnable CLI entry point for `moa_allocations`. Accepts a strategy DSL file path and an optional output directory, runs the allocation engine, and writes the result as a timestamped CSV.

**Module:** `main.py`
**Introduced:** add-io-dirs

---

## ADDED Requirements

### Requirement: CLI accepts --strategy and --output arguments

`main.py` SHALL accept two command-line arguments via `argparse`:
- `--strategy <path>` (required): path to a `.moastrat.json` DSL file.
- `--output <dir>` (optional): directory to write the result CSV. Defaults to `output/`.

#### Scenario: --strategy required, missing raises error

- **WHEN** `main.py` is invoked without `--strategy`
- **THEN** `argparse` SHALL print a usage error and exit with a non-zero status code

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
- `<stem>` is the filename stem of the `--strategy` argument (the filename without path or extension).

#### Scenario: Filename from strategy stem and run time

- **WHEN** `--strategy strategies/momentum.moastrat.json` is given and the run starts at 2026-03-22 14:35 local time
- **THEN** the output file SHALL be `<output_dir>/20260322_1435_momentum.csv`

#### Scenario: Strategy path contains directories

- **WHEN** `--strategy /some/deep/path/my_strat.moastrat.json` is given
- **THEN** the stem used SHALL be `my_strat` (only the filename portion, no directories)

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
