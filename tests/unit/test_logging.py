"""Tests for logging capability (add-logger change)."""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import pytest

from moa_allocations.compiler import compile_strategy
from moa_allocations.engine import Runner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_data(tickers: list[str], start: str = "2023-12-01", end: str = "2024-03-29") -> pd.DataFrame:
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        rng.uniform(100, 200, size=(len(idx), len(tickers))),
        index=idx,
        columns=tickers,
    ).astype("float64")


_SIMPLE_STRATEGY = {
    "id": "aa000000-0000-0000-0000-000000000001",
    "version-dsl": "1.0.0",
    "settings": {
        "id": "bb000000-0000-0000-0000-000000000001",
        "name": "Log Test Strategy",
        "starting_cash": 100_000,
        "start_date": "2024-01-02",
        "end_date": "2024-02-29",
        "rebalance_frequency": "weekly",
    },
    "root_node": {
        "id": "cc000000-0000-0000-0000-000000000001",
        "type": "weight",
        "name": "root",
        "method": "equal",
        "children": [
            {"id": "dd000000-0000-0000-0000-000000000001", "type": "asset", "ticker": "SPY"},
            {"id": "dd000000-0000-0000-0000-000000000002", "type": "asset", "ticker": "BND"},
        ],
    },
}


@pytest.fixture(autouse=True)
def clean_moa_logger():
    """Remove all handlers from moa_allocations logger around each test."""
    yield
    logger = logging.getLogger("moa_allocations")
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)


# ---------------------------------------------------------------------------
# 8.1 — Log file created at expected path
# ---------------------------------------------------------------------------

def test_log_file_created_at_expected_path(tmp_path):
    """_setup_logging creates a FileHandler writing to the given path."""
    from main import _setup_logging

    log_path = tmp_path / "20240102_1000_test_log.txt"
    _setup_logging(log_path, debug=False)

    moa_logger = logging.getLogger("moa_allocations")
    moa_logger.debug("sentinel log message")

    # Flush and close file handler so the file is written
    for h in moa_logger.handlers:
        h.flush()

    assert log_path.exists()
    assert "sentinel log message" in log_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 8.2 — Log file contains all keyword anchors
# ---------------------------------------------------------------------------

def test_keyword_anchors_in_log(caplog, tmp_path):
    """compile_strategy + Runner.run() emit all expected keyword anchors at DEBUG level."""
    path = tmp_path / "strategy.moastrat.json"
    path.write_text(json.dumps(_SIMPLE_STRATEGY), encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="moa_allocations"):
        root = compile_strategy(str(path))
        price_data = _make_price_data(["SPY", "BND"])
        runner = Runner(root, price_data)
        runner.run()

    log_text = caplog.text
    for keyword in ("COMPILE", "DOWNWARD", "NAV", "ALLOC", "UPWARD"):
        assert keyword in log_text, f"Keyword '{keyword}' not found in log output"


# ---------------------------------------------------------------------------
# 8.3 — --debug flag controls StreamHandler level
# ---------------------------------------------------------------------------

def test_setup_logging_debug_sets_stream_handler_to_debug(tmp_path):
    """_setup_logging(debug=True) sets StreamHandler level to DEBUG."""
    from main import _setup_logging

    log_path = tmp_path / "log.txt"
    _setup_logging(log_path, debug=True)
    moa_logger = logging.getLogger("moa_allocations")

    stream_handlers = [
        h for h in moa_logger.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    ]
    assert stream_handlers, "Expected at least one StreamHandler"
    assert all(h.level == logging.DEBUG for h in stream_handlers)


def test_setup_logging_no_debug_sets_stream_handler_to_info(tmp_path):
    """_setup_logging(debug=False) sets StreamHandler level to INFO."""
    from main import _setup_logging

    log_path = tmp_path / "log.txt"
    _setup_logging(log_path, debug=False)
    moa_logger = logging.getLogger("moa_allocations")

    stream_handlers = [
        h for h in moa_logger.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    ]
    assert stream_handlers, "Expected at least one StreamHandler"
    assert all(h.level == logging.INFO for h in stream_handlers)


# ---------------------------------------------------------------------------
# 8.4 — Library import produces no output (NullHandler behaviour)
# ---------------------------------------------------------------------------

def test_library_import_no_handlers():
    """Importing moa_allocations modules does not attach handlers to the logger."""
    import moa_allocations.compiler.compiler  # noqa: F401
    import moa_allocations.engine.runner  # noqa: F401
    import moa_allocations.engine.algos.selection  # noqa: F401
    import moa_allocations.engine.algos.weighting  # noqa: F401

    moa_logger = logging.getLogger("moa_allocations")
    # The fixture clears handlers after each test; at import time there should be none
    assert len(moa_logger.handlers) == 0


# ---------------------------------------------------------------------------
# 8.5 — UPWARD pass detail respects log level
# ---------------------------------------------------------------------------

def test_upward_pass_detail_at_debug_level(caplog, tmp_path):
    """UPWARD pass per-node blocks appear at DEBUG level and not at INFO level."""
    path = tmp_path / "strategy.moastrat.json"
    path.write_text(json.dumps(_SIMPLE_STRATEGY), encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="moa_allocations"):
        root = compile_strategy(str(path))
        price_data = _make_price_data(["SPY", "BND"])
        runner = Runner(root, price_data)
        runner.run()

    assert "┌─" in caplog.text, "Expected per-node block markers at DEBUG level"
    assert "UPWARD" in caplog.text, "Expected UPWARD keyword at DEBUG level"

    caplog.clear()

    with caplog.at_level(logging.INFO, logger="moa_allocations"):
        root = compile_strategy(str(path))
        price_data = _make_price_data(["SPY", "BND"])
        runner = Runner(root, price_data)
        runner.run()

    assert "┌─" not in caplog.text, "Per-node block markers should not appear at INFO level"
    assert "UPWARD" not in caplog.text, "UPWARD keyword should not appear at INFO level"


# ---------------------------------------------------------------------------
# 8.6 — DOWNWARD pass detail appears at DEBUG level
# ---------------------------------------------------------------------------

def test_downward_pass_detail_at_debug_level(caplog, tmp_path):
    """DOWNWARD pass per-node blocks appear at DEBUG level and not at INFO level."""
    path = tmp_path / "strategy.moastrat.json"
    path.write_text(json.dumps(_SIMPLE_STRATEGY), encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="moa_allocations"):
        root = compile_strategy(str(path))
        price_data = _make_price_data(["SPY", "BND"])
        runner = Runner(root, price_data)
        runner.run()

    assert "┌─" in caplog.text, "Expected per-node block markers at DEBUG level"
    assert "DOWNWARD" in caplog.text, "Expected DOWNWARD keyword at DEBUG level"

    caplog.clear()

    with caplog.at_level(logging.INFO, logger="moa_allocations"):
        root = compile_strategy(str(path))
        price_data = _make_price_data(["SPY", "BND"])
        runner = Runner(root, price_data)
        runner.run()

    assert "┌─" not in caplog.text, "Per-node block markers should not appear at INFO level"
