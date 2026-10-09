"""Tests for canonical graph validation and identity."""


def test_schema_module_imports() -> None:
    from qaoa_reliability.graphs import schema

    assert schema.__doc__

