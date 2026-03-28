## Context

`collect_tickers()` in `runner.py` builds the set of tickers that must have price data before simulation can begin. For netting, it unconditionally adds `settings.netting.cash_ticker` to this set. This is correct for real assets (e.g. `"SHV"`) but wrong for `"xcashx"`, which is the synthetic cash sentinel — an engine-internal construct that carries a hardcoded 0% daily return and is never looked up in `price_data`.

The engine already has a consistent, working model for `XCASHX`: it is injected dynamically during the downward pass, handled in the upward pass with `child_return = 0.0`, and accumulated in `_flatten_weights()` — all without any price array. The bug is that one code path (`collect_tickers`) does not know about this special case.

## Goals / Non-Goals

**Goals:**
- Make `cash_ticker: "xcashx"` (any case) work without requiring price data.
- Keep the fix local and minimal — one guard, one spec update, one new test scenario.

**Non-Goals:**
- Earning interest on cash (XCASHX return stays 0%).
- Changing how real asset `cash_ticker` values (e.g. `"SHV"`) work — they still require prices.
- Validating or normalising any other netting fields.

## Decisions

### Decision: Guard in `collect_tickers()`, not in `Runner.__init__()` validation

**Chosen:** Skip adding `cash_ticker` to the collected set when it equals the sentinel, inside `collect_tickers()`.

**Alternative considered:** Keep `collect_tickers()` unchanged and add an exclusion to the missing-ticker check in `Runner.__init__()`.

**Rationale:** `collect_tickers()` is the single authoritative source for "what tickers need prices". Fixing the membership there keeps the validation code clean and unsurprised — it never receives the sentinel in the first place, consistent with how XCASHX is never present in any price array anywhere else.

### Decision: Case-insensitive comparison (`cash_ticker.upper() == "XCASHX"`)

**Chosen:** Normalise to uppercase before comparing to the sentinel literal.

**Alternative considered:** Exact case match on `"xcashx"` only.

**Rationale:** The DSL schema accepts `cash_ticker` as a free-form string. Users may write `"xcashx"`, `"XCASHX"`, or `"XCashX"`. Case-insensitive matching eliminates a whole class of future confusion at negligible cost.

## Risks / Trade-offs

- **Risk: A user deliberately names a real tradeable ETF `"xcashx"`** → Mitigation: This is a reserved sentinel name. It is documented as such; no real instrument uses this ticker. Risk is theoretical.
- **Trade-off: Sentinel is now implicit, not enforced by schema** → The DSL schema does not restrict `cash_ticker` to a list of values, so the sentinel must be recognised by convention. This is already the case today for the `XCASHX` string produced by `_downward_pass()` — no schema change needed.
