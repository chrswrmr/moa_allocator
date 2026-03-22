## Purpose

Defines the calendar-based rebalance gating logic that determines whether the Downward Pass executes on a given trading day. Threshold drift checking is deferred to `moa_rebalancer` (ADR-005).

**Module:** `moa_allocations/engine/runner.py`
**Introduced:** e2-upward-pass

---

## Requirements

### Requirement: Rebalance day classification

The engine SHALL provide a function `_is_rebalance_day(current_date, prev_date, frequency) -> bool` that determines whether `current_date` is a rebalance day based on the `rebalance_frequency` setting.

| `frequency` | Rule |
|---|---|
| `"daily"` | Always returns `True` |
| `"weekly"` | Returns `True` when `current_date` and `prev_date` fall in different ISO calendar weeks |
| `"monthly"` | Returns `True` when `current_date` and `prev_date` fall in different calendar months |

#### Scenario: Daily frequency — every day rebalances
- **WHEN** `frequency` is `"daily"` and `current_date` is any trading day
- **THEN** `_is_rebalance_day` SHALL return `True`

#### Scenario: Weekly frequency — new week triggers rebalance
- **WHEN** `frequency` is `"weekly"`, `prev_date` is Friday 2024-01-05 (week 1), and `current_date` is Monday 2024-01-08 (week 2)
- **THEN** `_is_rebalance_day` SHALL return `True`

#### Scenario: Weekly frequency — same week does not rebalance
- **WHEN** `frequency` is `"weekly"`, `prev_date` is Monday 2024-01-08, and `current_date` is Tuesday 2024-01-09 (both week 2)
- **THEN** `_is_rebalance_day` SHALL return `False`

#### Scenario: Monthly frequency — new month triggers rebalance
- **WHEN** `frequency` is `"monthly"`, `prev_date` is 2024-01-31, and `current_date` is 2024-02-01
- **THEN** `_is_rebalance_day` SHALL return `True`

#### Scenario: Monthly frequency — same month does not rebalance
- **WHEN** `frequency` is `"monthly"`, `prev_date` is 2024-02-01, and `current_date` is 2024-02-05
- **THEN** `_is_rebalance_day` SHALL return `False`

#### Scenario: Year boundary with weekly frequency
- **WHEN** `frequency` is `"weekly"`, `prev_date` is 2024-12-31 (ISO week 1 of 2025), and `current_date` is 2025-01-02 (also ISO week 1 of 2025)
- **THEN** `_is_rebalance_day` SHALL return `False` (same ISO week despite calendar year change)

---

### Requirement: Day 0 is always a rebalance day

The first simulation day (`t_idx == 0`) SHALL always be treated as a rebalance day, regardless of the `rebalance_frequency` setting. This is necessary to establish initial weights via the Downward Pass.

#### Scenario: Monthly frequency on day 0
- **WHEN** `t_idx == 0` and `rebalance_frequency` is `"monthly"`
- **THEN** the Downward Pass SHALL execute

#### Scenario: Weekly frequency on day 0
- **WHEN** `t_idx == 0` and `rebalance_frequency` is `"weekly"`
- **THEN** the Downward Pass SHALL execute

---

### Requirement: Non-rebalance day weight carry-forward

On non-rebalance days, the Downward Pass SHALL NOT execute. Each node's `temp['weights']` SHALL retain the values from the last rebalance day. The `temp` dict SHALL NOT be reset on non-rebalance days.

#### Scenario: Weights carry forward between weekly rebalances
- **WHEN** `rebalance_frequency` is `"weekly"`, Monday was a rebalance day setting `temp['weights'] = {"A": 0.6, "B": 0.4}`, and Tuesday is not a rebalance day
- **THEN** on Tuesday, `temp['weights']` SHALL still be `{"A": 0.6, "B": 0.4}` and the Downward Pass SHALL NOT execute

#### Scenario: Upward Pass still runs on non-rebalance days
- **WHEN** the current day is not a rebalance day
- **THEN** the Upward Pass SHALL still execute, updating all NAV values using the carried-forward weights

---

### Requirement: rebalance_threshold is not interpreted by the engine

The engine SHALL NOT act on `Settings.rebalance_threshold`. The field SHALL remain on the `Settings` dataclass as a pass-through for downstream consumers (`moa_rebalancer`). No drift computation SHALL occur in the engine.

#### Scenario: Threshold is set but ignored
- **WHEN** `settings.rebalance_threshold` is `0.05` and the current day is a scheduled rebalance day
- **THEN** the Downward Pass SHALL execute unconditionally — no drift comparison is performed
