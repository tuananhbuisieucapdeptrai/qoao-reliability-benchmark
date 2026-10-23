"""Tests for deterministic T29 uncertainty calculations."""

import pytest

from qaoa_reliability.analysis.pilot_figures import bootstrap_mean_ci


def test_bootstrap_mean_ci_is_deterministic_and_contains_mean() -> None:
    first = bootstrap_mean_ci((1.0, 2.0, 3.0, 4.0), n_resamples=2_000, seed=7)
    second = bootstrap_mean_ci((1.0, 2.0, 3.0, 4.0), n_resamples=2_000, seed=7)

    assert first == second
    mean, low, high = first
    assert mean == pytest.approx(2.5)
    assert low < mean < high


@pytest.mark.parametrize("values", ((), (1.0,), (1.0, float("nan"))))
def test_bootstrap_rejects_invalid_samples(values) -> None:
    with pytest.raises(ValueError, match="at least two finite"):
        bootstrap_mean_ci(values)
