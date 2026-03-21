## 1. Package Setup

- [x] 1.1 Create `moa_allocations/compiler/` directory with `__init__.py` (exporting `compile_strategy`)
- [x] 1.2 Create `moa_allocations/compiler/schema/` directory and move `moa_DSL_schema.json` there as the canonical location
- [x] 1.3 Add `moa_allocations/compiler/compiler.py` with an empty `compile_strategy(path: str)` stub

## 2. JSON Loading

- [x] 2.1 Implement file loading in `compile_strategy()`: open `path` and call `json.load()`
- [x] 2.2 Catch `FileNotFoundError` and `json.JSONDecodeError`, re-raise as `DSLValidationError(node_id="root", node_name="settings", message=...)`

## 3. Version Pre-check

- [x] 3.1 After loading, check `"version-dsl"` key is present in the document; raise `DSLValidationError` immediately if missing
- [x] 3.2 Check `doc["version-dsl"] == "1.0.0"`; raise `DSLValidationError` immediately if not, including the bad value in the message

## 4. Schema Validation

- [x] 4.1 Load `moa_DSL_schema.json` via `importlib.resources` from `moa_allocations.compiler.schema`
- [x] 4.2 Call `jsonschema.validate(doc, schema)`, catch `jsonschema.ValidationError`, re-raise as `DSLValidationError(node_id="root", node_name="settings", message=e.message)`

## 5. Field Extraction

- [x] 5.1 Extract `id`, `version-dsl`, `settings`, `root_node` from the validated document into local variables
- [x] 5.2 Raise `NotImplementedError` as a stub for steps 3–5 (C3/C4), passing the extracted fields as context in the message

## 6. Tests

- [x] 6.1 Test: valid `.moastrat.json` file passes loading and validation without error (reaches `NotImplementedError`)
- [x] 6.2 Test: non-existent file raises `DSLValidationError`
- [x] 6.3 Test: file with invalid JSON raises `DSLValidationError`
- [x] 6.4 Test: document with missing `version-dsl` raises `DSLValidationError` before schema validation runs
- [x] 6.5 Test: document with wrong `version-dsl` (e.g. `"2.0.0"`) raises `DSLValidationError` before schema validation runs
- [x] 6.6 Test: document missing a required top-level field (e.g. `settings`) raises `DSLValidationError`
- [x] 6.7 Test: document with an invalid field type raises `DSLValidationError`
- [x] 6.8 Run `uv run pytest` — all tests pass
