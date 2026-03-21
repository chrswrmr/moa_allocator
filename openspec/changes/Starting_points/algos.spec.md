# algos.spec.md

> ⚠️ Draft — created as a starting point. Finalize during the first OpenSpec change before implementing.

**Module:** `moa_allocations/engine/algos/`  
**Version:** 1.0.0

---

## Responsibility

Atomic, callable units of selection and weighting logic. Each Algo performs exactly one task within an AlgoStack. Algos are stateless beyond what is passed via `target`.

---

## The Algo Contract

Every Algo is a callable class:

```python
class BaseAlgo:
    def __init__(self, **params):
        # Store static parameters set at compile time
        ...

    def __call__(self, target: StrategyNode) -> bool:
        # Read:  target.temp  — current-day mutable state
        #        target.perm  — persistent state across days
        # Write: target.temp['selected']  — list of selected child node ids
        #        target.temp['weights']   — dict of {node_id: float}
        # Return True  → proceed to next Algo in stack
        # Return False → halt stack; engine defaults node to 100% XCASHX (see [ARCHITECTURE.md](file:///c:/py/moa_allocator/ARCHITECTURE.md))
        ...
```

### Hard rules (enforced by code review and tests)

- Algos must not access global state
- Algos must not reach into sibling, parent, or grandparent nodes
- Algos must not perform DataFrame operations — receive pre-computed scalars or numpy arrays via `target.temp`
- Algos must not modify `target.perm` — that is engine-managed
- Returning `False` is not an error — it is a valid control signal (e.g. condition not met)

---

## Selection Algos

Selection Algos write to `target.temp['selected']` — a list of child node ids that pass through to the Weighting Algo.

---

### `SelectAll`

Selects all children of the node. Used by all `weight` node types.

```python
class SelectAll(BaseAlgo):
    def __call__(self, target) -> bool:
        target.temp['selected'] = [child.id for child in target.children]
        return True  # all prices guaranteed valid by pidb_ib contract
```

**Parameters:** none  
**Halts on:** never

---

### `SelectTopN`

Ranks children by a metric and selects the top N. Used by `filter` nodes with `select.mode == "top"`.

```python
class SelectTopN(BaseAlgo):
    def __init__(self, n: int, metric: str, lookback: int): ...
```

**Parameters:**

| Param | Type | Source |
|---|---|---|
| `n` | int | `filter.select.count` |
| `metric` | str | `filter.sort_by.function` |
| `lookback` | int | `filter.sort_by.lookback` (converted to trading days) |

**Behaviour:**
1. For each child, compute `metric` over the child's NAV series (or price series for `asset` leaves)
2. Rank children descending by metric value
3. Select top `n`; write ids to `target.temp['selected']`
4. Return `True` if at least 1 selected; `False` (→ XCASHX) if none
   (can only occur if n = 0, which the compiler rejects — so SelectTopN
   effectively never returns False)

**Halts on:** never in practice — compiler enforces select.count >= 1

---

### `SelectBottomN`

Identical to `SelectTopN` but ranks ascending. Used by `filter` nodes with `select.mode == "bottom"`.

```python
class SelectBottomN(BaseAlgo):
    def __init__(self, n: int, metric: str, lookback: int): ...

**Behaviour:**
1. For each child, compute `metric` over the child's NAV series (or price series for `asset` leaves)
2. Rank children ascending by metric value
3. Select top `n`; write ids to `target.temp['selected']`
4. Return `True` if at least 1 selected; `False` (→ XCASHX) if none
   (can only occur if n = 0, which the compiler rejects — so SelectBottomN
   effectively never returns False)

**Halts on:** never in practice — compiler enforces select.count >= 1
```

---

### `SelectIfCondition`

Evaluates one or more conditions and routes to `true_branch` or `false_branch`. Used by `if_else` nodes.

```python
class SelectIfCondition(BaseAlgo):
    def __init__(self, conditions: list[Condition], logic_mode: str): ...
```

**Parameters:**

| Param | Type | Source |
|---|---|---|
| `conditions` | list[Condition] | `if_else.conditions` (each with its own `duration`) |
| `logic_mode` | str | `"all"` or `"any"` |

**Behaviour:**
1. For each condition:
   - Evaluate `lhs_metric [comparator] rhs_metric_or_scalar`
   - Apply its specific duration window: evaluate the comparison independently at each of the last condition.duration trading days (indices [t - duration + 1, t]). The condition passes only if every single day in that window returns True. A single False or NaN day fails the entire condition.
2. Combine results with `logic_mode`:
   - `"all"` → AND across all conditions
   - `"any"` → OR across all conditions
3. If combined result is `True`: write `[true_branch.id]` to `target.temp['selected']`
4. If combined result is `False`: write `[false_branch.id]` to `target.temp['selected']`
5. Always returns `True` — selection always resolves to exactly one branch; `WeightEqually` then assigns `1.0` to it

**Note:** `if_else` is structurally identical to a `filter(top 1)` over two children. The condition is simply a selection mechanism. `WeightEqually` handles the 1.0 assignment — no special weighting logic inside this Algo.

**Condition evaluation:**

```python
# Evaluated per condition in the loop.
# duration is an integer number of trading days (already converted from DSL string by compiler).
# The condition must hold true on EVERY day in the trailing window [t - duration + 1, t].
# This requires evaluating the comparison at each day in the window, not just at t.

def _evaluate_condition_at_day(series_np: np.ndarray, day_idx: int,
                                condition: Condition) -> bool:
    # Slice series up to and including day_idx for metric computation
    lhs_series = series_np[:day_idx + 1]
    lhs_value = compute_metric(lhs_series, condition.lhs.function, condition.lhs.lookback)

    if isinstance(condition.rhs, (int, float)):
        rhs_value = condition.rhs
    else:
        rhs_series = target.perm['price_arr'][condition.rhs.asset][:day_idx + 1]
        rhs_value = compute_metric(rhs_series, condition.rhs.function, condition.rhs.lookback)

    if np.isnan(lhs_value) or (not isinstance(condition.rhs, (int, float)) and np.isnan(rhs_value)):
        return False  # NaN on any day in the window → condition fails

    if condition.comparator == "greater_than":
        return lhs_value > rhs_value
    else:
        return lhs_value < rhs_value

# Check condition holds on every day in [t - duration + 1 ... t]
# t_idx is the current day's integer index into the price array
window_start = max(0, t_idx - condition.duration + 1)
result = all(
    _evaluate_condition_at_day(lhs_series_np, day_idx, condition)
    for day_idx in range(window_start, t_idx + 1)
)
```

Duration semantics — precise definition:

- duration = 1  → single-day check at t only. Equivalent to no duration requirement.
- duration = 3  → condition must be True at t, t-1, and t-2. All three must pass.
- If the available history is shorter than duration (e.g. day 2 of the backtest,
  duration = 5), evaluate only the available days — do not fail the condition solely
  because the window is shorter than duration.
- A NaN metric value on any day within the window causes that day's check to return
  False, which causes the entire duration check to fail, which routes to false_branch.
- duration is converted from DSL time_offset string to integer trading days by the
  compiler before being stored on the Condition object. Algos receive integers only.


---

## Weighting Algos

Weighting Algos read `target.temp['selected']` and write to `target.temp['weights']` — a dict of `{node_id: float}`. All weights must sum to `1.0`.

---

### `WeightEqually`

Distributes weight equally across all selected children.

```python
class WeightEqually(BaseAlgo):
    def __call__(self, target) -> bool:
        selected = target.temp['selected']
        w = 1.0 / len(selected)
        target.temp['weights'] = {id: w for id in selected}
        return True
```

**Parameters:** none  
**Halts on:** never (selection Algo has already guaranteed at least 1 selected)

---

### `WeightSpecified`

Assigns manually defined weights to children. Used by `weight` nodes with `method == "defined"`.

```python
class WeightSpecified(BaseAlgo):
    def __init__(self, custom_weights: dict[str, float]): ...
    # custom_weights: {node_id: weight} — validated by compiler to sum to 1.0
```

**Behaviour:**
1. Read `custom_weights` (keyed by node id, validated at compile time to sum to 1.0)
2. Write to `target.temp['weights']`
3. Return `True`

---

### `WeightInvVol`

Weights children inversely proportional to their volatility over a lookback window.

```python
class WeightInvVol(BaseAlgo):
    def __init__(self, lookback: int): ...
    # lookback: integer trading days, from method_params.lookback
```

**Behaviour:**
1. For each selected child, compute `std_dev_return` over `lookback` days on its NAV/price series
2. `raw_weight[i] = 1 / vol[i]`
3. Normalise: `weight[i] = raw_weight[i] / Σ raw_weight`
4. Write to `target.temp['weights']`
5. If any child has zero or NaN vol (insufficient history): exclude it; redistribute weight to remaining
6. If all children have zero/NaN vol: return `False` (→ XCASHX)

**Parameters:**

| Param | Type | Source |
|---|---|---|
| `lookback` | int | `weight.method_params.lookback` converted to trading days |

---

## AlgoStack Composition

The engine builds the AlgoStack for each node at init time based on node type and parameters:

| Node type | AlgoStack |
|---|---|
| `weight / equal` | `[SelectAll(), WeightEqually()]` |
| `weight / defined` | `[SelectAll(), WeightSpecified(custom_weights)]` |
| `weight / inverse_volatility` | `[SelectAll(), WeightInvVol(lookback)]` |
| `filter / top` | `[SelectTopN(n, metric, lookback), WeightEqually()]` |
| `filter / bottom` | `[SelectBottomN(n, metric, lookback), WeightEqually()]` |
| `if_else` | `[SelectIfCondition(conditions, logic_mode), WeightEqually()]` |
| `asset` | `[]` (leaf — no AlgoStack) |

`XCASHX` is a virtual leaf with weight `1.0` and return `0.0` (no price series required).

---

## Testing Requirements

Every Algo must have unit tests covering:

| Test case | What to assert |
|---|---|
| Normal path | Returns `True`; `target.temp['weights']` sums to `1.0` |
| Empty selection | Returns `False`; engine sets node to 100% `XCASHX` |
| Single child | `WeightEqually` assigns `1.0`; `WeightInvVol` handles single-asset case |
| `SelectIfCondition` duration | Condition true for `condition.duration - 1` days → still routes to `false_branch` |
