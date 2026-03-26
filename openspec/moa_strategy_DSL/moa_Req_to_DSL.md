# MoaEdge DSL 1.0.0 — Building Blocks Reference

version-dsl 1.0.0

Building blocks describe the backtest. Each block is simple and can be configured by the user. They can be nested to depict comprehensive trading systems.

---

## Settings

The root node of every backtest. Exists exactly once per strategy definition.

### User-Configurable Parameters

- **id** — Unique identifier for the backtest
- **name** — Name of the backtest
- **starting_cash** — Initial capital
- **start_date / end_date** — Backtest date range
- **slippage** — Slippage assumption
- **fees** — Transaction fee assumption
- **rebalance_frequency** — One of: `daily`, `weekly`, `monthly`
- **rebalance_threshold** — Optional; percentage drift (e.g., 0.05 for 5%) that triggers rebalance on any scheduled rebalancing day it is exceeded
- **netting** — Optional; declares long/short ETF pairs to be netted in the output weight vector (see Netting section below)

### Threshold Rebalancing

Triggers a rebalance on a scheduled rebalancing day (defined by `rebalance_frequency`) only if an asset's deviation from its target weight exceeds a specific percentage.

- **Drift Calculation:** `Drift = abs(Current_Weight - Target_Weight)`
- **Rebalance Trigger:** `IF Drift >= Threshold`
- **Execution Goal:** `Order_Size = Target_Weight - Current_Weight`

### Position in Tree

This block is the **root node** and exists only once per backtest.

### Schema

```json
"settings": {
  "type": "object",
  "required": ["id", "name", "starting_cash", "start_date", "end_date", "rebalance_frequency"],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "name": { "type": "string" },
    "starting_cash": { "type": "number", "default": 100000 },
    "start_date": { "type": "string", "format": "date" },
    "end_date": { "type": "string", "format": "date" },
    "slippage": { "type": "number", "default": 0.0005 },
    "fees": { "type": "number", "default": 0.0 },
    "rebalance_frequency": { "enum": ["daily", "weekly", "monthly"] },
    "rebalance_threshold": { "type": "number", "description": "Percentage (e.g., 0.05 for 5%)" },
    "netting": {
      "type": "object",
      "required": ["pairs"],
      "properties": {
        "pairs": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["long_ticker", "long_leverage", "short_ticker", "short_leverage"],
            "properties": {
              "long_ticker": { "type": "string" },
              "long_leverage": { "type": "number", "exclusiveMinimum": 0 },
              "short_ticker": { "type": "string" },
              "short_leverage": { "type": "number", "exclusiveMaximum": 0 }
            },
            "additionalProperties": false
          }
        },
        "cash_ticker": { "type": ["string", "null"] }
      },
      "additionalProperties": false
    }
  }
}
```

### Example

```json
"settings": {
  "id": "a2b3c4d5-e6f7-8901-2345-67890abcdef1",
  "name": "Aggressive Tech Momentum",
  "starting_cash": 100000,
  "start_date": "2023-01-01",
  "end_date": "2026-01-01",
  "slippage": 0.001,
  "fees": 1.0,
  "rebalance_frequency": "monthly",
  "rebalance_threshold": 0.05
}
```

### Netting

When a strategy tree can independently route weight to both a long ETF and its leveraged inverse (e.g. QQQ and PSQ), the flattened output may contain offsetting positions. The `netting` block collapses each declared pair into a single net position and redirects the freed weight to a cash ticker or `XCASHX`.

**How it works:**

For each pair `(long_ticker, L, short_ticker, S)` where `L > 0` and `S < 0`:

```
net_exposure = w_long × L + w_short × S
```

- If `net_exposure > 0` → hold only the long leg at `net_exposure / L`
- If `net_exposure < 0` → hold only the short leg at `net_exposure / S`
- If `net_exposure == 0` → both legs are removed entirely

Freed weight = `(w_long + w_short) − (new_w_long + new_w_short)` is added to `cash_ticker` (if specified) or `XCASHX`.

**Constraints:**

- `long_leverage` must be `> 0` (e.g. `1` for a standard long ETF)
- `short_leverage` must be `< 0` (e.g. `-1` for a 1× inverse, `-3` for a 3× inverse)
- Each ticker may appear in at most one pair
- Both tickers in a pair must exist as asset leaves in the strategy tree
- `long_ticker` and `short_ticker` within a pair must differ
- Netting is applied on every trading day (rebalance and carry-forward days)
- The sum-to-one invariant is preserved after netting

> **v1 limitation:** The Upward Pass (NAV computation) uses raw un-netted weights. The backtested NAV reflects holding both legs; live execution holds only the netted position. Divergence is minimal for 1× inverse pairs.

### Example

```json
"settings": {
  "id": "a2b3c4d5-e6f7-8901-2345-67890abcdef1",
  "name": "Momentum with Netting",
  "starting_cash": 100000,
  "start_date": "2023-01-01",
  "end_date": "2026-01-01",
  "rebalance_frequency": "monthly",
  "netting": {
    "pairs": [
      {
        "long_ticker": "QQQ",
        "long_leverage": 1,
        "short_ticker": "PSQ",
        "short_leverage": -1
      },
      {
        "long_ticker": "EEM",
        "long_leverage": 1,
        "short_ticker": "EDZ",
        "short_leverage": -3
      }
    ],
    "cash_ticker": "SHV"
  }
}
```

---

## If/Else

Routes decision flow into one of two branches based on whether a condition is met.

### Multiple Conditions

Conditions are linked by a `logic_mode`:

- **all** — All conditions must be true
- **any** — At least one condition must be true

### Condition Structure

Each condition follows a four-part comparison syntax:

```
[LHS] — [Comparator] — [RHS] for last [x] days
```

**Supported metrics (LHS and RHS):**

- Current Price
- Cumulative Return
- Exponential Moving Average (EMA) of Price
- Moving Average (SMA) of Price
- Moving Average (SMA) of Return
- Max Drawdown
- Relative Strength Index (RSI)
- Standard Deviation of Price
- Standard Deviation of Return

**Comparators:** `greater_than`, `less_than`

**RHS Toggle:**
- **Off (default):** RHS is a dynamic metric (function of an asset)
- **On:** RHS accepts a static numeric value

**Duration:** Specifies how many consecutive days an individual condition must persist before triggering.

### Position in Tree

Can be a top-level node (directly under root) or anywhere in the middle. **Cannot be a leaf node.**

### Schema

```json
{
  "type": "object",
  "required": ["id", "type", "logic_mode", "conditions", "true_branch", "false_branch"],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "name": { "type": "string", "description": "Optional descriptive name (e.g., 'Bull/Bear Filter')." },
    "type": { "const": "if_else" },
    "logic_mode": { "enum": ["all", "any"] },
    "conditions": { "type": "array", "items": { "$ref": "#/definitions/condition" } },
    "true_branch": { "$ref": "#/definitions/node" },
    "false_branch": { "$ref": "#/definitions/node" }
  }
}
```

### Example

```json
{
  "id": "7878696d-352b-456c-8c4d-617374657231",
  "name": "Market Regime Router",
  "type": "if_else",
  "logic_mode": "all",
  "conditions": [{
    "lhs": { "asset": "SPY", "function": "current_price" },
    "comparator": "greater_than",
    "rhs": { "asset": "SPY", "function": "sma_price", "lookback": "200d" },
    "duration": "3d"
  }],
  "true_branch": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Bull Branch",
    "type": "asset",
    "ticker": "TQQQ"
  },
  "false_branch": {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "name": "Bear Branch",
    "type": "asset",
    "ticker": "BIL"
  }
}
```

---

## Weight

Distributes allocations across a list of assets and/or sub-strategies.

### Weighting Methods

- **equal** — Equal allocation across all children
- **defined** — Manually specified weights per child
- **inverse_volatility** — Weights inversely proportional to volatility; lookback period is configurable

### Position in Tree

Can be a top-level node (directly under root) or anywhere in the middle.

### Schema

```json
{
  "type": "object",
  "required": ["id", "type", "method", "children"],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "name": { "type": "string" },
    "type": { "const": "weight" },
    "method": { "enum": ["equal", "defined", "inverse_volatility"] },
    "method_params": {
      "type": "object",
      "properties": {
        "lookback": { "type": "string" },
        "custom_weights": { "type": "object" }
      }
    },
    "children": { "type": "array", "items": { "$ref": "#/definitions/node" } }
  }
}
```

### Example

```json
{
  "id": "ad8e7f50-3d3f-4e5a-a6c7-9b2d1c0e9f8a",
  "name": "60/40 Split",
  "type": "weight",
  "method": "defined",
  "method_params": {
    "custom_weights": {
      "0e9f8a7b-6c5d-4e3f-2b1a-0d9c8b7a6f5e": 0.6,
      "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d": 0.4
    }
  },
  "children": [
    { "id": "0e9f8a7b-6c5d-4e3f-2b1a-0d9c8b7a6f5e", "name": "Stocks", "type": "asset", "ticker": "VTI" },
    { "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d", "name": "Bonds", "type": "asset", "ticker": "BND" }
  ]
}
```

---

## Filter

Sorts and selects a subset of assets or sub-strategies based on a metric.

### Sort By

- Current Price
- Cumulative Return
- Exponential Moving Average of Price
- Max Drawdown
- Moving Average of Price
- Moving Average of Return
- Relative Strength Index
- Standard Deviation of Price
- Standard Deviation of Return

### Select

- **Top X** — Keep the top X by the sort metric
- **Bottom X** — Keep the bottom X by the sort metric

### Weighting

Filter survivors are always weighted equally. There is no `method` field on the filter node — equal weighting is the only supported mode in DSL version 1.0. Additional weighting methods may be added in a future DSL version.

### Position in Tree

Can be a top-level node (directly under root) or anywhere in the middle.

### Schema

```json
{
  "id": { "type": "string", "format": "uuid" },
  "name": { "type": "string" },
  "type": { "const": "filter" },
  "sort_by": { "$ref": "#/definitions/sortMetric" },
  "select": {
    "type": "object",
    "properties": {
      "mode": { "enum": ["top", "bottom"] },
      "count": { "type": "integer" }
    }
  },
  "children": { "type": "array", "items": { "$ref": "#/definitions/node" } }
}
```

### Example

```json
{
  "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
  "name": "Top Alpha Selector",
  "type": "filter",
  "sort_by": { "function": "cumulative_return", "lookback": "126d" },
  "select": { "mode": "top", "count": 1 },
  "children": [
    { "id": "3f2e1d0c-9b8a-7f6e-5d4c-1a2b3c4d5e6f", "name": "SPY", "type": "asset", "ticker": "SPY" },
    {
      "id": "2b1a0d9c-8b7a-6f5e-4d3c-2b1a0d9c8b7a",
      "name": "Synthetic Tech",
      "type": "weight",
      "method": "equal",
      "children": [
        { "id": "9f8e7d6c-5b4a-4321-8888-999900001111", "type": "asset", "ticker": "NVDA" },
        { "id": "e458e692-7711-479c-9c7d-e9f0d1a49f7e", "type": "asset", "ticker": "MSFT" }
      ]
    }
  ]
}
```

### Key Characteristics

- **Relative Ranking** — The Filter calculates the specified metric for each child node independently using that child's own price or NAV series.
- **Encapsulation** — The Filter ignores the internal children of a sub-strategy for selection, but they must still be defined in the JSON so the engine can calculate the sub-strategy's value.
- **Selection logic** — Only the top/bottom "survivors" pass through to the parent node.

---

## Asset

Defines a single tradeable asset that may receive an allocation.

### Position in Tree

**Leaf node only.** Cannot have children.

### Schema

```json
{
  "id": { "type": "string", "format": "uuid" },
  "name": { "type": "string" },
  "type": { "const": "asset" },
  "ticker": { "type": "string" }
}
```

### Example

```json
{
  "id": "3f2e1d0c-9b8a-7f6e-5d4c-1a2b3c4d5e6f",
  "name": "S&P 500 ETF",
  "type": "asset",
  "ticker": "SPY"
}
```