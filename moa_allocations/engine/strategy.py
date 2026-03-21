from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from moa_allocations.engine.node import AssetNode, StrategyNode


@dataclass
class Settings:
    id: str
    name: str
    starting_cash: float
    start_date: date
    end_date: date
    slippage: float
    fees: float
    rebalance_frequency: str  # "daily" | "weekly" | "monthly"
    rebalance_threshold: float | None


class RootNode:
    def __init__(
        self,
        settings: Settings,
        root: StrategyNode | AssetNode,
        dsl_version: str,
    ) -> None:
        self.settings = settings
        self.root = root
        self.dsl_version = dsl_version
