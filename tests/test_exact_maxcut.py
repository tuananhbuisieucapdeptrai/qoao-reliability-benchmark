"""Tests for exact unweighted-MaxCut ground truth."""


def test_exact_maxcut_module_imports() -> None:
    from qaoa_reliability.exact import maxcut

    assert maxcut.__doc__

