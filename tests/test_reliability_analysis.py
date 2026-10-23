"""Tests for T30 uncertainty helpers."""

import pytest

from qaoa_reliability.analysis.reliability_analysis import wilson_interval


def test_zero_success_wilson_interval_has_nonzero_upper_bound() -> None:
    low, high = wilson_interval(0, 100)

    assert low == pytest.approx(0.0, abs=1e-15)
    assert high == pytest.approx(0.0369935, rel=1e-5)


def test_wilson_interval_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        wilson_interval(2, 1)
