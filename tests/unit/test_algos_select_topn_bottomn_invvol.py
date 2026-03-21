"""Tests for SelectTopN, SelectBottomN, and WeightInvVol (A3)."""
from __future__ import annotations

import numpy as np
import pytest

from moa_allocations.engine.algos import SelectBottomN, SelectTopN, WeightInvVol
from moa_allocations.engine.node import StrategyNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Child:
    """Minimal child with just an id."""
    def __init__(self, node_id: str) -> None:
        self.id = node_id


def _make_price_series(values: list[float]) -> np.ndarray:
    return np.array(values, dtype=float)


def _node_with_children(child_ids: list[str]) -> StrategyNode:
    node = StrategyNode(id="parent")
    node.children = [_Child(cid) for cid in child_ids]
    node.temp = {}
    node.perm = {}
    return node


def _set_child_series(node: StrategyNode, series_map: dict[str, list[float]], t_idx: int) -> None:
    """Populate perm['child_series'] and temp['t_idx']."""
    node.perm["child_series"] = {cid: _make_price_series(s) for cid, s in series_map.items()}
    node.temp["t_idx"] = t_idx


# ---------------------------------------------------------------------------
# SelectTopN
# ---------------------------------------------------------------------------

class TestSelectTopN:
    def test_normal_descending_ranking_top3(self):
        """5 children ranked by cumulative_return descending; top 3 selected."""
        # cumulative_return over 2 bars: (series[-1]/series[-2]) - 1
        # Values: [0.10, 0.05, 0.20, 0.15, 0.03]
        node = _node_with_children(["a", "b", "c", "d", "e"])
        _set_child_series(node, {
            "a": [100.0, 110.0],  # return 0.10
            "b": [100.0, 105.0],  # return 0.05
            "c": [100.0, 120.0],  # return 0.20
            "d": [100.0, 115.0],  # return 0.15
            "e": [100.0, 103.0],  # return 0.03
        }, t_idx=1)

        result = SelectTopN(n=3, metric="cumulative_return", lookback=2)(node)

        assert result is True
        assert node.temp["selected"] == ["c", "d", "a"]  # 0.20, 0.15, 0.10

    def test_n_exceeds_children_selects_all(self):
        """n > len(children) → all children selected."""
        node = _node_with_children(["x", "y", "z"])
        _set_child_series(node, {
            "x": [100.0, 110.0],
            "y": [100.0, 105.0],
            "z": [100.0, 108.0],
        }, t_idx=1)

        result = SelectTopN(n=10, metric="cumulative_return", lookback=2)(node)

        assert result is True
        assert set(node.temp["selected"]) == {"x", "y", "z"}

    def test_nan_exclusion_some_children(self):
        """2 of 5 children have insufficient history → ranked over remaining 3."""
        node = _node_with_children(["a", "b", "c", "d", "e"])
        _set_child_series(node, {
            "a": [100.0, 110.0],        # return 0.10  (valid)
            "b": [105.0],               # too short for lookback=2 → NaN
            "c": [100.0, 120.0],        # return 0.20  (valid)
            "d": [100.0, 115.0],        # return 0.15  (valid)
            "e": [103.0],               # too short → NaN
        }, t_idx=0)
        # t_idx=0 means slice is [:1], so single-element series → NaN for lookback=2

        # Redo with t_idx=1 and short series padded to length 1
        node2 = _node_with_children(["a", "b", "c", "d", "e"])
        node2.perm["child_series"] = {
            "a": np.array([100.0, 110.0]),
            "b": np.array([105.0]),          # only 1 element, lookback=2 needs 2
            "c": np.array([100.0, 120.0]),
            "d": np.array([100.0, 115.0]),
            "e": np.array([103.0]),
        }
        node2.temp["t_idx"] = 1  # slice [:2] → b and e have only 1 element

        result = SelectTopN(n=3, metric="cumulative_return", lookback=2)(node2)

        assert result is True
        # Only a, c, d have valid metrics; n=3 selects all three
        assert set(node2.temp["selected"]) == {"a", "c", "d"}
        assert len(node2.temp["selected"]) == 3

    def test_valid_children_fewer_than_n_after_nan_exclusion(self):
        """n=3 but only 1 valid child after NaN exclusion → 1 selected, returns True."""
        node = _node_with_children(["a", "b", "c", "d", "e"])
        node.perm["child_series"] = {
            "a": np.array([100.0]),          # NaN (too short)
            "b": np.array([100.0, 110.0]),   # valid: return 0.10
            "c": np.array([50.0]),           # NaN
            "d": np.array([75.0]),           # NaN
            "e": np.array([200.0]),          # NaN
        }
        node.temp["t_idx"] = 1

        result = SelectTopN(n=3, metric="cumulative_return", lookback=2)(node)

        assert result is True
        assert node.temp["selected"] == ["b"]

    def test_all_nan_returns_false(self):
        """All children have insufficient history → returns False."""
        node = _node_with_children(["a", "b"])
        node.perm["child_series"] = {
            "a": np.array([100.0]),   # too short for lookback=2
            "b": np.array([200.0]),
        }
        node.temp["t_idx"] = 0  # slice [:1] → 1 element, lookback=2 needs 2

        result = SelectTopN(n=2, metric="cumulative_return", lookback=2)(node)

        assert result is False

    def test_stable_sort_on_tied_metric_values(self):
        """Tied metric values preserve child order from target.children."""
        node = _node_with_children(["first", "second", "third"])
        # All same cumulative_return = 0.10
        node.perm["child_series"] = {
            "first":  np.array([100.0, 110.0]),
            "second": np.array([100.0, 110.0]),
            "third":  np.array([100.0, 110.0]),
        }
        node.temp["t_idx"] = 1

        result = SelectTopN(n=2, metric="cumulative_return", lookback=2)(node)

        assert result is True
        # Stable sort: first two in original order
        assert node.temp["selected"] == ["first", "second"]


# ---------------------------------------------------------------------------
# SelectBottomN
# ---------------------------------------------------------------------------

class TestSelectBottomN:
    def test_normal_ascending_ranking_bottom2(self):
        """4 children ranked ascending by std_dev_return; bottom 2 selected."""
        # Need enough data for std_dev_return with lookback=2 (needs lookback+1=3 prices)
        node = _node_with_children(["a", "b", "c", "d"])
        # Vols (approx): a=low, b=high, c=medium, d=very low
        # Use flat series for low vol, varying for high vol
        node.perm["child_series"] = {
            "a": np.array([100.0, 101.0, 102.0]),    # small returns
            "b": np.array([100.0, 120.0, 90.0]),      # large swings
            "c": np.array([100.0, 105.0, 103.0]),     # medium
            "d": np.array([100.0, 100.5, 101.0]),     # very small
        }
        node.temp["t_idx"] = 2

        result = SelectBottomN(n=2, metric="std_dev_return", lookback=2)(node)

        assert result is True
        # d has smallest vol, a second smallest → ["d", "a"]
        assert node.temp["selected"][0] == "d"
        assert node.temp["selected"][1] == "a"

    def test_stable_sort_on_tied_metric_values(self):
        """Tied ascending metric preserves child order."""
        node = _node_with_children(["alpha", "beta", "gamma"])
        node.perm["child_series"] = {
            "alpha": np.array([100.0, 110.0]),
            "beta":  np.array([100.0, 110.0]),
            "gamma": np.array([100.0, 110.0]),
        }
        node.temp["t_idx"] = 1

        result = SelectBottomN(n=2, metric="cumulative_return", lookback=2)(node)

        assert result is True
        assert node.temp["selected"] == ["alpha", "beta"]

    def test_all_nan_returns_false(self):
        """All NaN → returns False."""
        node = _node_with_children(["a"])
        node.perm["child_series"] = {"a": np.array([100.0])}
        node.temp["t_idx"] = 0

        result = SelectBottomN(n=1, metric="cumulative_return", lookback=2)(node)

        assert result is False


# ---------------------------------------------------------------------------
# WeightInvVol
# ---------------------------------------------------------------------------

class TestWeightInvVol:
    def test_normal_inverse_vol_weights_sum_to_one(self):
        """3 children with known vols → correct inverse-vol weights."""
        node = _node_with_children([])
        # std_dev_return needs lookback+1 prices → lookback=2 needs 3 prices
        # Craft series so vols are known:
        # a: returns [0.02, 0.02] → std=0.0 (actually identical so 0)
        # Let's use distinct series
        node.perm["child_series"] = {
            "a": np.array([100.0, 102.0, 104.0, 106.0]),   # returns ~0.02 each, low vol
            "b": np.array([100.0, 110.0, 90.0, 110.0]),    # high vol
            "c": np.array([100.0, 103.0, 106.0, 109.0]),   # ~0.03 each, low vol
        }
        node.temp = {"t_idx": 3, "selected": ["a", "b", "c"]}

        result = WeightInvVol(lookback=3)(node)

        assert result is True
        weights = node.temp["weights"]
        assert set(weights.keys()) == {"a", "b", "c"}
        assert sum(weights.values()) == pytest.approx(1.0)
        # b has highest vol → lowest weight
        assert weights["b"] < weights["a"]
        assert weights["b"] < weights["c"]

    def test_single_selected_child_gets_full_weight(self):
        """Single selected child → weight 1.0."""
        node = _node_with_children([])
        node.perm["child_series"] = {
            "only": np.array([100.0, 101.0, 102.5, 101.0]),
        }
        node.temp = {"t_idx": 3, "selected": ["only"]}

        result = WeightInvVol(lookback=3)(node)

        assert result is True
        assert node.temp["weights"] == {"only": pytest.approx(1.0)}

    def test_zero_vol_child_excluded_weight_redistributed(self):
        """Zero-vol child excluded; remaining children share full weight."""
        node = _node_with_children([])
        node.perm["child_series"] = {
            "flat": np.array([100.0, 100.0, 100.0, 100.0]),  # zero returns → std=0
            "a":    np.array([100.0, 102.0, 98.0, 103.0]),   # some vol
            "b":    np.array([100.0, 105.0, 95.0, 105.0]),   # more vol
        }
        node.temp = {"t_idx": 3, "selected": ["flat", "a", "b"]}

        result = WeightInvVol(lookback=3)(node)

        assert result is True
        weights = node.temp["weights"]
        assert "flat" not in weights  # excluded
        assert set(weights.keys()) == {"a", "b"}
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_nan_vol_child_excluded(self):
        """NaN-vol child (insufficient history) excluded; rest redistributed."""
        node = _node_with_children([])
        node.perm["child_series"] = {
            "short": np.array([100.0]),               # too short for lookback=3
            "a":     np.array([100.0, 102.0, 98.0, 103.0]),
        }
        node.temp = {"t_idx": 3, "selected": ["short", "a"]}

        result = WeightInvVol(lookback=3)(node)

        assert result is True
        weights = node.temp["weights"]
        assert "short" not in weights
        assert weights == {"a": pytest.approx(1.0)}

    def test_all_children_excluded_returns_false(self):
        """All zero/NaN vol → returns False."""
        node = _node_with_children([])
        node.perm["child_series"] = {
            "flat1": np.array([100.0, 100.0, 100.0, 100.0]),
            "flat2": np.array([200.0, 200.0, 200.0, 200.0]),
        }
        node.temp = {"t_idx": 3, "selected": ["flat1", "flat2"]}

        result = WeightInvVol(lookback=3)(node)

        assert result is False
