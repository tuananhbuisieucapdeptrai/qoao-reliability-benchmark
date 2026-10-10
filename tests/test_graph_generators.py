"""Tests for deterministic graph generation."""

from __future__ import annotations

import networkx as nx
import pytest

from qaoa_reliability.graphs.generators import (
    SUPPORTED_FAMILIES,
    generate_erdos_renyi,
    generate_graph,
)
from qaoa_reliability.graphs.schema import (
    GraphGenerationError,
    GraphGenerationSpec,
    GraphValidationError,
    to_networkx,
)


@pytest.mark.parametrize(
    "spec",
    [
        GraphGenerationSpec(
            "erdos_renyi",
            8,
            42,
            {"edge_probability": 0.4},
        ),
        GraphGenerationSpec(
            "random_regular",
            8,
            42,
            {"degree": 3},
        ),
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
def test_every_family_is_reproducible_and_records_provenance(
    spec: GraphGenerationSpec,
) -> None:
    first = generate_graph(spec)
    second = generate_graph(spec)

    assert first == second
    assert first.graph_id == second.graph_id
    assert first.family == spec.family
    assert first.n_nodes == spec.n_nodes
    assert first.generation_seed == spec.seed
    assert isinstance(first.generation_parameters["effective_seed"], int)
    assert isinstance(first.generation_parameters["accepted_attempt"], int)
    assert nx.is_connected(to_networkx(first))


def test_random_regular_graph_has_requested_degree() -> None:
    record = generate_graph(GraphGenerationSpec("random_regular", 10, 7, {"degree": 4}))

    assert set(dict(to_networkx(record).degree()).values()) == {4}


def test_watts_strogatz_graph_has_expected_edge_count() -> None:
    record = generate_graph(
        GraphGenerationSpec(
            "watts_strogatz",
            10,
            7,
            {"neighborhood_size": 4, "rewiring_probability": 0.3},
        )
    )

    assert len(record.edges) == 10 * 4 // 2


def test_disconnected_graph_can_be_requested_explicitly() -> None:
    record = generate_graph(
        GraphGenerationSpec(
            "erdos_renyi",
            5,
            1,
            {
                "edge_probability": 0.0,
                "require_connected": False,
            },
        )
    )

    assert record.edges == ()
    assert not nx.is_connected(to_networkx(record))


def test_connected_generation_failure_is_explicit() -> None:
    spec = GraphGenerationSpec(
        "erdos_renyi",
        5,
        1,
        {
            "edge_probability": 0.0,
            "require_connected": True,
            "max_attempts": 2,
        },
    )

    with pytest.raises(GraphGenerationError, match="after 2 deterministic attempts"):
        generate_graph(spec)


@pytest.mark.parametrize(
    "spec",
    [
        GraphGenerationSpec("erdos_renyi", 8, 1, {}),
        GraphGenerationSpec("erdos_renyi", 8, 1, {"edge_probability": 1.5}),
        GraphGenerationSpec("random_regular", 8, 1, {"degree": 9}),
        GraphGenerationSpec("random_regular", 7, 1, {"degree": 3}),
        GraphGenerationSpec(
            "watts_strogatz",
            8,
            1,
            {"neighborhood_size": 3, "rewiring_probability": 0.2},
        ),
        GraphGenerationSpec(
            "stochastic_block_model",
            8,
            1,
            {
                "block_sizes": [3, 4],
                "probability_matrix": [[0.8, 0.2], [0.2, 0.8]],
            },
        ),
        GraphGenerationSpec(
            "stochastic_block_model",
            8,
            1,
            {
                "block_sizes": [4, 4],
                "probability_matrix": [[0.8, 0.1], [0.2, 0.8]],
            },
        ),
    ],
)
def test_invalid_family_parameters_are_rejected(spec: GraphGenerationSpec) -> None:
    with pytest.raises(GraphValidationError):
        generate_graph(spec)


def test_unknown_parameters_are_rejected() -> None:
    spec = GraphGenerationSpec(
        "erdos_renyi",
        8,
        1,
        {"edge_probability": 0.4, "typo": True},
    )

    with pytest.raises(GraphValidationError, match="unknown parameters: typo"):
        generate_graph(spec)


def test_wrong_direct_generator_is_rejected() -> None:
    spec = GraphGenerationSpec("random_regular", 8, 1, {"degree": 2})

    with pytest.raises(GraphValidationError, match="expected family 'erdos_renyi'"):
        generate_erdos_renyi(spec)


def test_unsupported_family_lists_supported_names() -> None:
    spec = GraphGenerationSpec("barabasi_albert", 8, 1)

    with pytest.raises(GraphValidationError, match="unsupported graph family"):
        generate_graph(spec)

    assert SUPPORTED_FAMILIES == {
        "erdos_renyi",
        "random_regular",
        "watts_strogatz",
        "stochastic_block_model",
    }
