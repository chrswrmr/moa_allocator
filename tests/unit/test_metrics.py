"""Tests for compute_metric() and all 9 metric functions."""
import math

import numpy as np
import pytest

from moa_allocations.engine.algos.metrics import compute_metric


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def arr(*values: float) -> np.ndarray:
    return np.array(values, dtype=float)


# ---------------------------------------------------------------------------
# 7.2 Known-value tests (hand-calculated)
# ---------------------------------------------------------------------------

class TestCurrentPrice:
    def test_returns_last_element(self):
        assert compute_metric(arr(100.0, 101.0, 102.0), "current_price", 0) == pytest.approx(102.0)

    def test_single_element(self):
        assert compute_metric(arr(50.0), "current_price", 0) == pytest.approx(50.0)


class TestCumulativeReturn:
    def test_known_values(self):
        # (115 / 110) - 1 = 0.04545...
        result = compute_metric(arr(100.0, 110.0, 105.0, 115.0), "cumulative_return", 3)
        assert result == pytest.approx((115.0 / 110.0) - 1.0)

    def test_flat_series(self):
        result = compute_metric(arr(100.0, 100.0, 100.0), "cumulative_return", 3)
        assert result == pytest.approx(0.0)


class TestSmaPrice:
    def test_known_values(self):
        # mean([30, 40, 50]) = 40
        result = compute_metric(arr(10.0, 20.0, 30.0, 40.0, 50.0), "sma_price", 3)
        assert result == pytest.approx(40.0)


class TestEmaPrice:
    def test_returns_float(self):
        result = compute_metric(arr(10.0, 20.0, 30.0, 40.0), "ema_price", 3)
        assert isinstance(result, float)
        assert not math.isnan(result)

    def test_series_shorter_than_span_still_returns_value(self):
        # EMA should compute even with fewer bars than lookback
        result = compute_metric(arr(10.0, 20.0), "ema_price", 10)
        assert not math.isnan(result)


class TestSmaReturn:
    def test_known_values(self):
        # returns: [0.1, -0.04545..., 0.09524...]
        # mean of last 2: (-0.04545 + 0.09524) / 2
        series = arr(100.0, 110.0, 105.0, 115.0)
        returns = np.diff(series) / series[:-1]
        expected = float(np.mean(returns[-2:]))
        result = compute_metric(series, "sma_return", 2)
        assert result == pytest.approx(expected)


class TestMaxDrawdown:
    def test_known_drawdown(self):
        # peak: [100, 120, 120, 120], drawdowns: [0, 0, -0.25, -0.0833]
        result = compute_metric(arr(100.0, 120.0, 90.0, 110.0), "max_drawdown", 4)
        assert result == pytest.approx(-0.25)

    def test_monotonically_increasing(self):
        result = compute_metric(arr(10.0, 20.0, 30.0, 40.0), "max_drawdown", 4)
        assert result == pytest.approx(0.0)

    def test_flat_series(self):
        result = compute_metric(arr(50.0, 50.0, 50.0), "max_drawdown", 3)
        assert result == pytest.approx(0.0)


class TestRsi:
    def test_all_gains_returns_100(self):
        # Monotonically increasing prices → all gains, no losses
        series = arr(10.0, 11.0, 12.0, 13.0, 14.0, 15.0)
        result = compute_metric(series, "rsi", 5)
        assert result == pytest.approx(100.0)

    def test_all_losses_returns_0(self):
        # Monotonically decreasing prices → all losses, no gains
        series = arr(15.0, 14.0, 13.0, 12.0, 11.0, 10.0)
        result = compute_metric(series, "rsi", 5)
        assert result == pytest.approx(0.0)

    def test_value_in_range(self):
        series = arr(44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.15,
                     43.61, 44.33, 44.83, 45.10, 45.15, 43.61, 44.33)
        result = compute_metric(series, "rsi", 14)
        assert 0.0 <= result <= 100.0


class TestStdDevPrice:
    def test_known_values(self):
        # std([10, 20, 30], ddof=1) = 10.0
        result = compute_metric(arr(10.0, 20.0, 30.0), "std_dev_price", 3)
        assert result == pytest.approx(10.0)

    def test_flat_series(self):
        result = compute_metric(arr(5.0, 5.0, 5.0), "std_dev_price", 3)
        assert result == pytest.approx(0.0)


class TestStdDevReturn:
    def test_known_values(self):
        series = arr(100.0, 110.0, 105.0, 115.0)
        returns = np.diff(series) / series[:-1]
        expected = float(np.std(returns, ddof=1))
        result = compute_metric(series, "std_dev_return", 3)
        assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 7.3 NaN for insufficient data
# ---------------------------------------------------------------------------

class TestNanOnInsufficientData:
    @pytest.mark.parametrize("function,series,lookback", [
        ("cumulative_return", arr(100.0, 105.0), 5),
        ("sma_price",         arr(100.0, 105.0), 5),
        ("sma_return",        arr(100.0, 105.0), 5),   # needs lookback+1=6
        ("max_drawdown",      arr(100.0, 105.0), 5),
        ("rsi",               arr(100.0, 105.0), 5),   # needs lookback+1=6
        ("std_dev_price",     arr(100.0, 105.0), 5),
        ("std_dev_return",    arr(100.0, 105.0), 5),   # needs lookback+1=6
    ])
    def test_returns_nan(self, function, series, lookback):
        result = compute_metric(series, function, lookback)
        assert math.isnan(result), f"{function} should return nan"


# ---------------------------------------------------------------------------
# 7.4 Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_series_current_price(self):
        result = compute_metric(arr(), "current_price", 0)
        assert math.isnan(result)

    def test_empty_series_ema_price(self):
        result = compute_metric(arr(), "ema_price", 10)
        assert math.isnan(result)

    def test_single_element_current_price(self):
        assert compute_metric(arr(42.0), "current_price", 0) == pytest.approx(42.0)

    def test_single_element_cumulative_return_nan(self):
        # lookback=5, only 1 element → nan
        result = compute_metric(arr(100.0), "cumulative_return", 5)
        assert math.isnan(result)

    def test_flat_series_cumulative_return(self):
        result = compute_metric(arr(100.0, 100.0, 100.0, 100.0), "cumulative_return", 4)
        assert result == pytest.approx(0.0)

    def test_rsi_all_gain(self):
        series = arr(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        assert compute_metric(series, "rsi", 5) == pytest.approx(100.0)

    def test_rsi_all_loss(self):
        series = arr(6.0, 5.0, 4.0, 3.0, 2.0, 1.0)
        assert compute_metric(series, "rsi", 5) == pytest.approx(0.0)

    def test_max_drawdown_monotonically_increasing(self):
        result = compute_metric(arr(1.0, 2.0, 3.0, 4.0, 5.0), "max_drawdown", 5)
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 7.5 ValueError on invalid function name
# ---------------------------------------------------------------------------

class TestInvalidFunctionName:
    def test_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown_metric"):
            compute_metric(arr(100.0, 101.0), "unknown_metric", 1)

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            compute_metric(arr(100.0), "", 1)


# ---------------------------------------------------------------------------
# 7.6 Input array not mutated
# ---------------------------------------------------------------------------

class TestNoMutation:
    @pytest.mark.parametrize("function,lookback", [
        ("current_price",     0),
        ("cumulative_return", 3),
        ("sma_price",         3),
        ("ema_price",         3),
        ("sma_return",        3),
        ("max_drawdown",      3),
        ("rsi",               3),
        ("std_dev_price",     3),
        ("std_dev_return",    3),
    ])
    def test_input_unchanged(self, function, lookback):
        original = arr(10.0, 20.0, 30.0, 40.0, 50.0)
        before = original.copy()
        compute_metric(original, function, lookback)
        np.testing.assert_array_equal(original, before, err_msg=f"{function} mutated input")


class TestIdempotency:
    @pytest.mark.parametrize("function,lookback", [
        ("current_price",     0),
        ("cumulative_return", 3),
        ("sma_price",         3),
        ("ema_price",         3),
        ("sma_return",        3),
        ("max_drawdown",      3),
        ("rsi",               3),
        ("std_dev_price",     3),
        ("std_dev_return",    3),
    ])
    def test_identical_calls_return_identical_results(self, function, lookback):
        series = arr(10.0, 20.0, 30.0, 40.0, 50.0)
        result1 = compute_metric(series, function, lookback)
        result2 = compute_metric(series, function, lookback)
        if math.isnan(result1):
            assert math.isnan(result2)
        else:
            assert result1 == result2
