## 1. Infrastructure — logging setup in `main.py`

- [x] 1.1 Add `--debug` flag to argparse in `main.py`
- [x] 1.2 Compute shared timestamp once; use it for both CSV filename and log filename
- [x] 1.3 Create `logs/` directory at runtime (like `output/`); configure FileHandler at `logs/<YYYYMMDD_HHMM>_<strategy-stem>_log.txt` with DEBUG level
- [x] 1.4 Configure StreamHandler on stderr; level INFO by default, DEBUG when `--debug` is set
- [x] 1.5 Attach both handlers to the `moa_allocations` logger with a shared format string (timestamp, logger name, level, message)
- [x] 1.6 Add INFO-level logs in `main.py`: after compilation (strategy path, ticker count, date range), before simulation start, after completion (output path, log path, elapsed time)
- [x] 1.7 Add `logs/` to `.gitignore`

## 2. COMPILE event — `compiler.py`

- [x] 2.1 Add `logger = logging.getLogger(__name__)` to `compiler.py`
- [x] 2.2 Emit `COMPILE` DEBUG log after successful tree build with strategy path and root node label; include `extra` dict

## 3. REBALANCE event — `runner.py`

- [x] 3.1 Add `logger = logging.getLogger(__name__)` to `runner.py`
- [x] 3.2 In `run()`, emit `REBALANCE` DEBUG log on rebalance days (date, t_idx) with `extra` dict
- [x] 3.3 In `run()`, emit single-line `t=<date>  (no rebalance)` DEBUG log on non-rebalance days

## 4. NAV and ALLOC events — `runner.py`

- [x] 4.1 In `_upward_pass()`, emit `NAV` DEBUG log for each node after nav_array update (node label, t_idx, nav value) with `extra` dict
- [x] 4.2 In `run()`, after `_flatten_weights()`, emit `ALLOC` DEBUG log with date and full weight map; include `extra` dict

## 5. METRIC, SELECT, CONDITION events — `selection.py`

- [x] 5.1 Add `logger = logging.getLogger(__name__)` to `selection.py`
- [x] 5.2 In `_rank_and_select()`, emit `METRIC` DEBUG log per child metric computation (node label, ticker, fn, lookback, value) with `extra` dict
- [x] 5.3 In `_rank_and_select()`, emit `SELECT` DEBUG log with selected/dropped child lists and `extra` dict
- [x] 5.4 In `SelectAll.__call__()`, emit `SELECT` DEBUG log listing all children as selected
- [x] 5.5 In `_evaluate_condition_at_day()`, emit `METRIC` DEBUG log for each LHS/RHS metric computation with `extra` dict
- [x] 5.6 In `_evaluate_condition_at_day()`, emit `CONDITION` DEBUG log per sub-day evaluation (LHS value, op, RHS value, result, day offset) with `extra` dict

## 6. WEIGHT event — `weighting.py`

- [x] 6.1 Add `logger = logging.getLogger(__name__)` to `weighting.py`
- [x] 6.2 In `WeightEqually.__call__()`, emit `WEIGHT` DEBUG log with method=equal and weight map; include `extra` dict
- [x] 6.3 In `WeightSpecified.__call__()`, emit `WEIGHT` DEBUG log with method=defined and weight map; include `extra` dict
- [x] 6.4 In `WeightInvVol.__call__()`, emit `WEIGHT` DEBUG log with method=inverse_volatility and weight map; include `extra` dict

## 7. Node label helper

- [x] 7.1 Add a `node_label(node)` helper (inline pattern or small utility) that returns `node.name or node.id`; use consistently across all log call sites

## 8. Tests

- [x] 8.1 Test that a run produces a log file at the expected path in `logs/`
- [x] 8.2 Test that the log file contains at least one occurrence of each keyword anchor (COMPILE, REBALANCE, METRIC, SELECT, CONDITION, WEIGHT, NAV, ALLOC)
- [x] 8.3 Test that `--debug` flag is accepted by argparse and does not error
- [x] 8.4 Test that library import without handler config produces no output (NullHandler behaviour)
