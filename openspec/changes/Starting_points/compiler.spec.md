# compiler.spec.md

> ⚠️ Draft — created as a starting point. Finalize during the first OpenSpec change before implementing.

**Module:** `moa_allocations/compiler/`  
**Version:** 1.0.0  
**DSL Schema:** `moa_DSL_schema.json` version `1.0.0`

---

## Responsibility

Parse, validate, and instantiate a `.moastrat.json` file into a live Strategy Tree ready for the engine. This is the only module that reads the DSL file. Everything downstream works with the instantiated tree.

---

## Public Interface

```python
from moa_allocations.compiler import compile_strategy

root: RootNode = compile_strategy("path/to/strategy.moastrat.json")
```

### `compile_strategy(path: str) -> RootNode`

| Step | Action |
|---|---|
| 1 | Load and parse JSON from `path` |
| 2 | Validate top-level structure against `moa_DSL_schema.json` |
| 3 | Validate semantic rules (see below) |
| 4 | Recursively instantiate the node tree from `root_node` |
| 5 | Return the `RootNode` instance |

Raises `DSLValidationError` on any failure. Never returns a partially built tree.

---

## Input: `.moastrat.json` Top-Level Structure

```json
{
  "id": "<uuid>",
  "version-dsl": "1.0.0",
  "settings": { ... },
  "root_node": { ... }
}
```

### Required top-level fields

| Field | Type | Rule |
|---|---|---|
| `id` | string (uuid) | Must be valid UUID v4 |
| `version-dsl` | string | Must equal `"1.0.0"` exactly |
| `settings` | object | See Settings spec below |
| `root_node` | object | Must be a valid node (see Node Types) |

---

## Settings Object

### Required fields

| Field | Type | Validation |
|---|---|---|
| `id` | string (uuid) | Valid UUID |
| `name` | string | Non-empty |
| `starting_cash` | number | > 0 |
| `start_date` | string (date) | ISO 8601; must be before `end_date` |
| `end_date` | string (date) | ISO 8601; must be after `start_date` |
| `rebalance_frequency` | enum | One of: `daily`, `weekly`, `monthly` |

### Optional fields

| Field | Type | Rule |
|---|---|---|
| `slippage` | number | Default `0.0005`; must be >= 0 |
| `fees` | number | Default `0.0`; must be >= 0 |
| `rebalance_threshold` | number | Optional; if set > 0, rebalance only occurs on scheduled days where drift >= threshold; must be < 1 |

**Semantic rule:** `rebalance_threshold` cannot be negative.

---

## Node Types

Every node must have `id` (valid UUID) and `type` (one of the four values below). `name` is optional on all node types.

### `if_else`

Routes allocation into one of two branches based on conditions.

**Required fields:**

| Field | Type | Rule |
|---|---|---|
| `type` | const | `"if_else"` |
| `logic_mode` | enum | `"all"` or `"any"` |
| `conditions` | array | At least 1 condition; each must be a valid condition object |
| `true_branch` | node | Any valid node type |
| `false_branch` | node | Any valid node type |

**Position rule:** Cannot be a leaf (both branches must resolve to a child node).

#### Condition object

```json
{
  "lhs": { "asset": "SPY", "function": "current_price" },
  "comparator": "greater_than",
  "rhs": { "asset": "SPY", "function": "sma_price", "lookback": "200d" },
  "duration": "3d"
}
```

| Field | Type | Rule |
|---|---|---|
| `lhs` | conditionMetric | Required |
| `comparator` | enum | `"greater_than"` or `"less_than"` |
| `rhs` | number or conditionMetric | Either a static scalar or a conditionMetric |
| `duration` | time_offset | Optional; default `"1d"` |

**Duration semantics:** condition must hold true on every day in the trailing `duration` window. `"1d"` = single-day check.

#### conditionMetric object (Used by If/Else)

```json
{ "asset": "SPY", "function": "sma_price", "lookback": "200d" }
```

| Field | Type | Rule |
|---|---|---|
| `asset` | string | Uppercase ticker; must be present in price data at runtime |
| `function` | enum | See metric functions table below |
| `lookback` | time_offset | Required for all functions except `current_price` |

#### sortMetric object (Used by Filter)

```json
{ "function": "rsi", "lookback": "14d" }
```

| Field | Type | Rule |
|---|---|---|
| `function` | enum | See metric functions table below |
| `lookback` | time_offset | Required for all functions except `current_price` |

**Metric functions:**

| `function` | Lookback required |
|---|---|
| `current_price` | No |
| `cumulative_return` | Yes |
| `ema_price` | Yes |
| `sma_price` | Yes |
| `sma_return` | Yes |
| `max_drawdown` | Yes |
| `rsi` | Yes |
| `std_dev_price` | Yes |
| `std_dev_return` | Yes |

**time_offset format:** string matching `^[0-9]+[dwm]$` — e.g. `"200d"`, `"4w"`, `"3m"`.  
Compiler converts to integer trading days: `1w = 5d`, `1m = 21d`.

---

### `weight`

Distributes capital across children using a weighting method.

**Required fields:**

| Field | Type | Rule |
|---|---|---|
| `type` | const | `"weight"` |
| `method` | enum | `"equal"`, `"defined"`, or `"inverse_volatility"` |
| `children` | array | At least 1 child node |

**Optional:**

| Field | Type | Rule |
|---|---|---|
| `method_params.lookback` | time_offset | Required when `method == "inverse_volatility"` |
| `method_params.custom_weights` | object | Required when `method == "defined"` |

**Semantic rules for `method == "defined"`:**
- `custom_weights` keys must be node `id` strings matching the `children` array
- `custom_weights` values must sum to `1.0` (tolerance ± 0.001)
- Every child node `id` must have a corresponding `custom_weights` entry

---

### `filter`

Ranks children by a metric and selects the top or bottom N.

**Required fields:**

| Field | Type | Rule |
|---|---|---|
| `type` | const | `"filter"` |
| `sort_by` | sortMetric | The metric used to rank children |
| `select.mode` | enum | `"top"` or `"bottom"` |
| `select.count` | integer | >= 1; must not exceed the number of children |
| `children` | array | At least 1 child node |

**Encapsulation rule:** the filter ranks each child by its aggregated NAV series, not by the children's internal sub-weights. Sub-strategy children must still be fully defined so the engine can compute their NAV.

---

### `asset`

A leaf node representing a single tradeable ticker.

**Required fields:**

| Field | Type | Rule |
|---|---|---|
| `type` | const | `"asset"` |
| `ticker` | string | Non-empty uppercase string |

**Position rule:** Leaf only — must have no children. Cannot appear as a branch node.

---

## Semantic Validation Rules (beyond schema)

These run after JSON Schema validation passes:

| Rule | Check |
|---|---|
| **UUID uniqueness** | All node `id` values in the file must be unique |
| **defined weights completeness** | Every child `id` of a `defined` weight node must appear in `custom_weights` |
| **defined weights sum** | `custom_weights` values must sum to `1.0` ± 0.001 |
| **filter count bound** | `select.count` must be <= `len(children)` |
| **lookback required** | All metric objects except `current_price` must have `lookback` |
| **asset is leaf** | Nodes of type `asset` must not appear as `true_branch`/`false_branch` parent containers; they are always terminals |
| **date ordering** | `start_date` < `end_date` |

---

## Output: Node Class Hierarchy

The compiler instantiates the following classes (defined in `engine/`):

```
BaseNode
├── StrategyNode      ← if_else, weight, filter
│   ├── if_else       → holds conditions + true_branch + false_branch
│   ├── weight        → holds method + method_params + children[]
│   └── filter        → holds sort_by + select + children[]
└── AssetNode      ← asset → holds ticker
```

`RootNode` is a `StrategyNode` wrapping the top-level `root_node` from the DSL, with `settings` attached.

### `RootNode` attributes

| Attribute | Type | Source |
|---|---|---|
| `settings` | `Settings` dataclass | Compiled from `settings` block |
| `root` | `StrategyNode \| AssetNode` | Compiled from `root_node` |

### `Settings` dataclass

```python
@dataclass
class Settings:
    id: str
    name: str
    starting_cash: float
    start_date: date
    end_date: date
    slippage: float
    fees: float
    rebalance_frequency: str          # "daily" | "weekly" | "monthly"
    rebalance_threshold: float | None
```

---

## Error Handling

All errors raise `DSLValidationError`:

```python
class DSLValidationError(Exception):
    def __init__(self, node_id: str, node_name: str, message: str): ...
```

For top-level errors (missing `version-dsl`, invalid `settings`), use `node_id = "root"` and `node_name = "settings"`.

**Example messages:**

```
DSLValidationError: node_id='ad8e7f50' name='60/40 Split' — custom_weights sum to 0.95, expected 1.0 ± 0.001
DSLValidationError: node_id='root' name='settings' — rebalance_threshold must be between 0.0 and 1.0
DSLValidationError: node_id='c9bf9e57' name='Top Alpha Selector' — select.count (5) exceeds children count (3)
```

---

## Edge Cases

| Case | Behaviour |
|---|---|
| `version-dsl` is not `"1.0.0"` | Raise `DSLValidationError` immediately — do not attempt partial parsing |
| Duplicate node `id` | Raise `DSLValidationError` naming both conflicting nodes |
| `custom_weights` has extra keys not in `children` | Raise `DSLValidationError` — strict match required |
| `filter` with `select.count == len(children)` | Valid — selects all; compiler allows it, engine handles it |
| `if_else` with empty `conditions` array | Raise `DSLValidationError` — at least 1 condition required |
