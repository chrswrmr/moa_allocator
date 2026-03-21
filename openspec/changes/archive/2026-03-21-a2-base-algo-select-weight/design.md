## Context

The node class hierarchy (C1) and `compute_metric` (A1) are implemented. The engine needs callable Algo units to execute during the downward pass. A2 introduces the `BaseAlgo` contract and the two Algos required for `weight/equal` nodes: `SelectAll` and `WeightEqually`. These are the simplest Algos and set the pattern for all future ones (A3/A4).

Currently `engine/algos/` contains only `metrics.py`. No Algo classes exist yet.

## Goals / Non-Goals

**Goals:**
- Define `BaseAlgo` as the abstract base for all Algos, enforcing the `__call__(target) -> bool` signature
- Implement `SelectAll` and `WeightEqually` per the algos spec
- Establish the file layout (`base.py`, `selection.py`, `weighting.py`) that A3/A4 will extend
- Export all public names from `engine/algos/__init__.py`

**Non-Goals:**
- Metric-dependent Algos (`SelectTopN`, `SelectBottomN`, `SelectIfCondition`, `WeightInvVol`, `WeightSpecified`) — those are A3/A4
- `AlgoStack` composition logic — that belongs to the Runner (E1)
- Any changes to node classes or `compute_metric`

## Decisions

### D1: `BaseAlgo` uses ABC with abstract `__call__`

Use `abc.ABC` + `@abstractmethod` on `__call__` so that subclasses that forget to implement it fail at instantiation, not at runtime during a backtest.

**Alternative considered:** A plain base class with `__call__` raising `NotImplementedError`. Rejected because the error would only surface when the Algo is actually called, which could be deep into a multi-day simulation.

### D2: One file per concern — `base.py`, `selection.py`, `weighting.py`

Selection and weighting Algos have distinct interfaces (`temp['selected']` vs `temp['weights']`), so separating them clarifies which side of the contract a class implements. `base.py` holds only the abstract contract.

**Alternative considered:** A single `algos.py` file. Rejected because A3/A4 will add 4+ more Algo classes; a single file would grow unwieldy.

### D3: `SelectAll` reads `target.children` directly

`SelectAll` iterates `target.children` (a list set at compile time on `WeightNode` / `FilterNode`). For `IfElseNode`, the children are `true_branch` and `false_branch` — `SelectAll` is not used on `IfElseNode` (that's `SelectIfCondition`), so no special handling is needed.

### D4: `WeightEqually` trusts that `selected` is non-empty

Per the algos spec, the selection Algo guarantees at least one selected child before `WeightEqually` runs. `WeightEqually` does not guard against division by zero — if `selected` is empty, that indicates a bug in the selection Algo or stack composition. This keeps the weighting Algo simple and avoids masking upstream errors.

**Alternative considered:** Defensive check returning `False` on empty selection. Rejected because it would silently degrade to XCASHX when the real issue is a broken selection Algo.

### D5: No `__init__` params for `SelectAll` or `WeightEqually`

Neither Algo needs compile-time parameters. They accept only `target` at call time. This matches the spec and keeps them zero-config.

## Risks / Trade-offs

- **[Risk] `WeightEqually` crashes on empty `selected`** → Acceptable: this is a programming error in stack composition, not a runtime data condition. A `ZeroDivisionError` is a clear signal. The Runner (E1) will compose stacks correctly.
- **[Risk] Future Algos may need shared utilities (e.g. normalization)** → Deferred to A3/A4. If needed, a `_utils.py` can be added without changing the public API.
