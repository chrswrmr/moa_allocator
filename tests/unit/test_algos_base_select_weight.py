"""Tests for BaseAlgo, SelectAll, and WeightEqually (A2)."""
import pytest

from moa_allocations.engine.algos import BaseAlgo, SelectAll, WeightEqually
from moa_allocations.engine.node import StrategyNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeChild:
    """Minimal child stand-in with just an id."""
    def __init__(self, node_id: str) -> None:
        self.id = node_id


def _node(child_ids: list[str]) -> StrategyNode:
    node = StrategyNode(id="parent")
    node.children = [_FakeChild(cid) for cid in child_ids]
    node.temp = {}
    return node


# ---------------------------------------------------------------------------
# 4.1  BaseAlgo — abstract __call__ enforcement
# ---------------------------------------------------------------------------

class TestBaseAlgo:
    def test_subclass_without_call_raises_on_instantiation(self):
        class Incomplete(BaseAlgo):
            pass  # no __call__

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_instantiates(self):
        class Concrete(BaseAlgo):
            def __call__(self, target):
                return True

        assert Concrete() is not None

    def test_keyword_params_stored_as_attributes(self):
        class Concrete(BaseAlgo):
            def __call__(self, target):
                return True

        algo = Concrete(lookback=20, threshold=0.5)
        assert algo.lookback == 20
        assert algo.threshold == 0.5


# ---------------------------------------------------------------------------
# 4.2  SelectAll — multi-child
# ---------------------------------------------------------------------------

class TestSelectAll:
    def test_multi_child_populates_selected_and_returns_true(self):
        node = _node(["a", "b", "c"])
        result = SelectAll()(node)

        assert result is True
        assert node.temp["selected"] == ["a", "b", "c"]

    # 4.3  SelectAll — single child
    def test_single_child_returns_list_with_one_id(self):
        node = _node(["only"])
        result = SelectAll()(node)

        assert result is True
        assert node.temp["selected"] == ["only"]

    def test_zero_config_instantiation(self):
        assert SelectAll() is not None


# ---------------------------------------------------------------------------
# 4.4  WeightEqually — three children
# ---------------------------------------------------------------------------

class TestWeightEqually:
    def test_three_children_equal_weights_sum_to_one(self):
        node = _node([])
        node.temp["selected"] = ["a", "b", "c"]
        result = WeightEqually()(node)

        assert result is True
        weights = node.temp["weights"]
        assert weights == {"a": pytest.approx(1/3), "b": pytest.approx(1/3), "c": pytest.approx(1/3)}
        assert sum(weights.values()) == pytest.approx(1.0)

    # 4.5  WeightEqually — single child
    def test_single_child_gets_full_weight(self):
        node = _node([])
        node.temp["selected"] = ["only"]
        result = WeightEqually()(node)

        assert result is True
        assert node.temp["weights"] == {"only": pytest.approx(1.0)}

    def test_two_children_half_weights(self):
        node = _node([])
        node.temp["selected"] = ["x", "y"]
        WeightEqually()(node)

        assert node.temp["weights"] == {"x": pytest.approx(0.5), "y": pytest.approx(0.5)}

    def test_zero_config_instantiation(self):
        assert WeightEqually() is not None
