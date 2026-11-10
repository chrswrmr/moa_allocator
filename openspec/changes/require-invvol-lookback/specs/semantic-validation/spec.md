## ADDED Requirements

### Requirement: Inverse-volatility weight node requires lookback
For every `weight` node whose `method` is `"inverse_volatility"`, `_validate_semantics()` SHALL verify that `method_params` is present and contains a `lookback` field. A violation SHALL raise `DSLValidationError` with the `id` and `name` of the weight node and a message naming `method_params.lookback`. This check runs at validation time so that `--validate` rejects the document and the engine never reaches `_build_algo_stack` with a missing lookback.

#### Scenario: inverse_volatility with lookback passes
- **WHEN** a `weight` node has `method: "inverse_volatility"` and `method_params: {"lookback": "20d"}`
- **THEN** no error is raised

#### Scenario: inverse_volatility without method_params fails
- **WHEN** a `weight` node has `method: "inverse_volatility"` and no `method_params` key
- **THEN** `DSLValidationError` is raised with the weight node's `id` and a message containing `method_params.lookback`

#### Scenario: inverse_volatility with method_params but no lookback fails
- **WHEN** a `weight` node has `method: "inverse_volatility"` and `method_params: {}`
- **THEN** `DSLValidationError` is raised with the weight node's `id` and a message containing `method_params.lookback`

#### Scenario: Other weight methods do not require lookback
- **WHEN** a `weight` node has `method: "equal"` and no `method_params`
- **THEN** no error is raised by this rule

#### Scenario: Bug-report tree is rejected at validation time
- **WHEN** the root is an `inverse_volatility` weight node without `method_params` whose children include an `if_else` with `sma_price` conditions and a `filter` branch
- **THEN** `compile_strategy()` raises `DSLValidationError` for the root weight node, and `--validate` reports the document as invalid instead of the full run crashing with `KeyError`
