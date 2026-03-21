from __future__ import annotations

import math

from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.algos.metrics import compute_metric
from moa_allocations.engine.node import StrategyNode


class WeightEqually(BaseAlgo):
    def __call__(self, target: StrategyNode) -> bool:
        selected = target.temp["selected"]
        w = 1.0 / len(selected)
        target.temp["weights"] = {node_id: w for node_id in selected}
        return True


class WeightInvVol(BaseAlgo):
    """Weight selected children inversely proportional to return volatility."""

    def __init__(self, lookback: int) -> None:
        self.lookback = lookback

    def __call__(self, target: StrategyNode) -> bool:
        t_idx = target.temp["t_idx"]
        selected = target.temp["selected"]

        raw: dict[str, float] = {}
        for node_id in selected:
            series = target.perm["child_series"][node_id][: t_idx + 1]
            vol = compute_metric(series, "std_dev_return", self.lookback)
            if math.isnan(vol) or vol == 0.0:
                continue
            raw[node_id] = 1.0 / vol

        if not raw:
            return False

        total = sum(raw.values())
        target.temp["weights"] = {nid: w / total for nid, w in raw.items()}
        return True
