## Context

`moa_allocations.run()` currently accepts an explicit `strategy_path` argument and the engine writes its output to a hardcoded `output/allocations.csv`. `main.py` is an empty stub with no CLI interface. There is no project-level convention for where strategy files live, and the output filename is not meaningful.

## Goals / Non-Goals

**Goals:**
- Add `strategies/` as a conventional input directory for `.moastrat.json` files.
- Wire `main.py` as a runnable CLI entry point: `uv run python main.py --strategy <path> [--output <dir>]`.
- Default output directory is the existing `output/` folder.
- Output filename: `YYYYMMDD_HHMM_<stem>.csv` where date/time is the run timestamp and stem is the strategy filename stem (e.g. `20260322_1435_momentum.csv`).
- Add a `README.md` section documenting the workflow.

**Non-Goals:**
- Batch processing of multiple strategy files.
- Renaming or replacing the existing `output/` directory.
- A `[project.scripts]` entry point (plain `uv run python main.py` is sufficient for now).
- Watching `strategies/` for changes.
- Changing the `run()` public API signature.

## Decisions

### D1: CSV write responsibility moves to `main.py`, not `Runner`

Currently `Runner.run()` writes `output/allocations.csv` itself. The output-assembly spec requires the engine to write CSV on every `run()` call.

**Decision**: Remove the file-write from `Runner.run()`. `Runner.run()` returns only the DataFrame. `main.py` is responsible for creating the output directory if absent and writing the file.

**Rationale**: The engine has no business knowing about project directory layout. Separating compute from persistence keeps `Runner` testable without touching the filesystem and lets the CLI control naming and destination. Tests already assert on the returned DataFrame and do not expect a file side-effect.

**Alternative considered**: Keep the write in `Runner` and parameterise the output path. Rejected — it bleeds I/O policy into the engine and complicates unit tests.

### D2: Output filename is `YYYYMMDD_HHMM_<stem>.csv`

`YYYYMMDD_HHMM` is the wall-clock timestamp at the moment `main.py` is invoked. `<stem>` is the filename stem of the `--strategy` argument (e.g. `momentum` from `momentum.moastrat.json`).

**Rationale**: The timestamp makes each run's output uniquely identifiable and sortable. Using the input filename stem keeps the connection to the source strategy obvious without requiring the engine to expose the DSL `id`.

### D3: `main.py` uses `argparse` with `--strategy` and `--output`

```
uv run python main.py --strategy strategies/momentum.moastrat.json
uv run python main.py --strategy strategies/momentum.moastrat.json --output /tmp/results
```

`--strategy` is required. `--output` defaults to `output/`.

**Rationale**: Flags are self-documenting and composable. The caller can point at any `.moastrat.json` file anywhere on disk; `strategies/` is a convention, not a constraint.

### D4: `main.py` uses the lower-level API (`compile_strategy` + `Runner`) directly

`main.py` does not call `run()`. It calls `compile_strategy()` to get the `RootNode`, constructs a `Runner`, calls `runner.run()`, and writes the returned DataFrame to the output path.

**Rationale**: `run()` abstracts away the `RootNode`, but `main.py` doesn't need it — the write is handled locally. Using the lower-level API avoids redundant work and keeps `run()` unchanged.

## Risks / Trade-offs

- **Breaking output side-effect**: Any caller relying on `Runner.run()` writing `output/allocations.csv` will no longer get that file. Mitigation: the output-assembly spec delta makes this explicit; existing tests do not assert on the file being written.
- **`output-assembly` spec delta required**: The spec currently mandates `output/allocations.csv` on every `run()` call. A delta spec is required to remove that requirement from the engine and document that write responsibility moves to the CLI.

## Migration Plan

1. Remove the CSV write from `Runner.run()` — return DataFrame only.
2. Update `output-assembly` spec (delta) to reflect removed write responsibility.
3. Create `strategies/` directory with `.gitkeep`.
4. Wire `main.py` with `argparse`.
5. Update `README.md` with usage instructions.
