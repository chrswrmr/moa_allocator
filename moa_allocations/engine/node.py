from __future__ import annotations


class BaseNode:
    def __init__(self, id: str, name: str | None = None) -> None:
        self.id = id
        self.name = name


class StrategyNode(BaseNode):
    def __init__(self, id: str, name: str | None = None) -> None:
        super().__init__(id, name)
        self.temp: dict = {}
        self.perm: dict = {}
        self.algo_stack: list = []


class IfElseNode(StrategyNode):
    def __init__(
        self,
        id: str,
        logic_mode: str,
        conditions: list,
        true_branch: StrategyNode | AssetNode,
        false_branch: StrategyNode | AssetNode,
        name: str | None = None,
    ) -> None:
        super().__init__(id, name)
        self.logic_mode = logic_mode
        self.conditions = conditions
        self.true_branch = true_branch
        self.false_branch = false_branch


class WeightNode(StrategyNode):
    def __init__(
        self,
        id: str,
        method: str,
        method_params: dict,
        children: list[StrategyNode | AssetNode],
        name: str | None = None,
    ) -> None:
        super().__init__(id, name)
        self.method = method
        self.method_params = method_params
        self.children = children


class FilterNode(StrategyNode):
    def __init__(
        self,
        id: str,
        sort_by: dict,
        select: dict,
        children: list[StrategyNode | AssetNode],
        name: str | None = None,
    ) -> None:
        super().__init__(id, name)
        self.sort_by = sort_by
        self.select = select
        self.children = children


class AssetNode(BaseNode):
    def __init__(self, id: str, ticker: str, name: str | None = None) -> None:
        super().__init__(id, name)
        self.ticker = ticker
