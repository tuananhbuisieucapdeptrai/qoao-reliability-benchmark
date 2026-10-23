"""Direct tests for the optional Qiskit statevector adapter."""

from __future__ import annotations

import math

import networkx as nx
import pytest

pytest.importorskip("qiskit")

from qaoa_reliability.evaluators import (  # noqa: E402
    EvaluationValidationError,
    Evaluator,
)
from qaoa_reliability.evaluators.qiskit_statevector import (  # noqa: E402
    QiskitStatevectorEvaluator,
    _build_maxcut_observable,
    _build_qaoa_circuit,
)
from qaoa_reliability.graphs.schema import from_networkx  # noqa: E402


def _record(graph: nx.Graph):
    return from_networkx(graph, family="fixture", seed=None)


def test_qiskit_evaluator_satisfies_runtime_protocol() -> None:
    assert isinstance(QiskitStatevectorEvaluator(), Evaluator)


def test_zero_angles_return_uniform_expected_cut() -> None:
    graph = _record(nx.cycle_graph(5))
    result = QiskitStatevectorEvaluator().evaluate(
        graph, depth=1, parameters=(0.0, 0.0)
    )
    assert result.objective == pytest.approx(len(graph.edges) / 2, abs=1e-12)


def test_single_edge_analytic_optimum() -> None:
    result = QiskitStatevectorEvaluator().evaluate(
        _record(nx.path_graph(2)),
        depth=1,
        parameters=(math.pi / 2, math.pi / 8),
    )
    assert result.objective == pytest.approx(1.0, abs=1e-12)


def test_empty_edge_set_has_zero_expectation_and_valid_observable() -> None:
    graph = _record(nx.empty_graph(3))
    observable = _build_maxcut_observable(graph)
    result = QiskitStatevectorEvaluator().evaluate(
        graph, depth=1, parameters=(0.73, 0.19)
    )
    assert observable.num_qubits == graph.n_nodes
    assert result.objective == 0.0


def test_circuit_has_one_cost_and_mixer_layer_per_depth() -> None:
    graph = _record(nx.path_graph(3))
    circuit = _build_qaoa_circuit(graph, 2, (0.1, 0.2, 0.3, 0.4))
    operations = circuit.count_ops()
    assert operations["h"] == 3
    assert operations["rzz"] == 4
    assert operations["rx"] == 6


def test_result_records_dependency_versions_and_conventions() -> None:
    result = QiskitStatevectorEvaluator().evaluate(
        _record(nx.path_graph(2)), depth=1, parameters=(0.2, 0.3)
    )
    assert result.evaluator == "qiskit_statevector"
    assert result.metadata["qiskit_version"]
    assert result.metadata["numpy_version"]
    assert result.metadata["objective_convention"] == "positive_expected_cut_value"


@pytest.mark.parametrize(
    ("depth", "parameters", "message"),
    [
        (0, (), "positive integer"),
        (1, (0.1,), "requires 2 parameters"),
        (2, (0.1, 0.2, 0.3), "requires 4 parameters"),
        (1, (0.1, float("nan")), "finite real number"),
    ],
)
def test_request_validation(depth, parameters, message: str) -> None:
    with pytest.raises(EvaluationValidationError, match=message):
        QiskitStatevectorEvaluator().evaluate(
            _record(nx.path_graph(2)), depth, parameters
        )


def test_statevector_size_guard() -> None:
    with pytest.raises(EvaluationValidationError, match="evaluator limit"):
        QiskitStatevectorEvaluator(max_qubits=2).evaluate(
            _record(nx.path_graph(3)), depth=1, parameters=(0.1, 0.2)
        )
