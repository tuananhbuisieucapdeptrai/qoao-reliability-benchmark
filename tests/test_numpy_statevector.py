"""Convention and analytic tests for the NumPy QAOA evaluator."""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest

from qaoa_reliability.evaluators.numpy_statevector import (
    NumpyStatevectorEvaluator,
    _apply_mixer,
    _cut_values,
)
from qaoa_reliability.graphs.schema import from_networkx


def _record(graph: nx.Graph):
    return from_networkx(graph, family="fixture", seed=None)


def test_zero_angles_return_uniform_expected_cut() -> None:
    graph = _record(nx.cycle_graph(5))
    result = NumpyStatevectorEvaluator().evaluate(graph, depth=1, parameters=(0.0, 0.0))
    assert result.objective == pytest.approx(len(graph.edges) / 2)


def test_single_edge_analytic_optimum_catches_cost_sign_and_angle_factors() -> None:
    graph = _record(nx.path_graph(2))
    result = NumpyStatevectorEvaluator().evaluate(
        graph,
        depth=1,
        parameters=(math.pi / 2, math.pi / 8),
    )
    assert result.objective == pytest.approx(1.0, abs=1e-12)


def test_single_edge_analytic_formula() -> None:
    graph = _record(nx.path_graph(2))
    gamma = 0.37
    beta = 0.21
    expected = 0.5 * (1.0 + math.sin(4.0 * beta) * math.sin(gamma))

    result = NumpyStatevectorEvaluator().evaluate(
        graph, depth=1, parameters=(gamma, beta)
    )
    assert result.objective == pytest.approx(expected, abs=1e-12)


def test_negative_gamma_reverses_single_edge_improvement() -> None:
    graph = _record(nx.path_graph(2))
    positive = NumpyStatevectorEvaluator().evaluate(
        graph, depth=1, parameters=(math.pi / 2, math.pi / 8)
    )
    negative = NumpyStatevectorEvaluator().evaluate(
        graph, depth=1, parameters=(-math.pi / 2, math.pi / 8)
    )
    assert positive.objective == pytest.approx(1.0, abs=1e-12)
    assert negative.objective == pytest.approx(0.0, abs=1e-12)


def test_cost_values_use_vertex_index_as_little_endian_qubit_index() -> None:
    graph = nx.Graph()
    graph.add_nodes_from(range(3))
    graph.add_edge(0, 1)
    values = _cut_values(_record(graph))

    np.testing.assert_array_equal(values, [0, 1, 1, 0, 0, 1, 1, 0])


def test_mixer_uses_exp_minus_i_beta_x_convention() -> None:
    state = np.array([1.0, 0.0], dtype=np.complex128)
    _apply_mixer(state, beta=math.pi / 2, n_qubits=1)
    np.testing.assert_allclose(state, [0.0, -1.0j], atol=1e-12)


def test_zero_second_layer_matches_depth_one() -> None:
    graph = _record(nx.path_graph(3))
    gamma = 0.41
    beta = 0.29
    evaluator = NumpyStatevectorEvaluator()

    depth_one = evaluator.evaluate(graph, 1, (gamma, beta))
    depth_two = evaluator.evaluate(graph, 2, (gamma, 0.0, beta, 0.0))
    assert depth_two.objective == pytest.approx(depth_one.objective, abs=1e-12)


def test_empty_edge_set_has_zero_expectation() -> None:
    graph = nx.empty_graph(3)
    result = NumpyStatevectorEvaluator().evaluate(
        _record(graph), depth=1, parameters=(0.73, 0.19)
    )
    assert result.objective == 0.0
