"""Tests for the paired T31 model-comparison interval."""

import pytest

from qaoa_reliability.analysis.predictive_analysis import paired_mae_improvement_ci


def test_paired_improvement_is_positive_when_expanded_errors_are_smaller() -> None:
    mean, low, high = paired_mae_improvement_ci(
        (0.4, 0.3, 0.2, 0.1),
        (0.2, 0.2, 0.1, 0.05),
        n_resamples=2_000,
        seed=11,
    )

    assert mean == pytest.approx(0.1125)
    assert low > 0
    assert high > mean


def test_paired_improvement_rejects_mismatched_vectors() -> None:
    with pytest.raises(ValueError, match="equal-length"):
        paired_mae_improvement_ci((0.1, 0.2), (0.1,))
