"""Tests for the framework-independent evaluator contract."""

from __future__ import annotations

import json
from dataclasses import replace

import networkx as nx
import pytest

from qaoa_reliability.evaluators import (
    EvaluationValidationError,
    Evaluator,
    NumpyStatevectorEvaluator,
)
from qaoa_reliability.graphs.schema import from_networkx


def _edge_graph():
    return from_networkx(nx.path_graph(2), family="fixture", seed=None)


def test_numpy_evaluator_satisfies_runtime_protocol() -> None:
    assert isinstance(NumpyStatevectorEvaluator(), Evaluator)


def test_result_is_json_compatible_and_has_stable_identity() -> None:
    evaluator = NumpyStatevectorEvaluator()
    first = evaluator.evaluate(_edge_graph(), depth=1, parameters=(0.2, 0.3))
    second = evaluator.evaluate(_edge_graph(), depth=1, parameters=(0.2, 0.3))

    assert first == second
    assert first.evaluation_id.startswith("sha256:")
    assert json.loads(json.dumps(first.to_dict())) == first.to_dict()


def test_evaluation_identity_distinguishes_parameter_vectors() -> None:
    evaluator = NumpyStatevectorEvaluator()
    first = evaluator.evaluate(_edge_graph(), depth=1, parameters=(0.2, 0.3))
    second = evaluator.evaluate(_edge_graph(), depth=1, parameters=(0.2, 0.4))

    assert first.evaluation_id != second.evaluation_id


def test_result_rejects_mismatched_evaluation_id() -> None:
    result = NumpyStatevectorEvaluator().evaluate(
        _edge_graph(), depth=1, parameters=(0.2, 0.3)
    )
    with pytest.raises(EvaluationValidationError, match="evaluation_id"):
        replace(result, evaluation_id="sha256:" + "0" * 64)


def test_result_rejects_malformed_graph_id() -> None:
    result = NumpyStatevectorEvaluator().evaluate(
        _edge_graph(), depth=1, parameters=(0.2, 0.3)
    )
    with pytest.raises(EvaluationValidationError, match="graph_id"):
        replace(result, graph_id="sha256:not-a-digest")


@pytest.mark.parametrize(
    ("depth", "parameters", "message"),
    [
        (0, (), "positive integer"),
        (True, (0.1, 0.2), "positive integer"),
        (1, (0.1,), "requires 2 parameters"),
        (1, (0.1, 0.2, 0.3), "requires 2 parameters"),
        (1, (0.1, float("nan")), "finite real number"),
        (1, (0.1, float("inf")), "finite real number"),
        (1, (0.1, True), "finite real number"),
    ],
)
def test_request_validation(depth, parameters, message: str) -> None:
    with pytest.raises(EvaluationValidationError, match=message):
        NumpyStatevectorEvaluator().evaluate(_edge_graph(), depth, parameters)


def test_statevector_size_guard() -> None:
    graph = from_networkx(nx.path_graph(3), family="fixture", seed=None)
    with pytest.raises(EvaluationValidationError, match="evaluator limit"):
        NumpyStatevectorEvaluator(max_qubits=2).evaluate(
            graph, depth=1, parameters=(0.1, 0.2)
        )
