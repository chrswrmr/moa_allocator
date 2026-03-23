## Why

pidb_ib provides exclusively daily bars (1 row = 1 trading day). The DSL's `time_offset` pattern currently accepts `d` (days), `w` (weeks, `*5`), and `m` (months, `*21`). Since there are no weekly or monthly bars in the data, `w` and `m` are sugar that silently converts to an approximate number of daily bars (`m=21` is inaccurate for months with 19-23 trading days). No existing strategy uses `w` or `m`. Removing them eliminates the leaky abstraction and makes the DSL honest: all lookbacks are in trading days (bars).

## What Changes

- **BREAKING**: DSL `time_offset` pattern changes from `^[0-9]+[dwm]$` to `^[0-9]+d$` — strategies using `w` or `m` will fail schema validation
- **BREAKING**: Compiler `_LOOKBACK_MULTIPLIERS` reduced to `{"d": 1}` — `w` and `m` keys removed
- ADR required for DSL schema change (per `dsl-integrity.md` rule)
- Update all spec scenarios that reference `w` or `m` lookback examples

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `tree-instantiation`: Remove `w`/`m` multipliers from lookback conversion requirement; remove weeks/months scenarios; update regex pattern
- `dsl-schema-validation`: `time_offset` pattern narrows to `^[0-9]+d$`

## Impact

- **Schema**: `moa_DSL_schema.json` — `time_offset` definition pattern change
- **Compiler**: `compiler.py` — `_LOOKBACK_MULTIPLIERS`, `_LOOKBACK_RE` narrowed
- **Specs**: `tree-instantiation/spec.md`, `dsl-schema-validation/spec.md` — scenario updates
- **Strategies**: No existing `.moastrat.json` files are affected (all already use `d`)
- **DSL docs**: `moa_Req_to_DSL.md` — remove references to `w`/`m` if present
- **ADR**: New entry in `DECISIONS.md` required before schema modification
