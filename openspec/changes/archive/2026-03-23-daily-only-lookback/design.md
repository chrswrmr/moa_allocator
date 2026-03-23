## Context

The DSL `time_offset` type currently accepts `d` (days), `w` (weeks), and `m` (months) via the pattern `^[0-9]+[dwm]$`. The compiler converts these to integer trading days using fixed multipliers (`d=1`, `w=5`, `m=21`). pidb_ib only provides daily bars, making `w` and `m` approximate sugar that no existing strategy uses. This change narrows the pattern to `^[0-9]+d$`, removing the leaky abstraction.

This requires a DSL schema change, which per `dsl-integrity.md` mandates a new ADR before modifying `moa_DSL_schema.json`.

## Goals / Non-Goals

**Goals:**
- Remove `w` and `m` from the DSL `time_offset` pattern
- Keep `d` as the sole unit suffix (forwards-compatible if `w` is ever re-added)
- Create ADR-006 documenting the schema change rationale
- Update compiler, schema, specs, and DSL docs to reflect the narrowed pattern

**Non-Goals:**
- Not bumping `version-dsl` (still `"1.0.0"` per `dsl-integrity.md` — no version branches for v1 work)
- Not removing the multiplier-based conversion architecture — `_LOOKBACK_MULTIPLIERS` stays as `{"d": 1}` so adding units later is a one-line change
- Not changing the internal representation (lookbacks remain `int` trading days after compilation)

## Decisions

### D1: Narrow the regex, keep the multiplier dict

**Decision:** Change `_LOOKBACK_RE` to `^(\d+)(d)$` and `_LOOKBACK_MULTIPLIERS` to `{"d": 1}`. Keep the dict+regex architecture rather than collapsing to a bare `int()` parse.

**Why:** The multiplier dict is the natural extension point. Re-adding `w` later is a one-line dict change + regex widen. Collapsing to `int()` would require restructuring the parser.

**Alternative rejected:** Parse as plain integer (drop `d` suffix entirely). This changes the field type from `string` to `integer`, making future unit re-addition a type-level breaking change to every strategy file.

### D2: ADR-006 before schema change

**Decision:** Create ADR-006 in `DECISIONS.md` as the first implementation step, before touching `moa_DSL_schema.json`.

**Why:** `dsl-integrity.md` rule: "Never modify `moa_DSL_schema.json` without first creating a new ADR in `DECISIONS.md`."

### D3: Update DSL docs alongside schema

**Decision:** Update `moa_Req_to_DSL.md` pattern reference and `moa_DSL_schema.json` `time_offset` definition together in a single task.

**Why:** These are the blueprint pair — schema is the machine contract, Req_to_DSL is the human reference. They must stay in sync.

### D4: Error message update

**Decision:** Update the `_convert_lookback` error message to say `expected pattern like '200d'` (drop `'4w', '3m'` examples).

**Why:** Error messages referencing removed features would confuse users.

## Risks / Trade-offs

- **[Risk] Existing strategies using `w`/`m`** → Mitigated: grep confirms zero usage across all `.moastrat.json` files. Only `d` is used.
- **[Risk] Future need for weekly/monthly lookbacks** → Mitigated: `d` suffix preserved as string type. Re-adding `w` is a backwards-compatible regex widen + one dict entry. No existing strategies break.
- **[Trade-off] Slight loss of convenience** → Users must write `"21d"` instead of `"1m"`. Acceptable since `"1m"` was approximate anyway (19-23 actual trading days per month).
