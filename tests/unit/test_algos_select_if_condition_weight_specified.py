"""Tests for SelectIfCondition and WeightSpecified (A4)."""
from __future__ import annotations

import numpy as np
import pytest

from moa_allocations.engine.algos import SelectIfCondition, WeightSpecified
from moa_allocations.engine.node import IfElseNode, StrategyNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_series(*values: float) -> np.ndarray:
    return np.array(values, dtype=float)


class _Branch:
    """Minimal branch node stub."""
    def __init__(self, node_id: str) -> None:
        self.id = node_id


def _if_else_node(
    child_series: dict[str, np.ndarray],
    t_idx: int,
    true_id: str = "true_branch",
    false_id: str = "false_branch",
) -> IfElseNode:
    node = IfElseNode(
        id="parent",
        logic_mode="all",
        conditions=[],
        true_branch=_Branch(true_id),
        false_branch=_Branch(false_id),
    )
    node.perm = {"child_series": child_series}
    node.temp = {"t_idx": t_idx}
    return node


def _cond(
    lhs_asset: str,
    comparator: str,
    rhs,
    duration: int = 1,
    lhs_func: str = "current_price",
    lhs_lookback: int = 1,
) -> dict:
    lhs = {"asset": lhs_asset, "function": lhs_func, "lookback": lhs_lookback}
    if isinstance(rhs, dict):
        rhs_val = rhs
    else:
        rhs_val = float(rhs)
    return {"lhs": lhs, "comparator": comparator, "rhs": rhs_val, "duration": duration}


# ---------------------------------------------------------------------------
# 3.1  Single condition, duration=1
# ---------------------------------------------------------------------------

class TestSelectIfConditionDuration1:
    def test_condition_met_routes_to_true_branch(self):
        node = _if_else_node({"A": _make_series(105.0)}, t_idx=0)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 100.0, duration=1)],
            logic_mode="all",
        )
        result = algo(node)
        assert result is True
        assert node.temp["selected"] == ["true_branch"]

    def test_condition_not_met_routes_to_false_branch(self):
        node = _if_else_node({"A": _make_series(95.0)}, t_idx=0)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 100.0, duration=1)],
            logic_mode="all",
        )
        result = algo(node)
        assert result is True
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.2  Duration=3 window semantics
# ---------------------------------------------------------------------------

class TestSelectIfConditionDuration3:
    def test_all_3_days_pass_routes_to_true_branch(self):
        # current_price > 50 must hold at t-2, t-1, t
        node = _if_else_node({"A": _make_series(60.0, 70.0, 80.0)}, t_idx=2)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 50.0, duration=3)],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_one_day_fails_routes_to_false_branch(self):
        # t-2=60, t-1=40 (fails), t=80
        node = _if_else_node({"A": _make_series(60.0, 40.0, 80.0)}, t_idx=2)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 50.0, duration=3)],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.3  Duration window clamping when history is short
# ---------------------------------------------------------------------------

class TestDurationWindowClamping:
    def test_duration_exceeds_history_evaluates_available_days(self):
        # Only 2 days available (t_idx=1), duration=5 → evaluate [0, 1]
        node = _if_else_node({"A": _make_series(60.0, 70.0)}, t_idx=1)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 50.0, duration=5)],
            logic_mode="all",
        )
        algo(node)
        # Both available days pass → true_branch
        assert node.temp["selected"] == ["true_branch"]

    def test_duration_exceeds_history_one_day_fails(self):
        # Only 2 days: t=0→40 (fails), t=1→70
        node = _if_else_node({"A": _make_series(40.0, 70.0)}, t_idx=1)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 50.0, duration=5)],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.4  NaN on lhs metric → false_branch
# ---------------------------------------------------------------------------

class TestNaNHandling:
    def test_nan_lhs_routes_to_false_branch(self):
        # cumulative_return with lookback=2 needs 2 prices; only 1 → NaN
        node = _if_else_node(
            {"A": _make_series(100.0)},
            t_idx=0,
        )
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 0.0, duration=1,
                              lhs_func="cumulative_return", lhs_lookback=2)],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["false_branch"]

    # 3.5  NaN on rhs metric dict → false_branch
    def test_nan_rhs_metric_routes_to_false_branch(self):
        rhs_dict = {"asset": "B", "function": "cumulative_return", "lookback": 2}
        node = _if_else_node(
            {
                "A": _make_series(110.0, 120.0),
                "B": _make_series(100.0),       # too short → NaN
            },
            t_idx=1,
        )
        algo = SelectIfCondition(
            conditions=[{"lhs": {"asset": "A", "function": "current_price", "lookback": 1},
                         "comparator": "greater_than",
                         "rhs": rhs_dict,
                         "duration": 1}],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.6  Logic mode "all"
# ---------------------------------------------------------------------------

class TestLogicModeAll:
    def test_all_conditions_pass_routes_to_true_branch(self):
        node = _if_else_node({"A": _make_series(110.0), "B": _make_series(200.0)}, t_idx=0)
        algo = SelectIfCondition(
            conditions=[
                _cond("A", "greater_than", 100.0),
                _cond("B", "greater_than", 150.0),
            ],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_one_condition_fails_routes_to_false_branch(self):
        node = _if_else_node({"A": _make_series(110.0), "B": _make_series(100.0)}, t_idx=0)
        algo = SelectIfCondition(
            conditions=[
                _cond("A", "greater_than", 100.0),
                _cond("B", "greater_than", 150.0),  # fails: 100 < 150
            ],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.7  Logic mode "any"
# ---------------------------------------------------------------------------

class TestLogicModeAny:
    def test_one_condition_passes_routes_to_true_branch(self):
        node = _if_else_node({"A": _make_series(90.0), "B": _make_series(200.0)}, t_idx=0)
        algo = SelectIfCondition(
            conditions=[
                _cond("A", "greater_than", 100.0),  # fails
                _cond("B", "greater_than", 150.0),  # passes
            ],
            logic_mode="any",
        )
        algo(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_all_conditions_fail_routes_to_false_branch(self):
        node = _if_else_node({"A": _make_series(80.0), "B": _make_series(100.0)}, t_idx=0)
        algo = SelectIfCondition(
            conditions=[
                _cond("A", "greater_than", 100.0),
                _cond("B", "greater_than", 150.0),
            ],
            logic_mode="any",
        )
        algo(node)
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.8  Comparators
# ---------------------------------------------------------------------------

class TestComparators:
    def test_greater_than_true(self):
        node = _if_else_node({"A": _make_series(10.0)}, t_idx=0)
        SelectIfCondition([_cond("A", "greater_than", 5.0)], logic_mode="all")(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_greater_than_false(self):
        node = _if_else_node({"A": _make_series(3.0)}, t_idx=0)
        SelectIfCondition([_cond("A", "greater_than", 5.0)], logic_mode="all")(node)
        assert node.temp["selected"] == ["false_branch"]

    def test_less_than_true(self):
        node = _if_else_node({"A": _make_series(3.0)}, t_idx=0)
        SelectIfCondition([_cond("A", "less_than", 5.0)], logic_mode="all")(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_less_than_false(self):
        node = _if_else_node({"A": _make_series(10.0)}, t_idx=0)
        SelectIfCondition([_cond("A", "less_than", 5.0)], logic_mode="all")(node)
        assert node.temp["selected"] == ["false_branch"]

    def test_greater_than_equal_values_is_false(self):
        node = _if_else_node({"A": _make_series(5.0)}, t_idx=0)
        SelectIfCondition([_cond("A", "greater_than", 5.0)], logic_mode="all")(node)
        assert node.temp["selected"] == ["false_branch"]

    def test_less_than_equal_values_is_false(self):
        node = _if_else_node({"A": _make_series(5.0)}, t_idx=0)
        SelectIfCondition([_cond("A", "less_than", 5.0)], logic_mode="all")(node)
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.9  rhs as metric dict — verify series lookup
# ---------------------------------------------------------------------------

class TestRhsMetricDict:
    def test_rhs_metric_dict_lhs_greater_than_rhs(self):
        # A=120 > B=100 at t=0
        rhs_dict = {"asset": "B", "function": "current_price", "lookback": 1}
        node = _if_else_node(
            {"A": _make_series(120.0), "B": _make_series(100.0)},
            t_idx=0,
        )
        algo = SelectIfCondition(
            conditions=[{"lhs": {"asset": "A", "function": "current_price", "lookback": 1},
                         "comparator": "greater_than",
                         "rhs": rhs_dict,
                         "duration": 1}],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_rhs_metric_dict_lhs_less_than_rhs(self):
        # A=80 < B=100
        rhs_dict = {"asset": "B", "function": "current_price", "lookback": 1}
        node = _if_else_node(
            {"A": _make_series(80.0), "B": _make_series(100.0)},
            t_idx=0,
        )
        algo = SelectIfCondition(
            conditions=[{"lhs": {"asset": "A", "function": "current_price", "lookback": 1},
                         "comparator": "greater_than",
                         "rhs": rhs_dict,
                         "duration": 1}],
            logic_mode="all",
        )
        algo(node)
        assert node.temp["selected"] == ["false_branch"]


# ---------------------------------------------------------------------------
# 3.10  price_offset correctness
# ---------------------------------------------------------------------------

class TestPriceOffset:
    def test_current_price_reads_from_simulation_date_not_pre_sim(self):
        # Full array: 100 pre-sim entries (value=50) + sim entries starting at index 100
        # price_offset=100, t_idx=5 → correct read is price_arr[105]=110
        # Without fix it would read price_arr[5]=50 and route to false_branch
        pre_sim = [50.0] * 100
        sim = [110.0] * 10
        price_arr = _make_series(*pre_sim, *sim)
        node = _if_else_node({"A": price_arr}, t_idx=5)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 100.0, duration=1)],
            logic_mode="all",
            price_offset=100,
        )
        algo(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_sma_price_window_ends_at_simulation_date(self):
        # price_offset=5, t_idx=10, lookback=5
        # Correct window: price_arr[11:16] → mean=200 (> 100 → true)
        # Wrong window:   price_arr[6:11]  → mean=50  (< 100 → false)
        pre_and_early = [50.0] * 11   # indices 0-10
        correct_window = [200.0] * 5  # indices 11-15 (price_offset+t_idx-4 .. price_offset+t_idx)
        price_arr = _make_series(*pre_and_early, *correct_window)
        node = _if_else_node({"A": price_arr}, t_idx=10)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 100.0, duration=1,
                              lhs_func="sma_price", lhs_lookback=5)],
            logic_mode="all",
            price_offset=5,
        )
        algo(node)
        assert node.temp["selected"] == ["true_branch"]

    def test_price_offset_zero_behaviour_unchanged(self):
        # price_offset=0: series[-1] at t_idx=0 is price_arr[0]=105
        node = _if_else_node({"A": _make_series(105.0)}, t_idx=0)
        algo = SelectIfCondition(
            conditions=[_cond("A", "greater_than", 100.0, duration=1)],
            logic_mode="all",
            price_offset=0,
        )
        algo(node)
        assert node.temp["selected"] == ["true_branch"]


# ---------------------------------------------------------------------------
# 4.1-4.3  WeightSpecified
# ---------------------------------------------------------------------------

class TestWeightSpecified:
    def _node(self) -> StrategyNode:
        node = StrategyNode(id="parent")
        node.temp = {}
        return node

    # 4.1  Two-child assignment
    def test_two_child_assignment(self):
        node = self._node()
        algo = WeightSpecified(custom_weights={"A": 0.7, "B": 0.3})
        result = algo(node)
        assert result is True
        assert node.temp["weights"] == {"A": pytest.approx(0.7), "B": pytest.approx(0.3)}

    # 4.2  Single-child assignment
    def test_single_child_full_weight(self):
        node = self._node()
        algo = WeightSpecified(custom_weights={"A": 1.0})
        result = algo(node)
        assert result is True
        assert node.temp["weights"] == {"A": pytest.approx(1.0)}

    # 4.3  Multi-child unequal weights
    def test_multi_child_unequal_weights(self):
        weights = {"A": 0.5, "B": 0.3, "C": 0.2}
        node = self._node()
        algo = WeightSpecified(custom_weights=weights)
        result = algo(node)
        assert result is True
        assert node.temp["weights"] == {
            "A": pytest.approx(0.5),
            "B": pytest.approx(0.3),
            "C": pytest.approx(0.2),
        }
        assert sum(node.temp["weights"].values()) == pytest.approx(1.0)

    def test_always_returns_true(self):
        node = self._node()
        assert WeightSpecified({"X": 1.0})(node) is True
