"""Tests for compile_strategy() steps 1-2: JSON loading and top-level validation."""
import json
import pytest

from moa_allocations.compiler import compile_strategy
from moa_allocations.exceptions import DSLValidationError


# ---------------------------------------------------------------------------
# Minimal valid document fixture
# ---------------------------------------------------------------------------

VALID_DOC = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "version-dsl": "1.0.0",
    "settings": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
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


def _write_json(tmp_path, data):
    p = tmp_path / "strategy.moastrat.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# 6.1 Valid document compiles successfully (steps 1-5 pass)
# ---------------------------------------------------------------------------

def test_valid_doc_compiles_successfully(tmp_path):
    from moa_allocations.engine.strategy import RootNode
    path = _write_json(tmp_path, VALID_DOC)
    result = compile_strategy(path)
    assert isinstance(result, RootNode)


# ---------------------------------------------------------------------------
# 6.2 Non-existent file raises DSLValidationError
# ---------------------------------------------------------------------------

def test_missing_file_raises_dsl_error(tmp_path):
    with pytest.raises(DSLValidationError) as exc_info:
        compile_strategy(str(tmp_path / "does_not_exist.json"))
    assert exc_info.value.node_id == "root"
    assert exc_info.value.node_name == "settings"


# ---------------------------------------------------------------------------
# 6.3 Invalid JSON raises DSLValidationError
# ---------------------------------------------------------------------------

def test_invalid_json_raises_dsl_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json }", encoding="utf-8")
    with pytest.raises(DSLValidationError) as exc_info:
        compile_strategy(str(p))
    assert exc_info.value.node_id == "root"
    assert exc_info.value.node_name == "settings"


# ---------------------------------------------------------------------------
# 6.4 Missing version-dsl raises DSLValidationError before schema validation
# ---------------------------------------------------------------------------

def test_missing_version_dsl_raises_immediately(tmp_path):
    doc = {k: v for k, v in VALID_DOC.items() if k != "version-dsl"}
    path = _write_json(tmp_path, doc)
    with pytest.raises(DSLValidationError) as exc_info:
        compile_strategy(path)
    assert exc_info.value.node_id == "root"
    assert "version-dsl" in exc_info.value.message


# ---------------------------------------------------------------------------
# 6.5 Wrong version-dsl raises DSLValidationError before schema validation
# ---------------------------------------------------------------------------

def test_wrong_version_dsl_raises_immediately(tmp_path):
    doc = {**VALID_DOC, "version-dsl": "2.0.0"}
    path = _write_json(tmp_path, doc)
    with pytest.raises(DSLValidationError) as exc_info:
        compile_strategy(path)
    assert exc_info.value.node_id == "root"
    assert "2.0.0" in exc_info.value.message


# ---------------------------------------------------------------------------
# 6.6 Document missing a required top-level field raises DSLValidationError
# ---------------------------------------------------------------------------

def test_missing_settings_raises_dsl_error(tmp_path):
    doc = {k: v for k, v in VALID_DOC.items() if k != "settings"}
    path = _write_json(tmp_path, doc)
    with pytest.raises(DSLValidationError) as exc_info:
        compile_strategy(path)
    assert exc_info.value.node_id == "root"
    assert exc_info.value.node_name == "settings"


# ---------------------------------------------------------------------------
# 6.7 Document with invalid field type raises DSLValidationError
# ---------------------------------------------------------------------------

def test_invalid_field_type_raises_dsl_error(tmp_path):
    doc = {**VALID_DOC, "settings": {**VALID_DOC["settings"], "starting_cash": "not-a-number"}}
    path = _write_json(tmp_path, doc)
    with pytest.raises(DSLValidationError) as exc_info:
        compile_strategy(path)
    assert exc_info.value.node_id == "root"
    assert exc_info.value.node_name == "settings"


# ---------------------------------------------------------------------------
# 6.8 Netting leverage sign constraints enforced at schema level
# ---------------------------------------------------------------------------

def _netting_doc(long_leverage, short_leverage):
    """Document with a netting pair; root_node is a single SPY asset (schema-level test only)."""
    return {
        **VALID_DOC,
        "settings": {
            **VALID_DOC["settings"],
            "netting": {
                "pairs": [
                    {
                        "long_ticker": "QQQ",
                        "long_leverage": long_leverage,
                        "short_ticker": "PSQ",
                        "short_leverage": short_leverage,
                    }
                ],
                "cash_ticker": None,
            },
        },
    }


def test_netting_zero_long_leverage_rejected(tmp_path):
    """long_leverage: 0 violates exclusiveMinimum: 0 — schema rejects it."""
    path = _write_json(tmp_path, _netting_doc(long_leverage=0, short_leverage=-1))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


def test_netting_negative_long_leverage_rejected(tmp_path):
    """long_leverage: -1 violates exclusiveMinimum: 0 — schema rejects it."""
    path = _write_json(tmp_path, _netting_doc(long_leverage=-1, short_leverage=-1))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


def test_netting_zero_short_leverage_rejected(tmp_path):
    """short_leverage: 0 violates exclusiveMaximum: 0 — schema rejects it."""
    path = _write_json(tmp_path, _netting_doc(long_leverage=1, short_leverage=0))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


def test_netting_positive_short_leverage_rejected(tmp_path):
    """short_leverage: 1 violates exclusiveMaximum: 0 — schema rejects it."""
    path = _write_json(tmp_path, _netting_doc(long_leverage=1, short_leverage=1))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


# ---------------------------------------------------------------------------
# Node-level required field validation (tasks 2.1–2.5)
# ---------------------------------------------------------------------------

def _make_doc(root_node):
    """Wrap a root_node dict in a valid top-level document."""
    return {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "version-dsl": "1.0.0",
        "settings": {
            "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "name": "Test Strategy",
            "starting_cash": 100000,
            "start_date": "2020-01-01",
            "end_date": "2021-01-01",
            "rebalance_frequency": "daily",
        },
        "root_node": root_node,
    }


_ASSET_SPY = {"id": "dddddddd-0001-0000-0000-000000000001", "type": "asset", "ticker": "SPY"}
_ASSET_TLT = {"id": "dddddddd-0002-0000-0000-000000000002", "type": "asset", "ticker": "TLT"}

_VALID_IF_ELSE = {
    "id": "cccccccc-0001-0000-0000-000000000001",
    "type": "if_else",
    "logic_mode": "all",
    "conditions": [
        {
            "lhs": {"asset": "SPY", "function": "current_price"},
            "comparator": "greater_than",
            "rhs": 100,
        }
    ],
    "true_branch": _ASSET_SPY,
    "false_branch": _ASSET_TLT,
}

_VALID_WEIGHT = {
    "id": "cccccccc-0002-0000-0000-000000000001",
    "type": "weight",
    "method": "equal",
    "children": [_ASSET_SPY, _ASSET_TLT],
}

_VALID_FILTER = {
    "id": "cccccccc-0003-0000-0000-000000000001",
    "type": "filter",
    "sort_by": {"function": "current_price"},
    "select": {"mode": "top", "count": 1},
    "children": [_ASSET_SPY, _ASSET_TLT],
}


# --- 2.1 if_else missing required fields ---

@pytest.mark.parametrize("missing_field", ["logic_mode", "conditions", "true_branch", "false_branch"])
def test_if_else_missing_required_field(tmp_path, missing_field):
    node = {k: v for k, v in _VALID_IF_ELSE.items() if k != missing_field}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


# --- 2.2 weight missing required fields ---

@pytest.mark.parametrize("missing_field", ["method", "children"])
def test_weight_missing_required_field(tmp_path, missing_field):
    node = {k: v for k, v in _VALID_WEIGHT.items() if k != missing_field}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


# --- 2.3 filter missing required fields ---

@pytest.mark.parametrize("missing_field", ["sort_by", "select", "children"])
def test_filter_missing_required_field(tmp_path, missing_field):
    node = {k: v for k, v in _VALID_FILTER.items() if k != missing_field}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


# --- 2.4 asset missing ticker ---

def test_asset_missing_ticker(tmp_path):
    node = {"id": "dddddddd-0001-0000-0000-000000000001", "type": "asset"}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


# --- 2.5 filter select missing mode or count ---

@pytest.mark.parametrize("missing_field", ["mode", "count"])
def test_filter_select_missing_field(tmp_path, missing_field):
    select = {k: v for k, v in {"mode": "top", "count": 1}.items() if k != missing_field}
    node = {**_VALID_FILTER, "select": select}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


# ---------------------------------------------------------------------------
# Empty arrays / empty string rejected at schema level (minItems / minLength)
# ---------------------------------------------------------------------------

def test_if_else_empty_conditions_rejected(tmp_path):
    node = {**_VALID_IF_ELSE, "conditions": []}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


def test_weight_empty_children_rejected(tmp_path):
    node = {**_VALID_WEIGHT, "children": []}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


def test_filter_empty_children_rejected(tmp_path):
    node = {**_VALID_FILTER, "children": []}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


def test_asset_empty_ticker_rejected(tmp_path):
    node = {"id": "dddddddd-0001-0000-0000-000000000001", "type": "asset", "ticker": ""}
    path = _write_json(tmp_path, _make_doc(node))
    with pytest.raises(DSLValidationError):
        compile_strategy(path)


# ---------------------------------------------------------------------------
# Non-empty arrays / strings still pass schema validation
# ---------------------------------------------------------------------------

def test_if_else_with_conditions_passes(tmp_path):
    path = _write_json(tmp_path, _make_doc(_VALID_IF_ELSE))
    compile_strategy(path)


def test_weight_with_children_passes(tmp_path):
    path = _write_json(tmp_path, _make_doc(_VALID_WEIGHT))
    compile_strategy(path)


def test_filter_with_children_passes(tmp_path):
    path = _write_json(tmp_path, _make_doc(_VALID_FILTER))
    compile_strategy(path)


def test_asset_with_ticker_passes(tmp_path):
    path = _write_json(tmp_path, _make_doc(_ASSET_SPY))
    compile_strategy(path)
