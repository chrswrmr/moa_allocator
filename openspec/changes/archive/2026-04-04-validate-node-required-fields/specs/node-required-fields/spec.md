# node-required-fields

**Module:** `moa_allocations/compiler/schema/moa_DSL_schema.json`

Schema-level enforcement of required fields per node type definition. Ensures that documents with missing type-specific fields are rejected during JSON Schema validation, before semantic validation or node instantiation.

---

## ADDED Requirements

### Requirement: if_else node required fields
The `ifElseNode` definition in `moa_DSL_schema.json` SHALL declare `required: ["logic_mode", "conditions", "true_branch", "false_branch"]`. An `if_else` node missing any of these fields SHALL be rejected at schema validation time.

#### Scenario: if_else node missing logic_mode rejected
- **WHEN** an `if_else` node has `conditions`, `true_branch`, and `false_branch` but no `logic_mode`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: if_else node missing conditions rejected
- **WHEN** an `if_else` node has `logic_mode`, `true_branch`, and `false_branch` but no `conditions`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: if_else node missing true_branch rejected
- **WHEN** an `if_else` node has `logic_mode`, `conditions`, and `false_branch` but no `true_branch`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: if_else node missing false_branch rejected
- **WHEN** an `if_else` node has `logic_mode`, `conditions`, and `true_branch` but no `false_branch`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: Complete if_else node passes
- **WHEN** an `if_else` node has all four required fields (`logic_mode`, `conditions`, `true_branch`, `false_branch`)
- **THEN** schema validation passes for this node

---

### Requirement: weight node required fields
The `weightNode` definition in `moa_DSL_schema.json` SHALL declare `required: ["method", "children"]`. A `weight` node missing either field SHALL be rejected at schema validation time.

#### Scenario: weight node missing method rejected
- **WHEN** a `weight` node has `children` but no `method`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: weight node missing children rejected
- **WHEN** a `weight` node has `method` but no `children`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: Complete weight node passes
- **WHEN** a `weight` node has both `method` and `children`
- **THEN** schema validation passes for this node

---

### Requirement: filter node required fields
The `filterNode` definition in `moa_DSL_schema.json` SHALL declare `required: ["sort_by", "select", "children"]`. A `filter` node missing any of these fields SHALL be rejected at schema validation time.

#### Scenario: filter node missing sort_by rejected
- **WHEN** a `filter` node has `select` and `children` but no `sort_by`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: filter node missing select rejected
- **WHEN** a `filter` node has `sort_by` and `children` but no `select`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: filter node missing children rejected
- **WHEN** a `filter` node has `sort_by` and `select` but no `children`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: Complete filter node passes
- **WHEN** a `filter` node has all three required fields (`sort_by`, `select`, `children`)
- **THEN** schema validation passes for this node

---

### Requirement: asset node required fields
The `assetNode` definition in `moa_DSL_schema.json` SHALL declare `required: ["ticker"]`. An `asset` node missing the `ticker` field SHALL be rejected at schema validation time.

#### Scenario: asset node missing ticker rejected
- **WHEN** an `asset` node has `type: "asset"` but no `ticker`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: Complete asset node passes
- **WHEN** an `asset` node has `ticker`
- **THEN** schema validation passes for this node

---

### Requirement: filter select sub-object required fields
The `select` property definition within `filterNode` in `moa_DSL_schema.json` SHALL declare `required: ["mode", "count"]`. A `select` object missing either field SHALL be rejected at schema validation time.

#### Scenario: select missing mode rejected
- **WHEN** a filter node's `select` object has `count` but no `mode`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: select missing count rejected
- **WHEN** a filter node's `select` object has `mode` but no `count`
- **THEN** schema validation fails with a `DSLValidationError`

#### Scenario: Complete select object passes
- **WHEN** a filter node's `select` object has both `mode` and `count`
- **THEN** schema validation passes for this node
