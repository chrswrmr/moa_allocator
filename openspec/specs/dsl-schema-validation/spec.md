# dsl-schema-validation

**Module:** `moa_allocations/compiler/`

JSON loading, DSL version checking, schema validation, and top-level field extraction for `compile_strategy()`. This is the entry gate — all downstream compiler steps receive a document that has already passed these checks.

---

## Requirements

### Requirement: JSON file loading
`compile_strategy(path)` SHALL load and JSON-parse the file at `path`. If the file does not exist or cannot be read, it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=...)`. If the file content is not valid JSON, it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=...)`.

#### Scenario: Valid JSON file is loaded
- **WHEN** `path` points to a readable, valid JSON file
- **THEN** the file is parsed into a Python dict without error

#### Scenario: File does not exist
- **WHEN** `path` points to a non-existent file
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

#### Scenario: File contains invalid JSON
- **WHEN** the file at `path` exists but its content is not valid JSON
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

---

### Requirement: DSL version pre-check
Before running schema validation, `compile_strategy()` SHALL check that `version-dsl` is present in the parsed document and equals `"1.0.0"` exactly. On any mismatch it SHALL raise `DSLValidationError` immediately without proceeding to schema validation.

#### Scenario: Correct version proceeds
- **WHEN** the document contains `"version-dsl": "1.0.0"`
- **THEN** execution continues to schema validation

#### Scenario: Wrong version is rejected immediately
- **WHEN** the document contains a `version-dsl` value other than `"1.0.0"` (e.g. `"2.0.0"`)
- **THEN** `DSLValidationError` is raised with `node_id="root"`, `node_name="settings"`, and a message identifying the bad version value

#### Scenario: Missing version-dsl is rejected immediately
- **WHEN** the document does not contain the `version-dsl` key
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

---

### Requirement: Schema validation
After the version pre-check passes, `compile_strategy()` SHALL validate the full document against `moa_DSL_schema.json` (the canonical copy at `moa_allocations/compiler/schema/moa_DSL_schema.json`). On any violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=<schema error message>)`. Only the first violation is reported (fail-fast).

#### Scenario: Valid document passes schema validation
- **WHEN** the document satisfies all constraints in `moa_DSL_schema.json`
- **THEN** no error is raised and execution continues to field extraction

#### Scenario: Document missing a required top-level field
- **WHEN** the document is missing a required field (e.g. `settings`)
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

#### Scenario: Document with an invalid field value
- **WHEN** the document contains a field whose value violates the schema (e.g. wrong type)
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

---

### Requirement: Top-level field extraction
After schema validation passes, `compile_strategy()` SHALL make the four top-level fields — `id`, `version-dsl`, `settings`, `root_node` — available for the semantic validation step. Semantic validation MUST complete successfully before node instantiation begins.

#### Scenario: All top-level fields are accessible after validation
- **WHEN** JSON loading and schema validation both succeed
- **THEN** `id`, `version-dsl`, `settings`, and `root_node` are extracted from the parsed document and available to the semantic validation step

#### Scenario: Semantic validation runs before instantiation
- **WHEN** JSON loading and schema validation both succeed
- **THEN** `_validate_semantics(doc)` is called before any node object is created, and any `DSLValidationError` it raises propagates to the caller without partial instantiation
