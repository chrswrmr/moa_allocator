## 1. ADR

- [x] 1.1 Add ADR-006 to `DECISIONS.md` documenting removal of `w`/`m` time_offset suffixes (required before schema change per `dsl-integrity.md`)

## 2. DSL Schema and Docs

- [x] 2.1 Update `time_offset` pattern in `moa_DSL_schema.json` from `^[0-9]+[dwm]$` to `^[0-9]+d$`
- [x] 2.2 Update the canonical copy at `moa_allocations/compiler/schema/moa_DSL_schema.json` to match
- [x] 2.3 Update `moa_Req_to_DSL.md` to remove any references to `w`/`m` suffixes

## 3. Compiler

- [x] 3.1 Change `_LOOKBACK_MULTIPLIERS` in `compiler.py` from `{"d": 1, "w": 5, "m": 21}` to `{"d": 1}`
- [x] 3.2 Change `_LOOKBACK_RE` from `^(\d+)([dwm])$` to `^(\d+)(d)$`
- [x] 3.3 Update `_convert_lookback` error message to reference only `'200d'` (drop `'4w'`, `'3m'` examples)

## 4. Tests

- [x] 4.1 Update existing lookback conversion tests: remove passing cases for `w` and `m`
- [x] 4.2 Add rejection tests: `"4w"` and `"3m"` SHALL raise `DSLValidationError`
- [x] 4.3 Run `uv run pytest` — all tests pass

## 5. Specs

- [x] 5.1 Verify main specs `openspec/specs/tree-instantiation/spec.md` and `openspec/specs/dsl-schema-validation/spec.md` are updated by delta sync after archive
