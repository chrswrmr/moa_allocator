## Why

The engine has no conventional home for strategy DSL files (the input) or allocation CSVs (the output), leaving callers to manage paths ad hoc. Establishing `strategies/` and `allocations/` as standard project-level directories and wiring `main.py` to them makes the system immediately runnable end-to-end without any argument plumbing.

## What Changes

- Add `strategies/` directory at project root — the canonical location for `.moastrat.json` DSL input files.
- Add `allocations/` directory at project root — replaces the current `output/` directory as the write target for allocation CSVs. **BREAKING**: output path changes from `output/allocations.csv` to `allocations/<strategy-id>.csv`.
- Update `main.py` to batch-process all `.moastrat.json` files in `strategies/`, running each through `moa_allocations.run()` and writing the result to `allocations/<strategy-id>.csv`.

## Capabilities

### New Capabilities
- `cli-entry-point`: `main.py` discovers `.moastrat.json` files in `strategies/`, runs each, and writes allocation CSVs to `allocations/`. Covers the discovery loop, per-file run invocation, and output naming convention.

### Modified Capabilities
- `output-assembly`: Output path changes from `output/allocations.csv` to `allocations/<strategy-id>.csv` where `strategy-id` is derived from the DSL document's top-level `id` field.

## Impact

- `moa_allocations/__init__.py` (`run()`): must accept or return enough information for the caller to derive the output path (the strategy `id`).
- `moa_allocations/engine/runner.py`: output directory changes from `output/` to `allocations/` — or the write responsibility moves to the CLI.
- `main.py`: replace stub with discovery + run loop.
- `openspec/specs/output-assembly/spec.md`: delta spec required for the new path and naming.
- Existing `output/` directory at project root: can be removed or left; new runs will not write to it.
