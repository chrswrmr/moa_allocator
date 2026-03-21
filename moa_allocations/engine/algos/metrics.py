"""
metrics.py — Pure metric computation functions for the MoA allocation engine.

Public interface: compute_metric(series, function, lookback) -> float

All functions are pure (no side effects, no state). Returns np.nan when the
series is too short for the requested computation. All metrics treat series[-1]
as today's close (ADR-003).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Private implementations
# ---------------------------------------------------------------------------

def _current_price(series: np.ndarray, lookback: int) -> float:
    return float(series[-1])


def _cumulative_return(series: np.ndarray, lookback: int) -> float:
    return float((series[-1] / series[-lookback]) - 1.0)


def _sma_price(series: np.ndarray, lookback: int) -> float:
    return float(np.mean(series[-lookback:]))


def _ema_price(series: np.ndarray, lookback: int) -> float:
    return float(pd.Series(series).ewm(span=lookback, adjust=False).mean().iloc[-1])


def _sma_return(series: np.ndarray, lookback: int) -> float:
    returns = np.diff(series) / series[:-1]
    return float(np.mean(returns[-lookback:]))


def _max_drawdown(series: np.ndarray, lookback: int) -> float:
    window = series[-lookback:]
    peak = np.maximum.accumulate(window)
    drawdowns = (window - peak) / peak
    return float(np.min(drawdowns))


def _rsi(series: np.ndarray, lookback: int) -> float:
    returns = np.diff(series[-lookback - 1:])
    gains = np.where(returns > 0, returns, 0.0)
    losses = np.where(returns < 0, -returns, 0.0)
    avg_gain = gains[0]
    avg_loss = losses[0]
    for g, l in zip(gains[1:], losses[1:]):
        avg_gain = (avg_gain * (lookback - 1) + g) / lookback
        avg_loss = (avg_loss * (lookback - 1) + l) / lookback
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _std_dev_price(series: np.ndarray, lookback: int) -> float:
    return float(np.std(series[-lookback:], ddof=1))


def _std_dev_return(series: np.ndarray, lookback: int) -> float:
    returns = np.diff(series) / series[:-1]
    return float(np.std(returns[-lookback:], ddof=1))


# ---------------------------------------------------------------------------
# Dispatch tables
# ---------------------------------------------------------------------------

# Functions that need len(series) >= lookback (price window).
_NEEDS_LOOKBACK_PRICES = frozenset(
    {"cumulative_return", "sma_price", "max_drawdown", "std_dev_price"}
)

# Functions that need len(series) >= lookback + 1 (return window).
_NEEDS_LOOKBACK_RETURNS = frozenset({"sma_return", "rsi", "std_dev_return"})

_DISPATCH: dict[str, Callable[[np.ndarray, int], float]] = {
    "current_price":     _current_price,
    "cumulative_return": _cumulative_return,
    "sma_price":         _sma_price,
    "ema_price":         _ema_price,
    "sma_return":        _sma_return,
    "max_drawdown":      _max_drawdown,
    "rsi":               _rsi,
    "std_dev_price":     _std_dev_price,
    "std_dev_return":    _std_dev_return,
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def compute_metric(series: np.ndarray, function: str, lookback: int) -> float:
    """Compute a DSL metric over *series* using the given *lookback* window.

    Parameters
    ----------
    series:   Price (or NAV) series in chronological order. series[-1] is today.
    function: DSL metric name (e.g. ``"sma_price"``).
    lookback: Trailing window in trading days (already converted from DSL string
              by the compiler).

    Returns
    -------
    float — metric value, or ``np.nan`` if the series is too short.

    Raises
    ------
    ValueError — if *function* is not a recognised DSL metric name.
    """
    if function not in _DISPATCH:
        raise ValueError(
            f"Unknown metric function {function!r}. "
            f"Valid functions: {sorted(_DISPATCH)}"
        )

    n = len(series)

    # Empty-series guard (applies to current_price and ema_price too)
    if n == 0:
        return np.nan

    # Dynamic minimum-length checks per function family
    if function in _NEEDS_LOOKBACK_PRICES and n < lookback:
        return np.nan
    if function in _NEEDS_LOOKBACK_RETURNS and n < lookback + 1:
        return np.nan

    return float(_DISPATCH[function](series, lookback))
