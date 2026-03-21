from __future__ import annotations

from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.node import StrategyNode


class WeightEqually(BaseAlgo):
    def __call__(self, target: StrategyNode) -> bool:
        selected = target.temp["selected"]
        w = 1.0 / len(selected)
        target.temp["weights"] = {node_id: w for node_id in selected}
        return True
