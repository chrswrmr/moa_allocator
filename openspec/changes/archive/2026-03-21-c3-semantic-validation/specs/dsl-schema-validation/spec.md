## MODIFIED Requirements

### Requirement: Top-level field extraction
After schema validation passes, `compile_strategy()` SHALL make the four top-level fields — `id`, `version-dsl`, `settings`, `root_node` — available for the semantic validation step. Semantic validation MUST complete successfully before node instantiation begins.

#### Scenario: All top-level fields are accessible after validation
- **WHEN** JSON loading and schema validation both succeed
- **THEN** `id`, `version-dsl`, `settings`, and `root_node` are extracted from the parsed document and available to the semantic validation step

#### Scenario: Semantic validation runs before instantiation
- **WHEN** JSON loading and schema validation both succeed
- **THEN** `_validate_semantics(doc)` is called before any node object is created, and any `DSLValidationError` it raises propagates to the caller without partial instantiation
