# netting

**Module:** `moa_allocations/engine/runner.py`

Post-flatten transformation that nets offsetting long/short ETF pairs into single-leg positions and redistributes freed weight. Applied to the global weight vector on every trading day, after flattening and before the sum-to-one assertion.

---

## Requirements

### Requirement: Netting computes net economic exposure per pair

For each configured netting pair `(long_ticker, L, short_ticker, S)` where `L > 0` and `S < 0`, the engine SHALL compute net economic exposure as:

```
net_exposure = w_long * L + w_short * S
```

where `w_long` and `w_short` are the current global weights of the long and short tickers respectively. If either ticker has zero weight (not present in the flattened vector), its weight SHALL be treated as `0.0`.

#### Scenario: Both tickers present with 1x leverage
- **WHEN** the flattened weights contain `QQQ=0.30, PSQ=0.10` and the netting pair is `(QQQ, 1, PSQ, -1)`
- **THEN** net exposure is `0.30 * 1 + 0.10 * (-1) = 0.20`

#### Scenario: Both tickers present with asymmetric leverage
- **WHEN** the flattened weights contain `EEM=0.30, EDZ=0.05` and the netting pair is `(EEM, 1, EDZ, -3)`
- **THEN** net exposure is `0.30 * 1 + 0.05 * (-3) = 0.15`

#### Scenario: Only long ticker present
- **WHEN** the flattened weights contain `QQQ=0.40` but no `PSQ` and the netting pair is `(QQQ, 1, PSQ, -1)`
- **THEN** net exposure is `0.40 * 1 + 0.0 * (-1) = 0.40` (netting is a no-op; QQQ stays at 0.40)

#### Scenario: Only short ticker present
- **WHEN** the flattened weights contain `PSQ=0.20` but no `QQQ` and the netting pair is `(QQQ, 1, PSQ, -1)`
- **THEN** net exposure is `0.0 * 1 + 0.20 * (-1) = -0.20`

---

### Requirement: Netting collapses pair to single-leg position

After computing net exposure, the engine SHALL replace the pair's weights in the global weight vector:

- If `net_exposure > 0` (net long): `new_w_long = net_exposure / L`, `new_w_short = 0.0`
- If `net_exposure < 0` (net short): `new_w_long = 0.0`, `new_w_short = net_exposure / S`
- If `net_exposure == 0` (perfectly offset): `new_w_long = 0.0`, `new_w_short = 0.0`

Tickers reduced to `0.0` SHALL be removed from the global weight vector.

#### Scenario: Net long with 1x leverage
- **WHEN** net exposure is `0.20` for pair `(QQQ, 1, PSQ, -1)` with original `QQQ=0.30, PSQ=0.10`
- **THEN** weights become `QQQ=0.20, PSQ` removed

#### Scenario: Net short with 3x inverse leverage
- **WHEN** net exposure is `-0.20` for pair `(EEM, 1, EDZ, -3)` with original `EEM=0.10, EDZ=0.10`
- **THEN** weights become `EEM` removed, `EDZ = -0.20 / -3 = 0.0667`

#### Scenario: Perfectly offset
- **WHEN** net exposure is `0.0` for pair `(QQQ, 1, PSQ, -1)` with original `QQQ=0.25, PSQ=0.25`
- **THEN** both `QQQ` and `PSQ` are removed from the weight vector

---

### Requirement: Freed weight allocated to cash ticker or XCASHX

The freed weight from netting SHALL be computed as:

```
freed = (w_long + w_short) - (new_w_long + new_w_short)
```

Freed weight SHALL be accumulated across all netting pairs. The total freed weight SHALL be added to:
- `netting.cash_ticker` if configured (non-null)
- `XCASHX` if `cash_ticker` is null or absent

If the target ticker already has weight in the vector, the freed weight SHALL be added to its existing weight.

#### Scenario: Freed weight to configured cash ticker
- **WHEN** pair `(QQQ, 1, PSQ, -1)` nets `QQQ=0.30, PSQ=0.10` and `cash_ticker` is `"SHV"` and `SHV` has no existing weight
- **THEN** freed weight is `0.40 - 0.20 = 0.20`, `SHV=0.20` is added to the weight vector

#### Scenario: Freed weight to XCASHX when no cash ticker
- **WHEN** pair `(QQQ, 1, PSQ, -1)` nets `QQQ=0.30, PSQ=0.10` and `cash_ticker` is null
- **THEN** freed weight `0.20` is added to `XCASHX`

#### Scenario: Freed weight added to existing cash ticker weight
- **WHEN** `SHV` already has weight `0.30` from the tree and netting frees `0.20` with `cash_ticker="SHV"`
- **THEN** `SHV` weight becomes `0.30 + 0.20 = 0.50`

#### Scenario: Multiple pairs accumulate freed weight
- **WHEN** pair 1 frees `0.10` and pair 2 frees `0.15` with `cash_ticker="BIL"`
- **THEN** `BIL` receives total freed weight `0.25`

---

### Requirement: Netting preserves sum-to-one invariant

After netting, the global weight vector SHALL still sum to `1.0`. The existing sum-to-one assertion (tolerance `1e-9`) SHALL pass after netting is applied.

#### Scenario: Weights sum to one after netting
- **WHEN** pre-netting weights are `{QQQ: 0.30, PSQ: 0.10, GLD: 0.60}` and pair `(QQQ, 1, PSQ, -1)` is netted with `cash_ticker="SHV"`
- **THEN** post-netting weights are `{QQQ: 0.20, GLD: 0.60, SHV: 0.20}` summing to `1.0`

---

### Requirement: Netting is a no-op when config is absent

If `settings.netting` is `None` (not configured), the engine SHALL skip the netting step entirely. The flattened weight vector SHALL pass through unchanged.

#### Scenario: No netting configured
- **WHEN** the strategy has no `netting` block in settings
- **THEN** the global weight vector after flattening is unchanged

#### Scenario: Empty pairs list
- **WHEN** the strategy has `netting: { pairs: [] }` in settings
- **THEN** the global weight vector after flattening is unchanged (no pairs to net)

---

### Requirement: Netting applied on every trading day

Netting SHALL be applied to the flattened weight vector on every trading day, regardless of whether the day is a rebalance day. On non-rebalance days where weights are carried forward, netting SHALL still be applied to the carried-forward flattened output.

#### Scenario: Netting on rebalance day
- **WHEN** the current day is a rebalance day and the downward pass produces weights with both legs of a netting pair
- **THEN** netting is applied to the flattened output

#### Scenario: Netting on carry-forward day
- **WHEN** the current day is not a rebalance day and carried-forward weights contain both legs of a netting pair
- **THEN** netting is applied to the flattened output
