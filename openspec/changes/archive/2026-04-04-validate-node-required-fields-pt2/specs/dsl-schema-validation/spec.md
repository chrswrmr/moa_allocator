## MODIFIED Requirements

### Requirement: Schema validation
After the version pre-check passes, `compile_strategy()` SHALL validate the full document against `moa_DSL_schema.json` (the canonical copy at `moa_allocations/compiler/schema/moa_DSL_schema.json`). On any violation it SHALL raise `DSLValidationError(node_id="root", node_name="settings", message=<schema error message>)`. Only the first violation is reported (fail-fast).

The `time_offset` definition in `moa_DSL_schema.json` SHALL use the pattern `^[0-9]+d$` (daily bars only). The `w` and `m` suffixes are no longer valid.

The `settings` object in `moa_DSL_schema.json` SHALL include an optional `netting` property with the following structure:

```json
{
  "netting": {
    "type": "object",
    "properties": {
      "pairs": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "long_ticker": { "type": "string" },
            "long_leverage": { "type": "number", "exclusiveMinimum": 0 },
            "short_ticker": { "type": "string" },
            "short_leverage": { "type": "number", "exclusiveMaximum": 0 }
          },
          "required": ["long_ticker", "long_leverage", "short_ticker", "short_leverage"],
          "additionalProperties": false
        }
      },
      "cash_ticker": { "type": ["string", "null"] }
    },
    "required": ["pairs"],
    "additionalProperties": false
  }
}
```

The `netting` property SHALL NOT be in the `required` array of `settings`. When absent, the strategy has no netting.

Each node type definition SHALL declare `required` for its type-specific fields:
- `ifElseNode`: `required: ["logic_mode", "conditions", "true_branch", "false_branch"]`
- `weightNode`: `required: ["method", "children"]`
- `filterNode`: `required: ["sort_by", "select", "children"]`
- `assetNode`: `required: ["ticker"]`

The `select` sub-object within `filterNode` SHALL declare `required: ["mode", "count"]`.

The `ifElseNode` `conditions` property SHALL declare `minItems: 1`. An if_else node with an empty conditions array SHALL be rejected at schema validation time.

The `weightNode` `children` property SHALL declare `minItems: 1`. A weight node with an empty children array SHALL be rejected at schema validation time.

The `filterNode` `children` property SHALL declare `minItems: 1`. A filter node with an empty children array SHALL be rejected at schema validation time.

The `assetNode` `ticker` property SHALL declare `minLength: 1`. An asset node with an empty ticker string SHALL be rejected at schema validation time.

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

#### Scenario: Settings with valid netting block passes schema
- **WHEN** settings contains `"netting": { "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}], "cash_ticker": "SHV" }`
- **THEN** schema validation passes

#### Scenario: Settings without netting block passes schema
- **WHEN** settings does not contain a `netting` property
- **THEN** schema validation passes (netting is optional)

#### Scenario: Netting with zero long_leverage rejected at schema level
- **WHEN** settings contains a netting pair with `"long_leverage": 0`
- **THEN** schema validation fails because `0` does not satisfy `exclusiveMinimum: 0`

#### Scenario: Netting with positive short_leverage rejected at schema level
- **WHEN** settings contains a netting pair with `"short_leverage": 1`
- **THEN** schema validation fails because `1` does not satisfy `exclusiveMaximum: 0`

#### Scenario: Netting with null cash_ticker passes schema
- **WHEN** settings contains `"netting": { "pairs": [...], "cash_ticker": null }`
- **THEN** schema validation passes

#### Scenario: Node missing type-specific required field rejected
- **WHEN** a node has `type: "weight"` but is missing `method` or `children`
- **THEN** schema validation fails and `DSLValidationError` is raised

#### Scenario: Filter node with incomplete select object rejected
- **WHEN** a `filter` node's `select` object is missing `mode` or `count`
- **THEN** schema validation fails and `DSLValidationError` is raised

#### Scenario: if_else node with empty conditions array rejected
- **WHEN** an `if_else` node has `"conditions": []` (empty array)
- **THEN** schema validation fails and `DSLValidationError` is raised because `[]` does not satisfy `minItems: 1`

#### Scenario: weight node with empty children array rejected
- **WHEN** a `weight` node has `"children": []` (empty array)
- **THEN** schema validation fails and `DSLValidationError` is raised because `[]` does not satisfy `minItems: 1`

#### Scenario: filter node with empty children array rejected
- **WHEN** a `filter` node has `"children": []` (empty array)
- **THEN** schema validation fails and `DSLValidationError` is raised because `[]` does not satisfy `minItems: 1`

#### Scenario: asset node with empty ticker string rejected
- **WHEN** an `asset` node has `"ticker": ""` (empty string)
- **THEN** schema validation fails and `DSLValidationError` is raised because `""` does not satisfy `minLength: 1`

#### Scenario: weight node with one child passes schema
- **WHEN** a `weight` node has `"children": [<one valid child>]`
- **THEN** schema validation passes for this node

#### Scenario: asset node with non-empty ticker passes schema
- **WHEN** an `asset` node has `"ticker": "SPY"`
- **THEN** schema validation passes for this node
