## MODIFIED Requirements

### Requirement: Ticker collection from tree

`Runner.__init__` SHALL collect all unique tickers from `AssetNode` leaves and from `IfElseNode` condition references (`lhs.asset`, `rhs.asset` when rhs is a dict). Additionally, if `settings.netting` is configured and `netting.cash_ticker` is a non-null string, that ticker SHALL be included in the collected ticker set — **unless** its value equals `"xcashx"` (case-insensitive), in which case it SHALL be excluded because it is the synthetic cash sentinel that requires no price data. This complete ticker set SHALL be used for price data validation.

#### Scenario: Tickers from asset leaves
- **WHEN** the tree has `AssetNode` leaves with tickers `["SPY", "BND", "GLD"]`
- **THEN** the collected ticker set SHALL include `"SPY"`, `"BND"`, and `"GLD"`

#### Scenario: Tickers from if_else condition references
- **WHEN** an `IfElseNode` has a condition with `lhs.asset == "VIX"` and `rhs` is a dict with `rhs.asset == "TLT"`
- **THEN** the collected ticker set SHALL include `"VIX"` and `"TLT"` (in addition to any leaf tickers)

#### Scenario: Netting cash ticker included in ticker collection
- **WHEN** `settings.netting.cash_ticker` is `"SHV"` and `"SHV"` is not an `AssetNode` leaf
- **THEN** the collected ticker set SHALL include `"SHV"`

#### Scenario: Netting cash ticker already a leaf
- **WHEN** `settings.netting.cash_ticker` is `"SHV"` and `"SHV"` is already an `AssetNode` leaf
- **THEN** `"SHV"` appears once in the ticker set (no duplication)

#### Scenario: Netting cash ticker is null
- **WHEN** `settings.netting.cash_ticker` is `null`
- **THEN** no additional ticker is added from netting config

#### Scenario: No netting configured
- **WHEN** `settings.netting` is not present
- **THEN** ticker collection behaves as before (leaves + condition references only)

#### Scenario: Netting cash ticker is the synthetic sentinel (lowercase)
- **WHEN** `settings.netting.cash_ticker` is `"xcashx"`
- **THEN** `"xcashx"` SHALL NOT be added to the collected ticker set

#### Scenario: Netting cash ticker is the synthetic sentinel (uppercase)
- **WHEN** `settings.netting.cash_ticker` is `"XCASHX"`
- **THEN** `"XCASHX"` SHALL NOT be added to the collected ticker set

#### Scenario: Strategy with xcashx cash ticker runs without PriceDataError
- **WHEN** a strategy has `settings.netting.cash_ticker == "xcashx"` and all real asset tickers are present in `price_data`
- **THEN** `Runner.__init__` SHALL complete without raising `PriceDataError`
