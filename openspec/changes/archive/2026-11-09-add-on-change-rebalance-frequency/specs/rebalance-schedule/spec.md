## MODIFIED Requirements

### Requirement: Rebalance day classification

The engine SHALL provide a function `_is_rebalance_day(current_date, prev_date, frequency) -> bool` that determines whether `current_date` is a rebalance day based on the `rebalance_frequency` setting.

| `frequency` | Rule |
|---|---|
| `"daily"` | Always returns `True` |
| `"weekly"` | Returns `True` when `current_date` and `prev_date` fall in different ISO calendar weeks |
| `"monthly"` | Returns `True` when `current_date` and `prev_date` fall in different calendar months |
| `"on_change"` | Always returns `True` (the engine evaluates the tree every trading day; `moa_rebalancer` decides whether to trade by comparing the resulting weights to the last traded target) |

The `"on_change"` case SHALL be an explicit branch in `_is_rebalance_day`, not a reliance on the trailing default return.

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

#### Scenario: On-change frequency — every day rebalances
- **WHEN** `frequency` is `"on_change"` and `current_date` is any trading day (including a day in the same ISO week and same month as `prev_date`)
- **THEN** `_is_rebalance_day` SHALL return `True`

#### Scenario: On-change strategy compiles and emits one row per trading day
- **WHEN** a strategy file sets `settings.rebalance_frequency` to `"on_change"`, is passed to `compile_strategy()`, and is then run by the engine over N trading days
- **THEN** compilation SHALL succeed (schema validation accepts the value) and the output DataFrame SHALL contain exactly N rows, one per trading day, with the Downward Pass having executed on every day
