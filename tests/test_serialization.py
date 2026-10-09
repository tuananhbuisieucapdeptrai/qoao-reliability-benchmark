"""Tests for validated graph-record serialization."""


def test_serialization_module_imports() -> None:
    from qaoa_reliability.graphs import serialization

    assert serialization.__doc__

