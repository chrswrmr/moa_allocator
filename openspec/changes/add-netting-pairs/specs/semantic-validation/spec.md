## ADDED Requirements

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
