## Context

The engine's two-pass architecture (Upward → Downward → Flatten) produces a global weight vector mapping each leaf ticker to its portfolio share. Because nodes are context-blind (P2), different branches can independently select both a long ETF and its leveraged inverse — producing offsetting positions in the flattened output. This is economically wasteful: it doubles fees, spreads, and tracking error for a net exposure achievable with a single leg.

The `Settings` dataclass currently holds rebalance configuration. It is the natural home for strategy-wide execution hints like netting, since netting is a strategy-level policy that applies uniformly across all trading days.

## Goals / Non-Goals

**Goals:**
- Allow the strategy author to declare long/short netting pairs in the DSL `settings` block
- Net offsetting positions in the flattened global weight vector, collapsing each pair to a single-leg position
- Redirect freed weight to a configurable cash ticker or `XCASHX`
- Preserve the sum-to-one invariant after netting
- Keep the change additive — strategies without `netting` behave identically

**Non-Goals:**
- NAV-aware netting (v2 concern): the upward pass continues to use raw un-netted weights. The backtested NAV reflects both legs' returns, not the netted position. This is acceptable because inverse ETFs track closely (especially 1x) and the engine does not model fees or spreads internally.
- Netting across more than two tickers in a group (e.g., three-way netting)
- Automatic detection of inverse pairs — the user must explicitly declare them

## Decisions

### Decision 1: Netting is a post-flatten transformation, not an algo or node type

Netting operates on the global weight dict returned by `_flatten_weights()`, not on per-node local weights. This keeps it outside the tree and respects P2 (Context-Blind) and P3 (AlgoStack is only logic gate). The tree's allocation logic is unchanged; netting is a strategy-level execution optimization applied to the output.

**Alternative considered:** Making netting an algo wrapping the root node. Rejected because it would require the root to know about specific leaf tickers — violating P5 (NAV Encapsulation) and adding complexity to the AlgoStack pipeline.

**Alternative considered:** Netting as a post-processing step outside the engine (in `__init__.py` or `main.py`). Rejected because the netting config is part of the strategy DSL and should be executed by the engine, not the caller. It also needs to integrate with the daily loop for logging and potential future NAV-aware netting.

### Decision 2: DSL shape — nested `netting` object in `settings`

```json
"settings": {
  "netting": {
    "pairs": [
      {
        "long_ticker": "QQQ",
        "long_leverage": 1,
        "short_ticker": "PSQ",
        "short_leverage": -1
      }
    ],
    "cash_ticker": "SHV"
  }
}
```

- `netting` is optional. If absent or `null`, netting is a no-op.
- `pairs` is an array of pair objects. Each pair has four fields: `long_ticker` (str), `long_leverage` (positive number), `short_ticker` (str), `short_leverage` (negative number).
- `cash_ticker` is optional (nullable). If `null` or absent, freed weight goes to `XCASHX`.

**Alternative considered:** Flat top-level keys (`netting_pairs`, `netting_cash_ticker`). Rejected because grouping under a single object makes the schema cleaner — the feature is either present (with its sub-fields) or absent.

### Decision 3: Leverage factors are signed by convention

`long_leverage` must be > 0 (e.g., 1 for a standard long ETF). `short_leverage` must be < 0 (e.g., -1 for a 1x inverse, -3 for a 3x inverse). The sign encodes the direction, so the netting formula is simply:

```
net_exposure = w_long * long_leverage + w_short * short_leverage
```

This matches the user's proposed format and is intuitive: the leverage factor represents economic exposure per dollar invested.

### Decision 4: Netting math

For each pair `(long_ticker, L, short_ticker, S)` where `L > 0` and `S < 0`:

```
net_exposure = w_long * L + w_short * S

if net_exposure > 0:          # net long
    new_w_long  = net_exposure / L
    new_w_short = 0.0
elif net_exposure < 0:         # net short
    new_w_long  = 0.0
    new_w_short = net_exposure / S    # S < 0, so this yields positive weight
else:                          # perfectly offset
    new_w_long  = 0.0
    new_w_short = 0.0

freed = (w_long + w_short) - (new_w_long + new_w_short)
```

Freed weight is accumulated across all pairs and then assigned to `cash_ticker` or `XCASHX`.

### Decision 5: Netting cash ticker included in ticker collection

If `netting.cash_ticker` is specified and is not already a leaf in the tree, it must still be included in the ticker set for price fetching. This is necessary because the output DataFrame will contain this ticker as a column, and downstream systems (`bt_rebalancer`, `iba`) need its price data.

The `collect_tickers()` function in `runner.py` will be extended (or the caller in `__init__.py` will add it) to include the netting cash ticker.

### Decision 6: New column ordering for netting cash ticker

The netting cash ticker may not be a DSL leaf. If it appears in the output, it is inserted after all DSL leaf columns but before `XCASHX` (if present). This follows the existing convention that `XCASHX` is always last.

### Decision 7: Netting applied on every day (rebalance and carry-forward)

Netting applies to the flattened weight vector on every trading day, regardless of whether it was a rebalance day. On carry-forward days, the raw weights are carried forward and then netted. This ensures the output always shows netted positions.

## Risks / Trade-offs

**[NAV divergence]** → The backtested NAV reflects holding both legs, but live execution holds only the netted position. The NAV will slightly differ from actual P&L. → *Mitigation:* Document this as a known v1 limitation. For 1x inverse pairs, the divergence is minimal. Users who need exact NAV can restructure their tree to avoid conflicts. Future v2 can add NAV-aware netting.

**[DSL schema change requires ADR]** → Per project rules, modifying `moa_DSL_schema.json` requires a new ADR in `DECISIONS.md`. → *Mitigation:* Create the ADR as part of the implementation tasks.

**[Ticker collision with tree leaves]** → If `cash_ticker` is the same as an existing leaf ticker (e.g., the tree already allocates to SHV via another branch), the freed weight is simply added to that ticker's existing allocation. This is correct behavior — no special handling needed.

**[Pair ordering]** → If netting pairs share a ticker (disallowed by validation), applying pairs in different orders could yield different results. → *Mitigation:* Semantic validation enforces that no ticker appears in more than one netting pair.

## Open Questions

None — the explore session resolved all design questions. Option A (output-only netting) is confirmed as the approach.
