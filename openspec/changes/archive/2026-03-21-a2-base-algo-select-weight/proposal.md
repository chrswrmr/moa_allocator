## Why

The engine's simulation loop needs to execute selection and weighting logic on each node during the downward pass. The Algo contract (`BaseAlgo.__call__`) and the two simplest concrete Algos (`SelectAll`, `WeightEqually`) are the foundation every other Algo builds on — without them, no node can resolve its weights and the engine has nothing to run. C1 (node classes) and A1 (`compute_metric`) are complete, so A2 is unblocked and is the next prerequisite for the runner (E1).

## What Changes

- **New file `engine/algos/base.py`** — `BaseAlgo` abstract base class with `__call__(self, target: StrategyNode) -> bool` contract.
- **New file `engine/algos/selection.py`** — `SelectAll` Algo: writes all child node ids to `target.temp['selected']`, always returns `True`.
- **New file `engine/algos/weighting.py`** — `WeightEqually` Algo: reads `target.temp['selected']`, assigns `1/n` weight to each, writes to `target.temp['weights']`, always returns `True`.
- **Updated `engine/algos/__init__.py`** — re-exports `BaseAlgo`, `SelectAll`, `WeightEqually`.
- **New tests** covering normal path, single-child, and multi-child scenarios for both Algos.

## Capabilities

### New Capabilities
- `base-algo`: The `BaseAlgo` abstract class defining the Algo contract — `__call__(target) -> bool`, stateless design, hard rules (no global state, no parent/sibling access, no DataFrame ops).
- `select-all`: `SelectAll` selection Algo — selects all children of a node unconditionally.
- `weight-equally`: `WeightEqually` weighting Algo — distributes `1/n` weight across all selected children.

### Modified Capabilities
_(none — these are net-new files with no changes to existing specs)_

## Impact

- **Code:** Three new files under `moa_allocations/engine/algos/`, plus `__init__.py` update. No changes to existing modules.
- **Dependencies:** Imports `StrategyNode` from `engine.node` (read-only — no engine logic imported into algos, per architecture boundary).
- **Downstream:** Unblocks A3/A4 (metric-dependent Algos) and E1 (Runner), which will compose `AlgoStack = [SelectAll(), WeightEqually()]` for `weight/equal` nodes.
