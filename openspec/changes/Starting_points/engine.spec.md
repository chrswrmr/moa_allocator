# engine.spec.md

> ⚠️ Draft — created as a starting point. Finalize during the first OpenSpec change before implementing.

**Module:** `moa_allocations/engine/`  
**Version:** 1.0.0

---

## Responsibility

Execute the daily simulation loop over a compiled Strategy Tree. Drives the two-pass (upward/downward) execution model per trading day and assembles the final allocation DataFrame.

---

## Public Interface

```python
from moa_allocations.engine.runner import Runner

runner = Runner(root: RootNode, price_data: pd.DataFrame)
allocations: pd.DataFrame = runner.run()
```

---

## Input Contracts

### `root: RootNode`

Produced by `compile_strategy()`. Fully instantiated — engine never reads the DSL file.

### `price_data: pd.DataFrame`

Injected by the caller from `pidb_ib`.

| Requirement | Detail |
|---|---|
| Index | `DatetimeIndex`, trading days only, no weekends or holidays |
| Columns | Uppercase ticker strings matching all `asset` nodes in the tree |
| Values | `float` — total-return adjusted closing prices |
| NaN policy | No NaN values permitted anywhere in the backtest window.
             | `pidb_ib` is solely responsible for forward-filling all gaps
             | before returning price data. The engine trusts this guarantee
             | unconditionally and performs no NaN checks at runtime.
             | NaN values in price_data produce undefined behaviour —
             | the fault lies with the caller, not the engine. |
| Date range | Must cover `[settings.start_date - max_lookback_days, settings.end_date]` |

**Validation on init (raises `PriceDataError`):**
- Any ticker referenced in an `asset` node is missing from `price_data.columns`
- `price_data` index does not cover the required date range

```python
class PriceDataError(Exception):
    def __init__(self, message: str): ...
```

---

## Output Contract

```python
allocations: pd.DataFrame
```

| Property | Detail |
|---|---|
| Column `DATE` | ISO 8601 date strings (`YYYY-MM-DD`), first column |
| Remaining columns | Uppercase ticker strings in DSL leaf order; `XCASHX` last if present (see [ARCHITECTURE.md](file:///c:/py/moa_allocator/ARCHITECTURE.md)) |
| Values | `float` in `[0.0, 1.0]`; every row sums to `1.0` |
| Row count | One row per trading day in `[start_date, end_date]` |

**CSV side-effect:** written to `output/allocations.csv` (directory created if absent).

```
DATE,SPY,BND,XCASHX
2024-01-02,0.600,0.400,0.000
2024-01-03,0.600,0.400,0.000
2024-01-04,0.000,0.000,1.000
```

---

## Daily Simulation Loop

For each trading day `t` in `[start_date, end_date]`:

```
1. Upward Pass   (leaves → root)
2. Downward Pass (root → leaves)
3. Collect Global Weight Vector → append row to allocations
```

### Pass A — Upward (Value & Risk)

Direction: leaves → root.

For each `AssetNode` (leaf):
- Look up `price_data.loc[t, ticker]`
- Value is guaranteed valid by pidb_ib contract — no NaN check performed

For each `StrategyNode` (branch), bottom-up:
- Compute daily return from prior-day weights × child returns
- Update `node.nav[t]` = `node.nav[t-1] × (1 + weighted_return)`
- NAV series starts at `1.0` on `start_date`
- **if_else nodes:** Both `true_branch` and `false_branch` have their NAV updated on every Upward Pass, regardless of which branch is currently active. The `if_else` node's own NAV is updated using the prior day's active branch return only. If no prior day exists (day 0), NAV initialises to 1.0.


**Purpose:** ensures parent Algos can compute metrics (SMA, RSI, etc.) over sub-strategy NAV series before making allocation decisions.

### Pass B — Downward (Logic & Push)

Direction: root → leaves.

For each node, top-down, trigger its `AlgoStack`:

```python
for algo in node.algo_stack:
    result = algo(node)
    if not result:
        node.temp['weights'] = {'XCASHX': 1.0}
        break
```

Metric data flow: Algos call compute_metric(series, function, lookback) directly — the engine does not pre-inject scalar metric values into target.temp. The "pre-computed" part means that all price and NAV series are converted to numpy arrays once before the simulation loop begins and stored on target.perm. Algos read these arrays from target.perm and pass them to compute_metric() at call time. compute_metric() operates on np.ndarray only — no DataFrame operations occur inside an Algo.

After AlgoStack completes:
- Normalize `node.temp['weights']` to sum to `1.0`
- Push each child's weight fraction down to child node as its capital allocation

**AlgoStack is derived from node type:**

| Node type | AlgoStack |
|---|---|
| `weight / equal` | `[SelectAll, WeightEqually]` |
| `weight / defined` | `[SelectAll, WeightSpecified]` |
| `weight / inverse_volatility` | `[SelectAll, WeightInvVol]` |
| `filter` | `[SelectTopN or SelectBottomN, WeightEqually]` |
| | *Note: SelectTopN/BottomN calculate the sortMetric for each child separately using that child's series.* |
| `if_else` | `[SelectIfCondition(conditions, logic_mode), WeightEqually()]` |
| `asset` | No AlgoStack — leaf; receives weight from parent |

### AlgoStack construction

AlgoStack construction: Runner.__init__() traverses the compiled tree and attaches an AlgoStack to each StrategyNode based on its type and parameters. The compiler does not attach AlgoStacks — it is strictly structural and must not create a dependency from compiler/ into engine/algos/. Each node's AlgoStack is built once at Runner init time and remains fixed for the duration of the simulation run.

### Global Weight Vector

After the Downward Pass, flatten weights from root → leaves:


```
global_weight(leaf) = ∏ local_weights along path from root → leaf
```

All leaf weights must sum to `1.0`. `XCASHX` is included as a virtual leaf when any AlgoStack halts.

---

## Node State

Each `StrategyNode` carries two state dicts, reset at the start of each day's Downward Pass:

```python
node.temp: dict   # current-day mutable state; reset each day
node.perm: dict   # persistent state across days (e.g. rolling windows)
```

### `temp` keys written by Algos

| Key | Type | Written by |
|---|---|---|
| `temp['selected']` | list[str] — child node ids | Selection Algos |
| `temp['weights']` | dict[str, float] — node id → weight | Weighting Algos |

### `perm` keys (engine-managed)

| Key | Type | Content |
|---|---|---|
| `perm['nav']` | pd.Series | Unitized NAV series for this node |
| `perm['prices']` | pd.DataFrame | Slice of price_data for child tickers |

---

## Rebalance Frequency

The engine only executes the Downward Pass (AlgoStack) on rebalance days. On non-rebalance days, prior weights carry forward.

| `rebalance_frequency` | Rebalance trigger |
|---|---|
| `daily` | Every trading day |
| `weekly` | First trading day of each calendar week |
| `monthly` | First trading day of each calendar month |

**Threshold logic (Scheduled days only):**
If `rebalance_threshold` is set (> 0), a rebalance is triggered ONLY on a scheduled rebalancing day (defined by `rebalance_frequency`) and ONLY if `abs(current_weight - target_weight) >= rebalance_threshold` for any asset.

**Threshold calculation:**
```
drift = abs(current_weight - target_weight)
rebalance if drift >= settings.rebalance_threshold
order_size = target_weight - current_weight
```

On non-rebalance days: Upward Pass still runs (NAV update); Downward Pass is skipped; prior weights copied forward.

---

## NaN & Empty Selection Handling

| Situation | Behaviour |
|---|---|
| AlgoStack returns `False` | 100% weight to `XCASHX` |
| `filter.select.count` > number of children | Select all children |

`XCASHX` is a virtual leaf with weight `1.0` and return `0.0` (no price series required). See [ARCHITECTURE.md](file:///c:/py/moa_allocator/ARCHITECTURE.md) for the definition of the `XCASHX` sentinel.

---

## Unitized NAV

Each `StrategyNode` maintains a synthetic price series:

- Initialised to `1.0` on `start_date - 1`
- Updated each day: `nav[t] = nav[t-1] × (1 + weighted_return[t])`
- `weighted_return[t] = Σ (weight[i,t-1] × return[i,t])` over selected children
- Stored in `node.perm['nav']` as a rolling `pd.Series`

The NAV series is used by parent Algos as if the sub-strategy were a single ticker. This enables condition evaluation and filter sorting over sub-strategies.

**Memory model:** `O(S × T)` where `S` = number of `StrategyNode` instances, `T` = number of trading days.

---

## Edge Cases

| Case | Behaviour |
|---|---|
| `start_date` falls on a non-trading day | Advance to next available trading day in `price_data.index` |
| `end_date` falls on a non-trading day | Use last available trading day on or before `end_date` |
| Single child in `weight` node | 100% weight to that child |
| `if_else` condition references a ticker not in `price_data` | `PriceDataError` raised at init, not at runtime |
| Lookback window extends before `price_data` start | Metric returns `NaN`; asset treated as excluded |
