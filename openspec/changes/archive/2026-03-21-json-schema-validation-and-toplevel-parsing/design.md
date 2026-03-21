## Context

`compile_strategy()` is the compiler's public entry point, but the `moa_allocations/compiler/` package does not yet exist. `DSLValidationError` already lives in `moa_allocations/exceptions.py` (delivered by C1). This change creates the compiler package and implements only steps 1–2 of `compile_strategy()`: JSON loading and top-level validation. Steps 3–5 (semantic validation, node instantiation, return) are deferred to C3 and C4.

## Goals / Non-Goals

**Goals:**
- Create `moa_allocations/compiler/` package with `compiler.py`
- Implement step 1: load and JSON-parse the file at `path`
- Implement step 2: validate the parsed document against the bundled `moa_DSL_schema.json` and extract top-level fields (`id`, `version-dsl`, `settings`, `root_node`)
- Raise `DSLValidationError(node_id="root", node_name="settings", message=...)` on any schema violation or wrong `version-dsl`
- Bundle `moa_DSL_schema.json` inside the compiler package at `compiler/schema/`

**Non-Goals:**
- Semantic validation (C3): date ordering, threshold ranges, custom_weights sums, etc.
- Node instantiation (C4): building `RootNode` or any `StrategyNode`
- Any engine, algo, or metrics code

## Decisions

### 1. Version check: explicit pre-check before full schema validation

Execution order within step 2:

1. Check `version-dsl` key is present and equals `"1.0.0"` → raise `DSLValidationError` immediately if not
2. Run `jsonschema.validate()` for full structural validation → catch `ValidationError`, re-raise as `DSLValidationError`
3. Extract top-level fields

The version pre-check runs first because the spec requires failing immediately on a wrong version without attempting further parsing. `jsonschema` would also reject a wrong value (via `enum: ["1.0.0"]` in the schema), but its error message is a generic path string. The explicit pre-check produces a controlled, readable message and short-circuits before the heavier validation runs.

**Alternative considered:** rely solely on jsonschema's enum violation and format its error message. Rejected — fragile, and the spec's "immediately" language implies the check should be deliberate and fast.

### 2. Schema file location: bundled as a package data file

`moa_DSL_schema.json` lives at `moa_allocations/compiler/schema/moa_DSL_schema.json` — this is its canonical location. It is resolved at runtime using `importlib.resources` (stdlib, Python 3.9+). The copy in `openspec/moa_strategy_DSL/` was a drafting artefact; `compiler/schema/` is the source of truth going forward.

**Alternative considered:** resolve schema relative to `__file__`. Works but `importlib.resources` is the idiomatic stdlib approach for package data and handles editable installs correctly.

### 3. `compile_strategy()` is a stub through C4

After steps 1–2 succeed, the function raises `NotImplementedError` as a placeholder for steps 3–5. This makes the partial implementation safe — callers get a clear signal rather than a silent partial result.

**Alternative considered:** return `None` or an empty object. Rejected — a `NotImplementedError` is self-documenting and prevents accidental downstream use before C4.

### 4. jsonschema error mapping

`jsonschema.ValidationError` is caught and re-raised as `DSLValidationError(node_id="root", node_name="settings", message=str(e.message))`. Only the first error is surfaced (fail-fast), consistent with the spec's "never return a partially built tree" contract.

## Risks / Trade-offs

- **Schema location** → `moa_allocations/compiler/schema/moa_DSL_schema.json` is the canonical location. The draft copy in `openspec/moa_strategy_DSL/` is superseded and can be treated as reference-only.
- **jsonschema version pinning** → `jsonschema` has historically had breaking changes between major versions. Mitigation: pin to a specific major version (e.g., `jsonschema>=4,<5`) in `pyproject.toml`.
