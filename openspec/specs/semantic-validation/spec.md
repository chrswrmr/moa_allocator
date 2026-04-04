# semantic-validation

**Module:** `moa_allocations/compiler/`

Post-schema semantic checks in `compile_strategy()`. Runs as Step 3 after JSON Schema validation passes and before node instantiation begins. Enforces cross-field invariants that JSON Schema cannot express.

---

## Requirements

### Requirement: UUID uniqueness
`_validate_semantics()` SHALL collect every node `id` across the entire document (settings node, all nodes in the `root_node` tree, including nodes inside `true_branch`, `false_branch`, and all `children` arrays at every depth). All collected `id` values MUST be unique. On the first duplicate found, it SHALL raise `DSLValidationError` identifying the offending node.

#### Scenario: All node ids are unique
- **WHEN** every node in the document has a distinct UUID
- **THEN** no error is raised and validation continues

#### Scenario: Duplicate node id detected
- **WHEN** two nodes share the same `id` value
- **THEN** `DSLValidationError` is raised with the `id` and `name` of the duplicate node

---

### Requirement: Defined weight completeness and sum
For every `weight` node whose `method` is `"defined"`, `_validate_semantics()` SHALL verify that the keys in `method_params.custom_weights` exactly match the `id` values of the node's `children` array (no missing keys, no extra keys) and that the values sum to `1.0 ± 0.001`. Any mismatch SHALL raise `DSLValidationError` with the `id` and `name` of the offending weight node.

#### Scenario: custom_weights keys and sum are correct
- **WHEN** a `defined` weight node's `custom_weights` keys match all child ids and values sum to 1.0
- **THEN** no error is raised

#### Scenario: custom_weights key missing for a child
- **WHEN** a child `id` is absent from `custom_weights`
- **THEN** `DSLValidationError` is raised with the weight node's `id` and `name`

#### Scenario: custom_weights has an extra key not in children
- **WHEN** `custom_weights` contains a key that does not correspond to any child `id`
- **THEN** `DSLValidationError` is raised with the weight node's `id` and `name`

#### Scenario: custom_weights values do not sum to 1.0
- **WHEN** the sum of `custom_weights` values deviates from `1.0` by more than `0.001`
- **THEN** `DSLValidationError` is raised with the weight node's `id` and `name`

#### Scenario: custom_weights values sum within tolerance
- **WHEN** the sum of `custom_weights` values is within `[0.999, 1.001]`
- **THEN** no error is raised

---

### Requirement: Filter select count bound
For every `filter` node, `_validate_semantics()` SHALL verify that `select.count` is >= 1 and <= `len(children)`. Any violation SHALL raise `DSLValidationError` with the `id` and `name` of the offending filter node.

#### Scenario: select.count within valid range
- **WHEN** `select.count` is >= 1 and <= the number of children
- **THEN** no error is raised

#### Scenario: select.count equals len(children)
- **WHEN** `select.count` equals the number of children
- **THEN** no error is raised (selecting all is valid)

#### Scenario: select.count exceeds len(children)
- **WHEN** `select.count` is greater than the number of children
- **THEN** `DSLValidationError` is raised with the filter node's `id` and `name`, and a message including the count and children count

---

### Requirement: Lookback required for metric functions
For every conditionMetric object (in `if_else` conditions' `lhs` and `rhs` fields) and every sortMetric object (in `filter` nodes' `sort_by` field), `_validate_semantics()` SHALL verify that a `lookback` field is present whenever the `function` is not `"current_price"`. Any violation SHALL raise `DSLValidationError` with the `id` and `name` of the enclosing node.

#### Scenario: Non-current_price metric has lookback
- **WHEN** a conditionMetric or sortMetric uses any function other than `current_price` and provides a `lookback` value
- **THEN** no error is raised

#### Scenario: current_price metric without lookback
- **WHEN** a conditionMetric or sortMetric uses `"current_price"` and has no `lookback` field
- **THEN** no error is raised

#### Scenario: Non-current_price metric missing lookback
- **WHEN** a conditionMetric or sortMetric uses any function other than `"current_price"` and has no `lookback` field
- **THEN** `DSLValidationError` is raised with the `id` and `name` of the enclosing node

---

### Requirement: Date ordering
`_validate_semantics()` SHALL verify that `settings.start_date` is strictly before `settings.end_date`. On violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=...)`.

#### Scenario: start_date before end_date
- **WHEN** `start_date` is an earlier date than `end_date`
- **THEN** no error is raised

#### Scenario: start_date equals end_date
- **WHEN** `start_date` and `end_date` are the same date
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

#### Scenario: start_date after end_date
- **WHEN** `start_date` is a later date than `end_date`
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

---

### Requirement: Rebalance threshold range
If `settings.rebalance_threshold` is present, `_validate_semantics()` SHALL verify that its value is strictly greater than `0` and strictly less than `1`. On violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=...)`.

#### Scenario: rebalance_threshold absent
- **WHEN** `rebalance_threshold` is not present in settings
- **THEN** no error is raised

#### Scenario: rebalance_threshold within valid range
- **WHEN** `rebalance_threshold` is set to a value in `(0, 1)` exclusive
- **THEN** no error is raised

#### Scenario: rebalance_threshold is zero
- **WHEN** `rebalance_threshold` is set to `0.0`
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

#### Scenario: rebalance_threshold is one or greater
- **WHEN** `rebalance_threshold` is set to `1.0` or any value >= 1
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"`

---

### Requirement: Netting pair tickers must exist as tree leaves
`_validate_semantics()` SHALL verify that every `long_ticker` and `short_ticker` in `settings.netting.pairs` exists as an `AssetNode` ticker somewhere in the `root_node` tree. On violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=...)` identifying the missing ticker.

#### Scenario: All netting pair tickers are tree leaves
- **WHEN** netting pairs reference tickers `QQQ` and `PSQ` and both appear as `AssetNode` leaves in the tree
- **THEN** no error is raised

#### Scenario: Netting pair references ticker not in tree
- **WHEN** a netting pair references `long_ticker: "XYZ"` but no `AssetNode` in the tree has ticker `"XYZ"`
- **THEN** `DSLValidationError` is raised with `node_id="root"` and `node_name="settings"` and a message identifying `"XYZ"` as missing

---

### Requirement: No ticker appears in multiple netting pairs
`_validate_semantics()` SHALL verify that no ticker (long or short) appears in more than one netting pair. On violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=...)` identifying the duplicate ticker.

#### Scenario: All tickers unique across pairs
- **WHEN** pair 1 has `QQQ/PSQ` and pair 2 has `EEM/EDZ`
- **THEN** no error is raised

#### Scenario: Ticker appears in two pairs
- **WHEN** pair 1 has `QQQ/PSQ` and pair 2 has `QQQ/SQQQ`
- **THEN** `DSLValidationError` is raised identifying `QQQ` as duplicated across netting pairs

---

### Requirement: Long ticker and short ticker in a pair must be different
`_validate_semantics()` SHALL verify that `long_ticker` and `short_ticker` within each netting pair are different tickers. On violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=...)`.

#### Scenario: Long and short tickers differ
- **WHEN** a pair has `long_ticker: "QQQ"` and `short_ticker: "PSQ"`
- **THEN** no error is raised

#### Scenario: Long and short tickers are the same
- **WHEN** a pair has `long_ticker: "QQQ"` and `short_ticker: "QQQ"`
- **THEN** `DSLValidationError` is raised

---

### Requirement: Netting validation skipped when netting is absent
If `settings.netting` is not present in the document, all netting-related semantic checks SHALL be skipped.

#### Scenario: No netting in settings
- **WHEN** the settings block has no `netting` key
- **THEN** netting validation is skipped and no error is raised

---

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

---

### Requirement: Semantic validation completes before node instantiation
`_validate_semantics()` MUST complete without error before any node instantiation begins. If any semantic rule is violated, `DSLValidationError` is raised and no node objects are created.

#### Scenario: All rules pass
- **WHEN** all semantic checks pass
- **THEN** `_validate_semantics()` returns `None` and node instantiation proceeds

#### Scenario: Any rule fails
- **WHEN** any semantic check raises `DSLValidationError`
- **THEN** node instantiation does not begin and the error propagates to the caller
