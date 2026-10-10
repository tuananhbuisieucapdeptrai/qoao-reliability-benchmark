"""Tests for exact unweighted-MaxCut ground truth."""

from __future__ import annotations

from itertools import product

import networkx as nx
import pytest

from qaoa_reliability.exact.maxcut import (
    EXACT_MAXCUT_SOLVER,
    EXACT_MAXCUT_SOLVER_VERSION,
    ExactMaxCutResult,
    ExactSolverSizeError,
    cut_value,
    solve_exact_maxcut,
)
from qaoa_reliability.graphs.schema import (
    GraphRecord,
    GraphValidationError,
    from_networkx,
)


def make_record(graph: nx.Graph) -> GraphRecord:
    return from_networkx(
        graph,
        family="test_fixture",
        seed=None,
        parameters={"purpose": "exact-solver test"},
    )


def naive_full_maxcut(record: GraphRecord) -> int:
    return max(
        cut_value(record, bits) for bits in product((0, 1), repeat=record.n_nodes)
    )


def assert_valid_result(record: GraphRecord, result: ExactMaxCutResult) -> None:
    assert result.graph_id == record.graph_id
    assert len(result.representative_bitstring) == record.n_nodes
    assert result.representative_bitstring[0] == 0
    assert cut_value(record, result.representative_bitstring) == result.optimum
    assert result.assignments_evaluated == 2 ** (record.n_nodes - 1)
    assert result.solver == EXACT_MAXCUT_SOLVER
    assert result.solver_version == EXACT_MAXCUT_SOLVER_VERSION


def test_cut_value_counts_crossing_edges() -> None:
    record = make_record(nx.path_graph(4))

    assert cut_value(record, (0, 1, 0, 1)) == 3
    assert cut_value(record, (0, 0, 1, 1)) == 1
    assert cut_value(record, (1, 0, 1, 0)) == 3


@pytest.mark.parametrize(
    ("bitstring", "message"),
    [
        ((0, 1), "length"),
        ((0, 1, 0, 1), "length"),
        ((0, 2, 1), "entry 1"),
        ((0, -1, 1), "entry 1"),
        (("0", "1", "0"), "entry 0"),
        ((False, True, False), "entry 0"),
    ],
)
def test_cut_value_rejects_invalid_bitstrings(
    bitstring: tuple[object, ...], message: str
) -> None:
    record = make_record(nx.path_graph(3))

    with pytest.raises(GraphValidationError, match=message):
        cut_value(record, bitstring)  # type: ignore[arg-type]


@pytest.mark.parametrize("n_nodes", [1, 2, 3, 4, 5, 8])
def test_path_graph_optimum(n_nodes: int) -> None:
    record = make_record(nx.path_graph(n_nodes))
    result = solve_exact_maxcut(record)

    assert result.optimum == n_nodes - 1
    assert_valid_result(record, result)


@pytest.mark.parametrize(
    ("n_nodes", "expected"),
    [(3, 2), (4, 4), (5, 4), (6, 6), (7, 6)],
)
def test_cycle_graph_optimum(n_nodes: int, expected: int) -> None:
    record = make_record(nx.cycle_graph(n_nodes))
    result = solve_exact_maxcut(record)

    assert result.optimum == expected
    assert_valid_result(record, result)


@pytest.mark.parametrize("n_nodes", [2, 3, 4, 5, 6])
def test_complete_graph_optimum(n_nodes: int) -> None:
    record = make_record(nx.complete_graph(n_nodes))
    result = solve_exact_maxcut(record)

    assert result.optimum == n_nodes**2 // 4
    assert_valid_result(record, result)


@pytest.mark.parametrize(("left", "right"), [(1, 3), (2, 3), (3, 3)])
def test_complete_bipartite_graph_optimum(left: int, right: int) -> None:
    record = make_record(nx.complete_bipartite_graph(left, right))
    result = solve_exact_maxcut(record)

    assert result.optimum == left * right
    assert_valid_result(record, result)


def test_edgeless_graph_counts_every_assignment_as_optimal() -> None:
    record = make_record(nx.empty_graph(4))
    result = solve_exact_maxcut(record)

    assert result.optimum == 0
    assert result.representative_bitstring == (0, 0, 0, 0)
    assert result.assignments_evaluated == 8
    assert result.n_optimal_assignments == 16
    assert_valid_result(record, result)


def test_single_vertex_graph() -> None:
    record = make_record(nx.empty_graph(1))
    result = solve_exact_maxcut(record)

    assert result.optimum == 0
    assert result.representative_bitstring == (0,)
    assert result.assignments_evaluated == 1
    assert result.n_optimal_assignments == 2


def test_triangle_optimum_assignment_count() -> None:
    record = make_record(nx.complete_graph(3))
    result = solve_exact_maxcut(record)

    assert result.optimum == 2
    assert result.n_optimal_assignments == 6


@pytest.mark.parametrize("seed", range(10))
def test_symmetry_reduced_solver_matches_full_enumeration(seed: int) -> None:
    record = make_record(nx.gnp_random_graph(7, 0.4, seed=seed))

    assert solve_exact_maxcut(record).optimum == naive_full_maxcut(record)


def test_solver_rejects_graph_over_configured_size_limit() -> None:
    record = make_record(nx.path_graph(11))

    with pytest.raises(ExactSolverSizeError, match="configured exact-solver limit"):
        solve_exact_maxcut(record, max_nodes=10)


@pytest.mark.parametrize("max_nodes", [0, -1, True, 4.5])
def test_solver_rejects_invalid_size_limit(max_nodes: object) -> None:
    record = make_record(nx.path_graph(2))

    with pytest.raises(ValueError, match="positive integer"):
        solve_exact_maxcut(record, max_nodes=max_nodes)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"graph_id": "not-a-hash"},
        {"optimum": -1},
        {"representative_bitstring": ()},
        {"representative_bitstring": (1, 0)},
        {"representative_bitstring": (0, 2)},
        {"n_optimal_assignments": 0},
        {"assignments_evaluated": 0},
        {"solver": "unknown"},
        {"solver_version": "99"},
    ],
)
def test_result_rejects_invalid_fields(overrides: dict[str, object]) -> None:
    record = make_record(nx.path_graph(2))
    fields: dict[str, object] = {
        "graph_id": record.graph_id,
        "optimum": 1,
        "representative_bitstring": (0, 1),
        "n_optimal_assignments": 2,
        "assignments_evaluated": 2,
        "solver": EXACT_MAXCUT_SOLVER,
        "solver_version": EXACT_MAXCUT_SOLVER_VERSION,
    }
    fields.update(overrides)

    with pytest.raises(ValueError):
        ExactMaxCutResult(**fields)  # type: ignore[arg-type]
