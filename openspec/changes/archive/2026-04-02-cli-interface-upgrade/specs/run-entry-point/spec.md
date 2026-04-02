## ADDED Requirements

### Requirement: validate function compiles and validates strategy

`moa_allocations/__init__.py` SHALL expose `validate(strategy_path: str) -> bool`. It SHALL call `compile_strategy(strategy_path)` and return `True` on success. If compilation raises `DSLValidationError`, the exception SHALL propagate to the caller (not caught).

#### Scenario: Valid strategy returns True

- **WHEN** `validate("path/to/valid.moastrat.json")` is called
- **THEN** it SHALL return `True`

#### Scenario: Invalid strategy raises DSLValidationError

- **WHEN** `validate("path/to/invalid.moastrat.json")` is called and the strategy has a validation error
- **THEN** `DSLValidationError` SHALL propagate with `node_id`, `node_name`, and `message`

---

### Requirement: get_tickers function extracts traded and signal tickers

`moa_allocations/__init__.py` SHALL expose `get_tickers(strategy_path: str) -> dict`. It SHALL compile the strategy and return a dict with:

- `traded_tickers`: sorted list of all AssetNode leaf tickers, excluding `XCASHX`
- `signal_tickers`: sorted list of tickers in `if_else` condition `lhs`/`rhs` `asset` fields that are NOT in the traded set

If compilation fails, `DSLValidationError` SHALL propagate.

#### Scenario: Strategy with traded and signal tickers

- **WHEN** `get_tickers("strat.json")` is called on a strategy with asset leaves `SPY`, `TLT` and an if_else condition referencing `VIXY`
- **THEN** it SHALL return `{"traded_tickers": ["SPY", "TLT"], "signal_tickers": ["VIXY"]}`

#### Scenario: All condition tickers are traded

- **WHEN** `get_tickers("strat.json")` is called on a strategy where all condition tickers are also asset leaves
- **THEN** `signal_tickers` SHALL be `[]`

#### Scenario: XCASHX excluded

- **WHEN** the strategy contains an XCASHX asset leaf
- **THEN** XCASHX SHALL NOT appear in either list

---

### Requirement: check_prices function verifies price data availability

`moa_allocations/__init__.py` SHALL expose `check_prices(strategy_path: str, db_path: str) -> dict`. It SHALL:

1. Compile the strategy (propagate `DSLValidationError` on failure)
2. Collect all tickers (traded + signal, excluding XCASHX)
3. Compute the lookback-adjusted date range
4. Fetch data via `get_matrix` and inspect for missing tickers or date gaps

On success: return `{"prices_available": True}`.
On missing data: raise `PriceDataError` with details about missing tickers and/or dates.

#### Scenario: All data available

- **WHEN** `check_prices("strat.json", "path/to/db")` is called and all tickers have data
- **THEN** it SHALL return `{"prices_available": True}`

#### Scenario: Missing tickers

- **WHEN** a ticker in the strategy has no data in pidb_ib
- **THEN** `PriceDataError` SHALL be raised with a message listing the missing tickers

#### Scenario: Compilation failure

- **WHEN** the strategy is invalid
- **THEN** `DSLValidationError` SHALL propagate (not `PriceDataError`)

---

### Requirement: list_indicators function returns engine indicator metadata

`moa_allocations/__init__.py` SHALL expose `list_indicators() -> list[dict]`. It SHALL read the `_DISPATCH` table and lookback sets from `moa_allocations.engine.algos.metrics` and return a list of dicts, each with:

- `name`: the metric function name (string)
- `requires_lookback`: `True` if the function is in `_NEEDS_LOOKBACK_PRICES` or `_NEEDS_LOOKBACK_RETURNS`, `False` otherwise (boolean)

The list SHALL be sorted alphabetically by `name`.

#### Scenario: Returns all dispatch entries

- **WHEN** `list_indicators()` is called
- **THEN** the returned list SHALL contain exactly the keys from `_DISPATCH`, one entry per key

#### Scenario: current_price does not require lookback

- **WHEN** `list_indicators()` is called
- **THEN** the entry for `"current_price"` SHALL have `"requires_lookback": False`

#### Scenario: Sorted alphabetically

- **WHEN** `list_indicators()` is called
- **THEN** the entries SHALL be sorted by `name` in ascending alphabetical order

---

### Requirement: collect_traded_tickers function

`moa_allocations/engine/runner.py` SHALL expose `collect_traded_tickers(root: RootNode) -> set[str]`. It SHALL walk the strategy tree and return all AssetNode leaf tickers, excluding `XCASHX`.

#### Scenario: Asset leaves only

- **WHEN** `collect_traded_tickers(root)` is called on a tree with AssetNode leaves `SPY`, `TLT`, `XCASHX`
- **THEN** it SHALL return `{"SPY", "TLT"}`

#### Scenario: Condition tickers excluded

- **WHEN** the tree has an if_else condition referencing `VIXY` but no `VIXY` AssetNode
- **THEN** `VIXY` SHALL NOT be in the result

---

### Requirement: collect_signal_tickers function

`moa_allocations/engine/runner.py` SHALL expose `collect_signal_tickers(root: RootNode) -> set[str]`. It SHALL walk the strategy tree and return tickers referenced in `if_else` condition `lhs`/`rhs` `asset` fields that are NOT AssetNode leaves. `XCASHX` SHALL be excluded.

#### Scenario: Signal ticker not traded

- **WHEN** the tree has an if_else condition referencing `VIXY` and `VIXY` is not an AssetNode leaf
- **THEN** `collect_signal_tickers` SHALL return a set containing `"VIXY"`

#### Scenario: Condition ticker is also traded

- **WHEN** the tree has an if_else condition referencing `SPY` and `SPY` is also an AssetNode leaf
- **THEN** `SPY` SHALL NOT be in the signal tickers set

#### Scenario: No conditions

- **WHEN** the strategy has no if_else nodes
- **THEN** `collect_signal_tickers` SHALL return an empty set
