"""Tests for canonical graph validation and identity."""

import math

import networkx as nx
import pytest

from qaoa_reliability.graphs.schema import (
    SCHEMA_VERSION,
    GraphGenerationSpec,
    GraphIntegrityError,
    GraphRecord,
    GraphValidationError,
    canonical_identity_payload,
    canonicalize_edges,
    compute_graph_id,
    from_networkx,
    to_networkx,
)


def test_generation_spec_is_a_defensive_validated_recipe() -> None:
    parameters = {"p": 0.4, "blocks": [4, 4]}
    spec = GraphGenerationSpec("erdos_renyi", 8, 42, parameters)

    parameters["p"] = 0.9
    parameters["blocks"].append(2)

    assert spec.family == "erdos_renyi"
    assert spec.n_nodes == 8
    assert spec.seed == 42
    assert spec.parameters == {"p": 0.4, "blocks": [4, 4]}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"family": "", "n_nodes": 8, "seed": 1}, "family"),
        ({"family": "er", "n_nodes": 0, "seed": 1}, "positive"),
        ({"family": "er", "n_nodes": 8, "seed": True}, "seed"),
        (
            {
                "family": "er",
                "n_nodes": 8,
                "seed": 1,
                "parameters": {"p": math.nan},
            },
            "NaN",
        ),
    ],
)
def test_generation_spec_rejects_invalid_input(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(GraphValidationError, match=message):
        GraphGenerationSpec(**kwargs)  # type: ignore[arg-type]


def test_edges_are_oriented_and_sorted() -> None:
    assert canonicalize_edges(4, [(3, 1), (2, 0), (2, 3)]) == (
        (0, 2),
        (1, 3),
        (2, 3),
    )


@pytest.mark.parametrize(
    ("n_nodes", "edges", "message"),
    [
        (3, [(0, 0)], "self-loop"),
        (3, [(0, 1), (1, 0)], "duplicate"),
        (3, [(0, 3)], "outside"),
        (3, [(0, "1")], "integers"),
        (-1, [], "non-negative"),
    ],
)
def test_invalid_edges_are_rejected(
    n_nodes: int, edges: list[tuple[object, object]], message: str
) -> None:
    with pytest.raises(GraphValidationError, match=message):
        canonicalize_edges(n_nodes, edges)  # type: ignore[arg-type]


def test_identity_ignores_edge_order_and_provenance() -> None:
    first = GraphRecord.from_topology(
        family="fixture_a",
        n_nodes=4,
        edges=[(2, 0), (1, 0)],
        generation_seed=1,
        generation_parameters={"note": "first"},
    )
    second = GraphRecord.from_topology(
        family="fixture_b",
        n_nodes=4,
        edges=[(0, 1), (0, 2)],
        generation_seed=999,
        generation_parameters={"note": "second"},
    )

    assert first.graph_id == second.graph_id
    assert first.edges == second.edges == ((0, 1), (0, 2))


def test_identity_changes_with_topology_or_isolated_node_count() -> None:
    base = compute_graph_id(3, [(0, 1)])

    assert compute_graph_id(3, [(0, 2)]) != base
    assert compute_graph_id(4, [(0, 1)]) != base


def test_identity_payload_is_json_ready_and_versioned() -> None:
    assert canonical_identity_payload(3, [(2, 0), (0, 1)]) == {
        "identity_version": "graph-identity-v1",
        "n_nodes": 3,
        "edges": [[0, 1], [0, 2]],
    }


def test_graph_id_contract_has_a_fixed_reference_value() -> None:
    assert compute_graph_id(3, [(0, 1), (0, 2)]) == (
        "sha256:8d5db3cf3dee57b5cb0f20773b632a088466c9d1f59d0e49cf036ebb061b9791"
    )


def test_record_rejects_a_stale_graph_id() -> None:
    with pytest.raises(GraphIntegrityError, match="does not match"):
        GraphRecord(
            schema_version=SCHEMA_VERSION,
            graph_id="sha256:not-the-real-id",
            family="fixture",
            n_nodes=2,
            edges=((0, 1),),
            generation_seed=None,
        )


def test_networkx_round_trip_preserves_isolated_nodes() -> None:
    graph = nx.Graph()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(2, 1), (1, 0)])

    record = from_networkx(
        graph,
        family="fixture_path_with_isolate",
        seed=None,
        parameters={"purpose": "test"},
    )
    restored = to_networkx(record)

    assert set(restored.nodes) == {0, 1, 2, 3}
    assert set(restored.edges) == {(0, 1), (1, 2)}
    assert record.edges == ((0, 1), (1, 2))


@pytest.mark.parametrize(
    "graph",
    [nx.DiGraph([(0, 1)]), nx.MultiGraph([(0, 1)])],
)
def test_networkx_conversion_rejects_unsupported_graph_types(
    graph: nx.Graph,
) -> None:
    with pytest.raises(GraphValidationError):
        from_networkx(graph, family="invalid", seed=None)


def test_networkx_conversion_rejects_nonconsecutive_labels() -> None:
    graph = nx.Graph([(1, 2)])

    with pytest.raises(GraphValidationError, match="consecutive integers"):
        from_networkx(graph, family="invalid", seed=None)
