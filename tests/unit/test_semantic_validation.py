"""Tests for compile_strategy() step 3: semantic validation."""
import json
import pytest

from moa_allocations.compiler import compile_strategy
from moa_allocations.exceptions import DSLValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path, data):
    p = tmp_path / "strategy.moastrat.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def _compile(tmp_path, doc):
    """Run compile_strategy; return the raised exception (DSLValidationError or NotImplementedError)."""
    with pytest.raises((DSLValidationError, NotImplementedError)) as exc_info:
        compile_strategy(_write(tmp_path, doc))
    return exc_info.value


def _assert_passes(tmp_path, doc):
    """Assert the doc passes semantic validation (hits the NotImplementedError stub, not DSLValidationError)."""
    exc = _compile(tmp_path, doc)
    assert isinstance(exc, NotImplementedError), f"Expected NotImplementedError but got DSLValidationError: {exc}"


def _assert_fails(tmp_path, doc, *, node_id=None, fragment=None):
    exc = _compile(tmp_path, doc)
    assert isinstance(exc, DSLValidationError), f"Expected DSLValidationError but got {type(exc).__name__}: {exc}"
    if node_id is not None:
        assert exc.node_id == node_id, f"Expected node_id={node_id!r}, got {exc.node_id!r}"
    if fragment is not None:
        assert fragment in exc.message, f"Expected {fragment!r} in message: {exc.message!r}"
    return exc


# ---------------------------------------------------------------------------
# Base valid document
# ---------------------------------------------------------------------------

_SETTINGS_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"

VALID_DOC = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "version-dsl": "1.0.0",
    "settings": {
        "id": _SETTINGS_ID,
        "name": "Test Strategy",
        "starting_cash": 100000,
        "start_date": "2020-01-01",
        "end_date": "2021-01-01",
        "rebalance_frequency": "daily",
    },
    "root_node": {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "type": "asset",
        "ticker": "SPY",
    },
}


def _doc(**overrides):
    import copy
    d = copy.deepcopy(VALID_DOC)
    for k, v in overrides.items():
        d[k] = v
    return d


def _settings(**overrides):
    s = {**VALID_DOC["settings"], **overrides}
    return _doc(settings=s)


# ---------------------------------------------------------------------------
# 4.1 UUID uniqueness
# ---------------------------------------------------------------------------

class TestUUIDUniqueness:
    def test_all_unique_passes(self, tmp_path):
        _assert_passes(tmp_path, VALID_DOC)

    def test_root_node_id_duplicates_settings_id(self, tmp_path):
        doc = _doc(root_node={
            "id": _SETTINGS_ID,  # same as settings id
            "type": "asset",
            "ticker": "SPY",
        })
        _assert_fails(tmp_path, doc, node_id=_SETTINGS_ID, fragment="duplicate")

    def test_duplicate_across_nested_children(self, tmp_path):
        child_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        doc = _doc(root_node={
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "weight",
            "method": "equal",
            "children": [
                {"id": child_id, "type": "asset", "ticker": "SPY"},
                {"id": child_id, "type": "asset", "ticker": "AGG"},  # duplicate
            ],
        })
        _assert_fails(tmp_path, doc, node_id=child_id, fragment="duplicate")

    def test_duplicate_in_if_else_branches(self, tmp_path):
        shared_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        doc = _doc(root_node={
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "if_else",
            "logic_mode": "all",
            "conditions": [{
                "lhs": {"asset": "SPY", "function": "current_price"},
                "comparator": "greater_than",
                "rhs": 100,
            }],
            "true_branch": {"id": shared_id, "type": "asset", "ticker": "SPY"},
            "false_branch": {"id": shared_id, "type": "asset", "ticker": "AGG"},
        })
        _assert_fails(tmp_path, doc, node_id=shared_id, fragment="duplicate")


# ---------------------------------------------------------------------------
# 4.2 Defined-weight completeness
# ---------------------------------------------------------------------------

_CHILD_A = "aaaaaaaa-0000-0000-0000-000000000000"
_CHILD_B = "bbbbbbbb-0000-0000-0000-000000000000"

def _defined_weight_doc(custom_weights: dict) -> dict:
    return _doc(root_node={
        "id": "11111111-1111-1111-1111-111111111111",
        "type": "weight",
        "method": "defined",
        "method_params": {"custom_weights": custom_weights},
        "children": [
            {"id": _CHILD_A, "type": "asset", "ticker": "SPY"},
            {"id": _CHILD_B, "type": "asset", "ticker": "AGG"},
        ],
    })


class TestDefinedWeightCompleteness:
    def test_exact_match_passes(self, tmp_path):
        _assert_passes(tmp_path, _defined_weight_doc({_CHILD_A: 0.6, _CHILD_B: 0.4}))

    def test_missing_key_fails(self, tmp_path):
        _assert_fails(tmp_path, _defined_weight_doc({_CHILD_A: 1.0}), fragment="missing")

    def test_extra_key_fails(self, tmp_path):
        extra = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        _assert_fails(
            tmp_path,
            _defined_weight_doc({_CHILD_A: 0.5, _CHILD_B: 0.3, extra: 0.2}),
            fragment="extra",
        )

    def test_missing_and_extra_both_reported(self, tmp_path):
        extra = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        exc = _assert_fails(
            tmp_path,
            _defined_weight_doc({_CHILD_A: 0.6, extra: 0.4}),
        )
        assert "missing" in exc.message
        assert "extra" in exc.message


# ---------------------------------------------------------------------------
# 4.3 Defined-weight sum
# ---------------------------------------------------------------------------

class TestDefinedWeightSum:
    def test_sum_exactly_1_passes(self, tmp_path):
        _assert_passes(tmp_path, _defined_weight_doc({_CHILD_A: 0.5, _CHILD_B: 0.5}))

    def test_sum_within_tolerance_lower_passes(self, tmp_path):
        _assert_passes(tmp_path, _defined_weight_doc({_CHILD_A: 0.5005, _CHILD_B: 0.499}))

    def test_sum_within_tolerance_upper_passes(self, tmp_path):
        _assert_passes(tmp_path, _defined_weight_doc({_CHILD_A: 0.5005, _CHILD_B: 0.5}))

    def test_sum_too_low_fails(self, tmp_path):
        _assert_fails(tmp_path, _defined_weight_doc({_CHILD_A: 0.4, _CHILD_B: 0.4}), fragment="sum")

    def test_sum_too_high_fails(self, tmp_path):
        _assert_fails(tmp_path, _defined_weight_doc({_CHILD_A: 0.7, _CHILD_B: 0.4}), fragment="sum")


# ---------------------------------------------------------------------------
# 4.4 Filter select count bound
# ---------------------------------------------------------------------------

def _filter_doc(count: int, n_children: int) -> dict:
    children = [
        {"id": f"child{i:08x}-0000-0000-0000-000000000000", "type": "asset", "ticker": f"T{i}"}
        for i in range(n_children)
    ]
    return _doc(root_node={
        "id": "11111111-1111-1111-1111-111111111111",
        "type": "filter",
        "sort_by": {"function": "current_price"},
        "select": {"mode": "top", "count": count},
        "children": children,
    })


class TestFilterCountBound:
    def test_count_equals_children_passes(self, tmp_path):
        _assert_passes(tmp_path, _filter_doc(count=3, n_children=3))

    def test_count_less_than_children_passes(self, tmp_path):
        _assert_passes(tmp_path, _filter_doc(count=2, n_children=3))

    def test_count_exceeds_children_fails(self, tmp_path):
        exc = _assert_fails(tmp_path, _filter_doc(count=5, n_children=3), fragment="select.count")
        assert "5" in exc.message
        assert "3" in exc.message


# ---------------------------------------------------------------------------
# 4.5 Lookback required
# ---------------------------------------------------------------------------

def _if_else_doc(lhs_func: str, lhs_extra: dict | None = None) -> dict:
    lhs = {"asset": "SPY", "function": lhs_func}
    if lhs_extra:
        lhs.update(lhs_extra)
    return _doc(root_node={
        "id": "11111111-1111-1111-1111-111111111111",
        "type": "if_else",
        "logic_mode": "all",
        "conditions": [{
            "lhs": lhs,
            "comparator": "greater_than",
            "rhs": 100,
        }],
        "true_branch": {"id": "22222222-2222-2222-2222-222222222222", "type": "asset", "ticker": "SPY"},
        "false_branch": {"id": "33333333-3333-3333-3333-333333333333", "type": "asset", "ticker": "AGG"},
    })


def _filter_sort_doc(func: str, sort_extra: dict | None = None) -> dict:
    sort_by = {"function": func}
    if sort_extra:
        sort_by.update(sort_extra)
    return _doc(root_node={
        "id": "11111111-1111-1111-1111-111111111111",
        "type": "filter",
        "sort_by": sort_by,
        "select": {"mode": "top", "count": 1},
        "children": [
            {"id": "aaaaaaaa-0000-0000-0000-000000000000", "type": "asset", "ticker": "SPY"},
            {"id": "bbbbbbbb-0000-0000-0000-000000000000", "type": "asset", "ticker": "AGG"},
        ],
    })


LOOKBACK_FUNCTIONS = [
    "cumulative_return", "ema_price", "sma_price", "sma_return",
    "max_drawdown", "rsi", "std_dev_price", "std_dev_return",
]


class TestLookbackRequired:
    def test_current_price_without_lookback_passes(self, tmp_path):
        _assert_passes(tmp_path, _if_else_doc("current_price"))

    @pytest.mark.parametrize("func", LOOKBACK_FUNCTIONS)
    def test_non_current_price_with_lookback_passes(self, tmp_path, func):
        _assert_passes(tmp_path, _if_else_doc(func, {"lookback": "14d"}))

    @pytest.mark.parametrize("func", LOOKBACK_FUNCTIONS)
    def test_non_current_price_missing_lookback_fails(self, tmp_path, func):
        _assert_fails(tmp_path, _if_else_doc(func), fragment="lookback")

    @pytest.mark.parametrize("func", LOOKBACK_FUNCTIONS)
    def test_sort_by_missing_lookback_fails(self, tmp_path, func):
        _assert_fails(tmp_path, _filter_sort_doc(func), fragment="lookback")

    def test_sort_by_current_price_passes(self, tmp_path):
        _assert_passes(tmp_path, _filter_sort_doc("current_price"))


# ---------------------------------------------------------------------------
# 4.6 Date ordering
# ---------------------------------------------------------------------------

class TestDateOrdering:
    def test_start_before_end_passes(self, tmp_path):
        _assert_passes(tmp_path, _settings(start_date="2020-01-01", end_date="2021-01-01"))

    def test_start_equals_end_fails(self, tmp_path):
        _assert_fails(
            tmp_path,
            _settings(start_date="2020-06-01", end_date="2020-06-01"),
            node_id="root",
            fragment="start_date",
        )

    def test_start_after_end_fails(self, tmp_path):
        _assert_fails(
            tmp_path,
            _settings(start_date="2021-01-01", end_date="2020-01-01"),
            node_id="root",
            fragment="start_date",
        )


# ---------------------------------------------------------------------------
# 4.7 Rebalance threshold range
# ---------------------------------------------------------------------------

class TestRebalanceThreshold:
    def test_absent_passes(self, tmp_path):
        _assert_passes(tmp_path, VALID_DOC)

    def test_valid_value_passes(self, tmp_path):
        _assert_passes(tmp_path, _settings(rebalance_threshold=0.05))

    def test_zero_fails(self, tmp_path):
        _assert_fails(
            tmp_path,
            _settings(rebalance_threshold=0.0),
            node_id="root",
            fragment="rebalance_threshold",
        )

    def test_one_fails(self, tmp_path):
        _assert_fails(
            tmp_path,
            _settings(rebalance_threshold=1.0),
            node_id="root",
            fragment="rebalance_threshold",
        )

    def test_negative_fails(self, tmp_path):
        _assert_fails(
            tmp_path,
            _settings(rebalance_threshold=-0.1),
            node_id="root",
            fragment="rebalance_threshold",
        )

    def test_greater_than_one_fails(self, tmp_path):
        _assert_fails(
            tmp_path,
            _settings(rebalance_threshold=1.5),
            node_id="root",
            fragment="rebalance_threshold",
        )
