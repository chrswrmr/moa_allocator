"""Unit and integration tests for netting pairs — math, column ordering, sum-to-one."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from moa_allocations.engine.runner import Runner
from moa_allocations.engine.node import AssetNode, WeightNode
from moa_allocations.engine.strategy import RootNode, Settings


# ---------------------------------------------------------------------------
# Helpers — bypass __init__ to test _apply_netting in isolation
# ---------------------------------------------------------------------------

def _runner_with_netting(netting: dict | None) -> Runner:
    """Return a Runner shell with only _netting set — sufficient to call _apply_netting."""
    obj = Runner.__new__(Runner)
    obj._netting = netting
    return obj


# ---------------------------------------------------------------------------
# 7.1 Unit tests — netting math
# ---------------------------------------------------------------------------

class TestApplyNettingMath:
    def test_net_long_1x(self):
        """Long leg dominates: freed weight goes to cash_ticker."""
        runner = _runner_with_netting({
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": "SHV",
        })
        weights = {"QQQ": 0.30, "PSQ": 0.10, "GLD": 0.60}
        result = runner._apply_netting(weights)

        assert abs(result["QQQ"] - 0.20) < 1e-10
        assert "PSQ" not in result
        assert abs(result["GLD"] - 0.60) < 1e-10
        assert abs(result["SHV"] - 0.20) < 1e-10
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_net_short_3x_inverse(self):
        """Short leg dominates with 3x inverse ETF."""
        runner = _runner_with_netting({
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "EDZ", "short_leverage": -3}],
            "cash_ticker": "SHV",
        })
        # net_exp = 0.10*1 + 0.20*(-3) = -0.50 → short wins
        # new_w_short = -0.50 / -3 = 0.1667; freed = 0.10+0.20-0.1667 = 0.1333
        weights = {"QQQ": 0.10, "EDZ": 0.20, "GLD": 0.70}
        result = runner._apply_netting(weights)

        assert "QQQ" not in result
        assert abs(result["EDZ"] - (0.50 / 3)) < 1e-10
        assert abs(result["GLD"] - 0.70) < 1e-10
        freed = 0.10 + 0.20 - (0.50 / 3)
        assert abs(result["SHV"] - freed) < 1e-10
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_perfectly_offset(self):
        """Long and short exactly cancel — all pair weight freed."""
        runner = _runner_with_netting({
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": "SHV",
        })
        weights = {"QQQ": 0.15, "PSQ": 0.15, "GLD": 0.70}
        result = runner._apply_netting(weights)

        assert "QQQ" not in result
        assert "PSQ" not in result
        assert abs(result["GLD"] - 0.70) < 1e-10
        assert abs(result["SHV"] - 0.30) < 1e-10
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_only_one_leg_present(self):
        """Short leg absent — no netting action, weights unchanged."""
        runner = _runner_with_netting({
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": "SHV",
        })
        weights = {"QQQ": 0.30, "GLD": 0.70}
        result = runner._apply_netting(weights)

        # net_exp = 0.30*1 + 0*(-1) = 0.30 > 0 → new_w_long = 0.30, freed = 0
        assert abs(result["QQQ"] - 0.30) < 1e-10
        assert abs(result["GLD"] - 0.70) < 1e-10
        assert "SHV" not in result
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_empty_pairs_list_noop(self):
        """Empty pairs list — weights returned unchanged."""
        runner = _runner_with_netting({"pairs": [], "cash_ticker": "SHV"})
        weights = {"QQQ": 0.50, "PSQ": 0.50}
        result = runner._apply_netting(weights)
        assert result == weights

    def test_no_netting_config_noop(self):
        """netting is None — weights returned unchanged."""
        runner = _runner_with_netting(None)
        weights = {"QQQ": 0.50, "PSQ": 0.50}
        result = runner._apply_netting(weights)
        assert result == weights

    def test_freed_weight_to_xcashx_when_no_cash_ticker(self):
        """No cash_ticker configured — freed weight routes to XCASHX."""
        runner = _runner_with_netting({
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": None,
        })
        weights = {"QQQ": 0.30, "PSQ": 0.10, "GLD": 0.60}
        result = runner._apply_netting(weights)

        assert abs(result["QQQ"] - 0.20) < 1e-10
        assert "PSQ" not in result
        assert abs(result["XCASHX"] - 0.20) < 1e-10
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_freed_weight_added_to_existing_cash_ticker(self):
        """Freed weight accumulates onto an existing cash ticker weight."""
        runner = _runner_with_netting({
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": "SHV",
        })
        # SHV already has 0.30 from the tree; netting QQQ/PSQ (both 0.10) frees 0.20
        weights = {"SHV": 0.30, "QQQ": 0.10, "PSQ": 0.10, "GLD": 0.50}
        result = runner._apply_netting(weights)

        assert "QQQ" not in result
        assert "PSQ" not in result
        assert abs(result["GLD"] - 0.50) < 1e-10
        assert abs(result["SHV"] - 0.50) < 1e-10  # 0.30 existing + 0.20 freed
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_multiple_pairs(self):
        """Two independent pairs both netted correctly."""
        runner = _runner_with_netting({
            "pairs": [
                {"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1},
                {"long_ticker": "EEM", "long_leverage": 1, "short_ticker": "EDZ", "short_leverage": -3},
            ],
            "cash_ticker": "SHV",
        })
        # Pair 1: QQQ=0.25, PSQ=0.05 → net=0.20 → QQQ=0.20, freed1=0.10
        # Pair 2: EEM=0.05, EDZ=0.15 → net_exp=0.05-0.45=-0.40 → EDZ=0.40/3, freed2=0.20-0.40/3
        # rest: BND=0.50
        w_qqq, w_psq = 0.25, 0.05
        w_eem, w_edz = 0.05, 0.15
        w_bnd = 0.50
        weights = {"QQQ": w_qqq, "PSQ": w_psq, "EEM": w_eem, "EDZ": w_edz, "BND": w_bnd}
        result = runner._apply_netting(weights)

        assert abs(result["QQQ"] - 0.20) < 1e-10
        assert "PSQ" not in result
        net2 = w_eem * 1 + w_edz * (-3)  # -0.40
        new_edz = -net2 / 3
        freed = (w_qqq + w_psq - 0.20) + (w_eem + w_edz - new_edz)
        assert abs(result["EDZ"] - new_edz) < 1e-10
        assert "EEM" not in result
        assert abs(result["BND"] - 0.50) < 1e-10
        assert abs(result["SHV"] - freed) < 1e-10
        assert abs(sum(result.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# 7.3 Integration test — full Runner.run() with netting pairs
# ---------------------------------------------------------------------------

_TRADING_DAYS = pd.bdate_range("2023-01-02", "2024-12-31")


def _make_price_data(tickers: list[str]) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        rng.uniform(50, 200, size=(len(_TRADING_DAYS), len(tickers))),
        index=_TRADING_DAYS,
        columns=tickers,
    )


def _settings(netting: dict | None = None) -> Settings:
    return Settings(
        id="test",
        name="netting-integration",
        starting_cash=100_000.0,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 10),
        slippage=0.0,
        fees=0.0,
        rebalance_frequency="daily",
        rebalance_threshold=None,
        netting=netting,
    )


def _build_root(netting: dict | None = None) -> RootNode:
    """Build a simple 3-asset equal-weight tree: QQQ / PSQ / GLD."""
    qqq = AssetNode(id="id-qqq", ticker="QQQ")
    psq = AssetNode(id="id-psq", ticker="PSQ")
    gld = AssetNode(id="id-gld", ticker="GLD")
    root_node = WeightNode(
        id="id-root",
        method="equal",
        method_params={},
        children=[qqq, psq, gld],
    )
    return RootNode(settings=_settings(netting), root=root_node, dsl_version="1.0.0")


class TestNettingIntegration:
    def test_run_without_netting_baseline(self):
        """Without netting all three assets receive ~1/3 each."""
        root = _build_root(netting=None)
        price_data = _make_price_data(["QQQ", "PSQ", "GLD"])
        runner = Runner(root, price_data)
        df = runner.run()

        assert list(df.columns) == ["DATE", "QQQ", "PSQ", "GLD"]
        for col in ["QQQ", "PSQ", "GLD"]:
            assert abs(df[col].iloc[0] - 1 / 3) < 1e-9

    def test_run_with_netting_non_leaf_cash_ticker(self):
        """Netting (QQQ,1,PSQ,-1) collapses to single leg; SHV receives freed weight."""
        netting = {
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": "SHV",
        }
        root = _build_root(netting=netting)
        price_data = _make_price_data(["QQQ", "PSQ", "GLD", "SHV"])
        runner = Runner(root, price_data)
        df = runner.run()

        # Column order: DSL leaves (QQQ, PSQ, GLD) → SHV (non-leaf, used) → no XCASHX
        assert list(df.columns) == ["DATE", "QQQ", "PSQ", "GLD", "SHV"]

        # Pre-netting: QQQ=1/3, PSQ=1/3, GLD=1/3
        # net_exp = 1/3 * 1 + 1/3 * (-1) = 0 → perfectly offset, all freed to SHV
        # Result: GLD=1/3, SHV=2/3
        for _, row in df.iterrows():
            assert abs(row["QQQ"] - 0.0) < 1e-9
            assert abs(row["PSQ"] - 0.0) < 1e-9
            assert abs(row["GLD"] - 1 / 3) < 1e-9
            assert abs(row["SHV"] - 2 / 3) < 1e-9

    def test_run_with_netting_freed_to_xcashx(self):
        """Netting with no cash_ticker routes freed weight to XCASHX."""
        netting = {
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": None,
        }
        root = _build_root(netting=netting)
        price_data = _make_price_data(["QQQ", "PSQ", "GLD"])
        runner = Runner(root, price_data)
        df = runner.run()

        # Column order: DSL leaves → XCASHX (last)
        assert list(df.columns) == ["DATE", "QQQ", "PSQ", "GLD", "XCASHX"]

        for _, row in df.iterrows():
            assert abs(row["QQQ"] - 0.0) < 1e-9
            assert abs(row["PSQ"] - 0.0) < 1e-9
            assert abs(row["GLD"] - 1 / 3) < 1e-9
            assert abs(row["XCASHX"] - 2 / 3) < 1e-9

    def test_run_netting_cash_ticker_already_leaf(self):
        """When cash_ticker is already a DSL leaf it stays in its original column position."""
        netting = {
            "pairs": [{"long_ticker": "QQQ", "long_leverage": 1, "short_ticker": "PSQ", "short_leverage": -1}],
            "cash_ticker": "GLD",  # GLD is already a DSL leaf
        }
        root = _build_root(netting=netting)
        price_data = _make_price_data(["QQQ", "PSQ", "GLD"])
        runner = Runner(root, price_data)
        df = runner.run()

        # GLD is in DSL leaf order — no extra column for it
        assert list(df.columns) == ["DATE", "QQQ", "PSQ", "GLD"]
        # QQQ and PSQ fully cancel; freed weight added to GLD
        for _, row in df.iterrows():
            assert abs(row["QQQ"] - 0.0) < 1e-9
            assert abs(row["PSQ"] - 0.0) < 1e-9
            assert abs(row["GLD"] - 1.0) < 1e-9
