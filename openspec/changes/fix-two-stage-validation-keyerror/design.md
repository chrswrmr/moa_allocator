## Context

`compile_strategy()` (compiler.py, step 2b/3) records a schema error instead of raising, runs `_validate_semantics(doc)`, re-raises any `DSLValidationError` from it, and only then raises the recorded schema error. `_validate_semantics()` is written for schema-valid input: it uses `doc["settings"]`, `node["id"]`, `node["select"]["count"]`, `pair["long_ticker"]` and so on. When the schema check failed precisely because one of those keys is missing, the semantic pass blows up with `KeyError` before it can report anything.

## Goals / Non-Goals

**Goals:**
- Malformed documents always surface as `DSLValidationError`.
- Keep the intent of `62be8aa`: when both layers can report, the semantic error with a `node_id` wins.
- Put the two-stage rule into the spec.

**Non-Goals:**
- Making `_validate_semantics()` tolerant of missing keys throughout. That would duplicate what the schema already checks and scatter `.get()` defaults across every rule.
- Changing any error message or the `node_id`/`node_name` conventions.

## Decisions

**1. Catch at the call site in `compile_strategy()`, not inside `_validate_semantics()`.**
The call site knows whether a schema error is pending. The rule becomes: `DSLValidationError` from semantics propagates; any other exception is swallowed only if `schema_error` is set, and then the schema error is raised. If no schema error is pending, the exception propagates unchanged, so a genuine bug in the semantic checks on a valid document is never hidden.
Alternative: `.get()`-proof every access in `_validate_semantics()`. Rejected as invasive and as weakening the function's precondition.

**2. Swallow `Exception`, not just `KeyError`.**
A structurally invalid document can also produce `TypeError` (e.g. `children` is not a list, `custom_weights.values()` on a string) or `AttributeError`. Any of these means "the semantic pass could not run on this document", and the schema error is the correct report. The catch is guarded by `schema_error is not None`, so it cannot mask bugs on valid input.

**3. Spec placement.**
The rule is documented under the `dsl-schema-validation` "Schema validation" requirement, since that is where the schema-failure path is specified. The `semantic-validation` spec's "completes before node instantiation" requirement remains true and is not modified.

## Risks / Trade-offs

- [A real bug in `_validate_semantics()` could be masked when the document also has a schema error] → the schema error is still reported, so the user gets a correct, actionable message; the bug would surface on the next schema-valid document. Acceptable.
- [Semantic pass does wasted work on broken documents] → negligible; documents are small.

## Migration Plan

None. Additive behaviour fix. Rollback is a revert.

## Open Questions

None.
