## ADDED Requirements

### Requirement: Weight node must have at least one child
`_validate_semantics()` SHALL verify that every `weight` node has at least one entry in its `children` array. On violation it SHALL raise `DSLValidationError` with the `id` and `name` of the offending weight node and the message `"weight node must have at least one child"`.

#### Scenario: Weight node with one child passes
- **WHEN** a `weight` node has one or more children
- **THEN** no error is raised

#### Scenario: Weight node with empty children rejected
- **WHEN** a `weight` node has `"children": []`
- **THEN** `DSLValidationError` is raised with the weight node's `id` and `name` and message `"weight node must have at least one child"`

---

### Requirement: Filter node must have at least one child
`_validate_semantics()` SHALL verify that every `filter` node has at least one entry in its `children` array. On violation it SHALL raise `DSLValidationError` with the `id` and `name` of the offending filter node and the message `"filter node must have at least one child"`.

#### Scenario: Filter node with one child passes
- **WHEN** a `filter` node has one or more children
- **THEN** no error is raised

#### Scenario: Filter node with empty children rejected
- **WHEN** a `filter` node has `"children": []`
- **THEN** `DSLValidationError` is raised with the filter node's `id` and `name` and message `"filter node must have at least one child"`

---

### Requirement: if_else node must have at least one condition
`_validate_semantics()` SHALL verify that every `if_else` node has at least one entry in its `conditions` array. On violation it SHALL raise `DSLValidationError` with the `id` and `name` of the offending if_else node and the message `"if_else node must have at least one condition"`.

#### Scenario: if_else node with one condition passes
- **WHEN** an `if_else` node has one or more conditions
- **THEN** no error is raised

#### Scenario: if_else node with empty conditions rejected
- **WHEN** an `if_else` node has `"conditions": []`
- **THEN** `DSLValidationError` is raised with the if_else node's `id` and `name` and message `"if_else node must have at least one condition"`

---

### Requirement: Asset node must have a non-empty ticker
`_validate_semantics()` SHALL verify that every `asset` node has a non-empty `ticker` string. On violation it SHALL raise `DSLValidationError` with the `id` and `name` of the offending asset node and the message `"asset node must have a non-empty ticker"`.

#### Scenario: Asset node with non-empty ticker passes
- **WHEN** an `asset` node has `"ticker": "SPY"`
- **THEN** no error is raised

#### Scenario: Asset node with empty ticker rejected
- **WHEN** an `asset` node has `"ticker": ""`
- **THEN** `DSLValidationError` is raised with the asset node's `id` and `name` and message `"asset node must have a non-empty ticker"`
