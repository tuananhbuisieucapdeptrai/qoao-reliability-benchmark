"""Tests for baseline graph-feature extraction."""

from __future__ import annotations

import math

import networkx as nx
import pytest

from qaoa_reliability.features.graph_features import (
    FEATURE_SCHEMA_VERSION,
    GraphFeatureRecord,
    extract_graph_features,
)
from qaoa_reliability.graphs.generators import generate_graph
from qaoa_reliability.graphs.schema import (
    GraphGenerationSpec,
    GraphRecord,
    GraphValidationError,
    from_networkx,
)


def make_record(graph: nx.Graph) -> GraphRecord:
    return from_networkx(
        graph,
        family="test_fixture",
        seed=None,
        parameters={"purpose": "feature test"},
    )


def test_complete_graph_features() -> None:
    features = extract_graph_features(make_record(nx.complete_graph(4)))

    assert features.n_nodes == 4
    assert features.n_edges == 6
    assert features.density == pytest.approx(1.0)
    assert features.degree_mean == pytest.approx(3.0)
    assert features.degree_std == pytest.approx(0.0)
    assert features.degree_min == 3
    assert features.degree_max == 3
    assert features.triangle_count == 4
    assert features.average_clustering == pytest.approx(1.0)
    assert features.degree_assortativity is None
    assert features.is_connected
    assert features.n_connected_components == 1
    assert features.diameter == 1


def test_path_graph_features() -> None:
    features = extract_graph_features(make_record(nx.path_graph(4)))

    assert features.n_edges == 3
    assert features.density == pytest.approx(0.5)
    assert features.degree_mean == pytest.approx(1.5)
    assert features.degree_std == pytest.approx(0.5)
    assert features.degree_min == 1
    assert features.degree_max == 2
    assert features.triangle_count == 0
    assert features.average_clustering == pytest.approx(0.0)
    assert features.diameter == 3


def test_cycle_graph_features() -> None:
    features = extract_graph_features(make_record(nx.cycle_graph(4)))

    assert features.n_edges == 4
    assert features.density == pytest.approx(2 / 3)
    assert features.degree_mean == pytest.approx(2.0)
    assert features.degree_std == pytest.approx(0.0)
    assert features.degree_min == 2
    assert features.degree_max == 2
    assert features.triangle_count == 0
    assert features.average_clustering == pytest.approx(0.0)
    assert features.degree_assortativity is None
    assert features.diameter == 2


def test_star_graph_features() -> None:
    features = extract_graph_features(make_record(nx.star_graph(3)))

    assert features.n_edges == 3
    assert features.density == pytest.approx(0.5)
    assert features.degree_mean == pytest.approx(1.5)
    assert features.degree_std == pytest.approx(math.sqrt(0.75))
    assert features.degree_min == 1
    assert features.degree_max == 3
    assert features.triangle_count == 0
    assert features.average_clustering == pytest.approx(0.0)
    assert features.degree_assortativity == pytest.approx(-1.0)
    assert features.diameter == 2


def test_disconnected_graph_has_explicit_missing_diameter() -> None:
    graph = nx.Graph()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(0, 1), (2, 3)])

    features = extract_graph_features(make_record(graph))

    assert not features.is_connected
    assert features.n_connected_components == 2
    assert features.diameter is None


def test_single_vertex_features() -> None:
    features = extract_graph_features(make_record(nx.empty_graph(1)))

    assert features.n_nodes == 1
    assert features.n_edges == 0
    assert features.density == pytest.approx(0.0)
    assert features.degree_mean == pytest.approx(0.0)
    assert features.degree_std == pytest.approx(0.0)
    assert features.degree_min == 0
    assert features.degree_max == 0
    assert features.degree_assortativity is None
    assert features.diameter == 0


def test_feature_row_is_flat_and_detached() -> None:
    features = extract_graph_features(make_record(nx.path_graph(3)))
    row = features.to_dict()

    assert row["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert row["graph_id"] == features.graph_id
    assert all(not isinstance(value, (dict, list, tuple)) for value in row.values())


@pytest.mark.parametrize(
    "spec",
    [
        GraphGenerationSpec("erdos_renyi", 8, 42, {"edge_probability": 0.4}),
        GraphGenerationSpec("random_regular", 8, 42, {"degree": 3}),
        GraphGenerationSpec(
            "watts_strogatz",
            8,
            42,
            {"neighborhood_size": 4, "rewiring_probability": 0.25},
        ),
        GraphGenerationSpec(
            "stochastic_block_model",
            8,
            42,
            {
                "block_sizes": [4, 4],
                "probability_matrix": [[0.8, 0.2], [0.2, 0.8]],
            },
        ),
    ],
)
def test_generated_graph_feature_invariants(spec: GraphGenerationSpec) -> None:
    record = generate_graph(spec)
    features = extract_graph_features(record)

    assert features.graph_id == record.graph_id
    assert features.family == record.family
    assert features.n_nodes == record.n_nodes
    assert features.n_edges == len(record.edges)
    assert features.degree_mean == pytest.approx(
        2 * features.n_edges / features.n_nodes
    )
    assert 0.0 <= features.density <= 1.0
    assert 0.0 <= features.average_clustering <= 1.0


def test_empty_graph_record_is_rejected() -> None:
    record = GraphRecord.from_topology(
        family="empty",
        n_nodes=0,
        edges=[],
        generation_seed=None,
    )

    with pytest.raises(GraphValidationError, match="at least one node"):
        extract_graph_features(record)


def test_feature_record_rejects_inconsistent_connectivity() -> None:
    record = make_record(nx.path_graph(2))

    with pytest.raises(ValueError, match="connectivity fields are inconsistent"):
        GraphFeatureRecord(
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            graph_id=record.graph_id,
            family=record.family,
            n_nodes=2,
            n_edges=1,
            density=1.0,
            degree_mean=1.0,
            degree_std=0.0,
            degree_min=1,
            degree_max=1,
            triangle_count=0,
            average_clustering=0.0,
            degree_assortativity=None,
            is_connected=False,
            n_connected_components=1,
            diameter=None,
        )
