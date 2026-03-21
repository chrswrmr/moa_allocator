# DSL Integrity

- Never modify `moa_DSL_schema.json` without first creating a new ADR in `DECISIONS.md`. The schema is the contract between the user-facing DSL and the compiler — changes have downstream consequences for all existing strategy files.
- `version-dsl` is frozen at `"1.0.0"` for all v1 work. Do not bump the version or add version branches without a new ADR and a new change.
