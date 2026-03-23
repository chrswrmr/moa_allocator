## Why

The engine produces no diagnostic output. A developer verifying that a strategy works as intended — that metrics compute correctly, conditions branch the right way, and selections pick the right children — must manually inspect output CSVs and reverse-engineer what happened. A structured log file per run would make correctness verification immediate.

## What Changes

- Add Python stdlib `logging` to every module that participates in a run: `main.py`, `compiler.py`, `runner.py`, `selection.py`, `weighting.py`.
- Configure logging in `main.py` (the CLI entry point) following Python convention: library modules emit, entry point configures handlers.
- Write a `.txt` log file per run to a new `logs/` directory, named with the same timestamp+strategy stem as the output CSV.
- INFO tier: strategy loaded, tickers found, date window, simulation start/end, output path, elapsed time.
- DEBUG tier: per-day rebalance markers, per-node metric evaluations (with computed values), selection results (selected/dropped), weighting results, condition evaluations (LHS value, RHS value, comparator, result, branch taken — including every sub-day when `duration > 1`), NAV updates, flattened allocations. Non-rebalance days log only the date.
- Use keyword anchors in log messages (`REBALANCE`, `METRIC`, `SELECT`, `CONDITION`, `WEIGHT`, `NAV`, `ALLOC`) for grep-based searching.
- Include `extra={}` dicts on DEBUG calls from day one so a JSON formatter can be swapped in later without code changes.
- Add a `--debug` CLI flag: default level is INFO, `--debug` switches to DEBUG.

## Capabilities

### New Capabilities
- `logging`: Log configuration, handler setup, log file naming, level control, keyword-anchor format, and the `extra={}` structured-data convention.

### Modified Capabilities
_(none — existing module requirements do not change; logging calls are additive instrumentation with no effect on inputs, outputs, or control flow)_

## Impact

- **Files touched**: `main.py`, `moa_allocations/engine/runner.py`, `moa_allocations/engine/algos/selection.py`, `moa_allocations/engine/algos/weighting.py`, `moa_allocations/compiler/compiler.py`
- **New directory**: `logs/` (add to `.gitignore`)
- **Dependencies**: none (stdlib `logging` only)
- **Interfaces**: no changes to `Runner`, `compile_strategy`, `run()`, or any Algo signatures
- **Tests**: existing tests unaffected; new tests for log file creation and key log events
