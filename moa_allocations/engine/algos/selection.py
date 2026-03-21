from __future__ import annotations

from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.node import StrategyNode


class SelectAll(BaseAlgo):
    def __call__(self, target: StrategyNode) -> bool:
        target.temp["selected"] = [child.id for child in target.children]
        return True
