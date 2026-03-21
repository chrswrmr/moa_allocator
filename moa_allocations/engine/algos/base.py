from __future__ import annotations

from abc import ABC, abstractmethod

from moa_allocations.engine.node import StrategyNode


class BaseAlgo(ABC):
    def __init__(self, **params) -> None:
        self.__dict__.update(params)

    @abstractmethod
    def __call__(self, target: StrategyNode) -> bool: ...
