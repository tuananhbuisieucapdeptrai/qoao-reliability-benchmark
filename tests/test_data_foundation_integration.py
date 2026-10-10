"""End-to-end quality gate for the October 10 data foundation."""

from __future__ import annotations

from pathlib import Path

import pytest

from qaoa_reliability.exact.maxcut import cut_value, solve_exact_maxcut
from qaoa_reliability.features import extract_graph_features
from qaoa_reliability.graphs.generators import generate_graph
from qaoa_reliability.graphs.schema import GraphGenerationSpec
from qaoa_reliability.graphs.serialization import (
    load_graph_record,
    save_graph_record,
)

PILOT_FIXTURES = (
    (
        GraphGenerationSpec(
            "erdos_renyi",
            8,
            42,
            {"edge_probability": 0.4},
        ),
        "sha256:ec48b7e08a23b17b1dfdb725628fe5c8f101e83a91dd9854964dcf27098fc3b4",
        7,
    ),
    (
        GraphGenerationSpec(
            "random_regular",
            8,
            42,
            {"degree": 3},
        ),
        "sha256:78afdd66ca4e41b2368c90a53cb90064094641dbe091741dca5aef55c639a6b2",
        10,
    ),
    (
        GraphGenerationSpec(
            "watts_strogatz",
            8,
            42,
            {
                "neighborhood_size": 4,
                "rewiring_probability": 0.25,
            },
        ),
        "sha256:01365da5af8866ec614c1084fdfc95e512aa059c608d24464d9ef50d63b95b93",
        12,
    ),
    (
        GraphGenerationSpec(
            "stochastic_block_model",
            8,
            42,
            {
                "block_sizes": [4, 4],
                "probability_matrix": [[0.8, 0.2], [0.2, 0.8]],
            },
        ),
        "sha256:7b33d679773aa6c64ab52559eea8570a4bf49f1cd2d54b3eea73d921d088ec41",
        9,
    ),
)


@pytest.mark.parametrize(
    ("spec", "expected_graph_id", "expected_optimum"),
    PILOT_FIXTURES,
    ids=(
        "erdos-renyi",
        "random-regular",
        "watts-strogatz",
        "stochastic-block-model",
    ),
)
def test_reproducible_graph_to_exact_result_pipeline(
    tmp_path: Path,
    spec: GraphGenerationSpec,
    expected_graph_id: str,
    expected_optimum: int,
) -> None:
    """Freeze generation, persistence, and exact-ground-truth behavior."""

    first = generate_graph(spec)
    second = generate_graph(spec)
    assert first == second
    assert first.graph_id == expected_graph_id

    path = tmp_path / f"{spec.family}.json"
    save_graph_record(first, path)
    loaded = load_graph_record(path)
    assert loaded == first

    exact = solve_exact_maxcut(loaded)
    features = extract_graph_features(loaded)
    assert exact.graph_id == loaded.graph_id
    assert exact.optimum == expected_optimum
    assert exact.assignments_evaluated == 2 ** (loaded.n_nodes - 1)
    assert cut_value(loaded, exact.representative_bitstring) == exact.optimum
    assert features.graph_id == loaded.graph_id
    assert features.n_nodes == loaded.n_nodes
    assert features.n_edges == len(loaded.edges)
