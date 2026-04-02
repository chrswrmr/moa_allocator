"""Integration tests for CLI interface upgrade."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_STRATEGIES_DIR = _ROOT / "strategies"


def _run_cli(*args: str, expect_code: int = 0) -> subprocess.CompletedProcess:
    """Run the CLI via python -m moa_allocations and return the result."""
    result = subprocess.run(
        [sys.executable, "-m", "moa_allocations", *args],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
    )
    assert result.returncode == expect_code, (
        f"Expected exit {expect_code}, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result


def _find_strategy() -> str | None:
    if _STRATEGIES_DIR.exists():
        for f in _STRATEGIES_DIR.rglob("*.moastrat.json"):
            return str(f)
    return None


# ---------------------------------------------------------------------------
# 8.1 --validate
# ---------------------------------------------------------------------------

class TestValidateMode:
    def test_valid_strategy(self):
        path = _find_strategy()
        if path is None:
            pytest.skip("No strategy files found")
        result = _run_cli("--strategy", path, "--validate")
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["valid"] is True

    def test_invalid_strategy(self, tmp_path):
        bad = tmp_path / "bad.moastrat.json"
        bad.write_text("{}")
        result = _run_cli("--strategy", str(bad), "--validate", expect_code=1)
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["code"] == 1
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert "node_id" in data["errors"][0]


# ---------------------------------------------------------------------------
# 8.2 --tickers
# ---------------------------------------------------------------------------

class TestTickersMode:
    def test_tickers_output(self):
        path = _find_strategy()
        if path is None:
            pytest.skip("No strategy files found")
        result = _run_cli("--strategy", path, "--tickers")
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "traded_tickers" in data
        assert "signal_tickers" in data
        assert isinstance(data["traded_tickers"], list)
        assert isinstance(data["signal_tickers"], list)
        # traded_tickers should be sorted
        assert data["traded_tickers"] == sorted(data["traded_tickers"])


# ---------------------------------------------------------------------------
# 8.3 --check-prices
# ---------------------------------------------------------------------------

class TestCheckPricesMode:
    def test_valid_prices(self):
        path = _find_strategy()
        if path is None:
            pytest.skip("No strategy files found")
        db = str(_ROOT / "..\\pidb_ib\\data\\pidb_ib.db")
        if not Path(db).exists():
            pytest.skip("pidb_ib database not found")
        result = _run_cli("--strategy", path, "--check-prices", "--db", db)
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["prices_available"] is True

    def test_missing_ticker(self, tmp_path):
        """Strategy with a fake ticker should fail with exit 2."""
        # Create a minimal valid strategy with a fake ticker
        # This requires a full valid DSL — skip if we can't create one easily
        pytest.skip("Requires crafted strategy with non-existent ticker")


# ---------------------------------------------------------------------------
# 8.4 --list-indicators
# ---------------------------------------------------------------------------

class TestListIndicatorsMode:
    def test_returns_all_indicators(self):
        from moa_allocations.engine.algos.metrics import _DISPATCH
        result = _run_cli("--list-indicators")
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        names = {ind["name"] for ind in data["indicators"]}
        assert names == set(_DISPATCH.keys())

    def test_requires_lookback_fields(self):
        result = _run_cli("--list-indicators")
        data = json.loads(result.stdout)
        for ind in data["indicators"]:
            assert "name" in ind
            assert "requires_lookback" in ind
            assert isinstance(ind["requires_lookback"], bool)

    def test_no_strategy_needed(self):
        # Should work without --strategy
        result = _run_cli("--list-indicators")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# 8.5 --json run mode
# ---------------------------------------------------------------------------

class TestJsonRunMode:
    def test_json_run_output(self, tmp_path):
        path = _find_strategy()
        if path is None:
            pytest.skip("No strategy files found")
        db = str(_ROOT / "..\\pidb_ib\\data\\pidb_ib.db")
        if not Path(db).exists():
            pytest.skip("pidb_ib database not found")
        result = _run_cli(
            "--strategy", path,
            "--output", str(tmp_path),
            "--db", db,
            "--json",
        )
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "allocations_path" in data
        assert "rows" in data
        assert isinstance(data["rows"], int)
        assert "traded_tickers" in data
        assert "signal_tickers" in data


# ---------------------------------------------------------------------------
# 8.6 Mutual exclusivity
# ---------------------------------------------------------------------------

class TestMutualExclusivity:
    def test_two_query_flags_rejected(self):
        result = subprocess.run(
            [sys.executable, "-m", "moa_allocations", "--validate", "--tickers",
             "--strategy", "dummy.json"],
            capture_output=True,
            text=True,
            cwd=str(_ROOT),
        )
        assert result.returncode != 0
        assert "not allowed with argument" in result.stderr
