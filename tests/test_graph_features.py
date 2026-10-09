"""Tests for baseline graph-feature extraction."""


def test_graph_features_module_imports() -> None:
    from qaoa_reliability.features import graph_features

    assert graph_features.__doc__

