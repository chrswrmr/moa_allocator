from __future__ import annotations

import logging
import math

from moa_allocations.engine.algos.base import BaseAlgo
from moa_allocations.engine.algos.metrics import compute_metric
from moa_allocations.engine.node import StrategyNode

logger = logging.getLogger(__name__)


def _node_label(node) -> str:
    return node.name or node.id


_NODE_TYPE_MAP = {"IfElseNode": "if_else", "WeightNode": "weight", "FilterNode": "filter"}


def _node_type(node) -> str:
    return _NODE_TYPE_MAP.get(type(node).__name__, type(node).__name__)


class WeightEqually(BaseAlgo):
    def __call__(self, target: StrategyNode) -> bool:
        selected = target.temp["selected"]
        w = 1.0 / len(selected)
        target.temp["weights"] = {node_id: w for node_id in selected}
        node_lbl = _node_label(target)
        node_type = _node_type(target)
        logger.debug(
            "WEIGHT  node=%s  type=%s  method=equal  weights=%s",
            node_lbl, node_type, {nid: f"{wv:.6f}" for nid, wv in target.temp["weights"].items()},
            extra={"keyword": "WEIGHT", "node": node_lbl, "node_type": node_type,
                   "method": "equal", "weights": target.temp["weights"]},
        )
        return True


class WeightSpecified(BaseAlgo):
    """Assign pre-validated custom weights directly to target.temp['weights']."""

    def __init__(self, custom_weights: dict[str, float]) -> None:
        self.custom_weights = custom_weights

    def __call__(self, target: StrategyNode) -> bool:
        target.temp["weights"] = dict(self.custom_weights)
        node_lbl = _node_label(target)
        node_type = _node_type(target)
        logger.debug(
            "WEIGHT  node=%s  type=%s  method=defined  weights=%s",
            node_lbl, node_type, {nid: f"{wv:.6f}" for nid, wv in target.temp["weights"].items()},
            extra={"keyword": "WEIGHT", "node": node_lbl, "node_type": node_type,
                   "method": "defined", "weights": target.temp["weights"]},
        )
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
        node_lbl = _node_label(target)
        node_type = _node_type(target)
        logger.debug(
            "WEIGHT  node=%s  type=%s  method=inverse_volatility  weights=%s",
            node_lbl, node_type, {nid: f"{wv:.6f}" for nid, wv in target.temp["weights"].items()},
            extra={"keyword": "WEIGHT", "node": node_lbl, "node_type": node_type,
                   "method": "inverse_volatility", "weights": target.temp["weights"]},
        )
        return True
