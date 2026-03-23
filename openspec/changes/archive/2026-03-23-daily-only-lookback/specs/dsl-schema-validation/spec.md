## MODIFIED Requirements

### Requirement: Schema validation
After the version pre-check passes, `compile_strategy()` SHALL validate the full document against `moa_DSL_schema.json` (the canonical copy at `moa_allocations/compiler/schema/moa_DSL_schema.json`). On any violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=<schema error message>)`. Only the first violation is reported (fail-fast).

The `time_offset` definition in `moa_DSL_schema.json` SHALL use the pattern `^[0-9]+d$` (daily bars only). The `w` and `m` suffixes are no longer valid.

#### Scenario: Valid document passes schema validation
- **WHEN** the document satisfies all constraints in `moa_DSL_schema.json`
- **THEN** no error is raised and execution continues to field extraction

#### Scenario: Document missing a required top-level field
- **WHEN** the document is missing a required field (e.g. `settings`)
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

#### Scenario: Document with an invalid field value
- **WHEN** the document contains a field whose value violates the schema (e.g. wrong type)
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

#### Scenario: Lookback with week suffix rejected at schema level
- **WHEN** a document contains `lookback: "4w"` in any node
- **THEN** schema validation fails and `DSLValidationError` is raised because `"4w"` does not match `^[0-9]+d$`

#### Scenario: Lookback with month suffix rejected at schema level
- **WHEN** a document contains `duration: "3m"` in any node
- **THEN** schema validation fails and `DSLValidationError` is raised because `"3m"` does not match `^[0-9]+d$`
