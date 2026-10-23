"""Independent NumPy/Qiskit cross-validation for p=1 and p=2."""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest

pytest.importorskip("qiskit")

from qaoa_reliability.evaluators import NumpyStatevectorEvaluator  # noqa: E402
from qaoa_reliability.evaluators.qiskit_statevector import (  # noqa: E402
    QiskitStatevectorEvaluator,
)
from qaoa_reliability.graphs.generators import generate_graph  # noqa: E402
from qaoa_reliability.graphs.schema import (  # noqa: E402
    GraphGenerationSpec,
    GraphRecord,
    from_networkx,
)

CROSS_ADAPTER_ABS_TOLERANCE = 1e-10


def _p1_specs() -> list[GraphGenerationSpec]:
    specs: list[GraphGenerationSpec] = []
    for seed in range(5):
        specs.extend(
            [
                GraphGenerationSpec(
                    "erdos_renyi",
                    6,
                    100 + seed,
                    {"edge_probability": 0.55},
                ),
                GraphGenerationSpec(
                    "random_regular",
                    6,
                    200 + seed,
                    {"degree": 3},
                ),
                GraphGenerationSpec(
                    "watts_strogatz",
                    6,
                    300 + seed,
                    {"neighborhood_size": 2, "rewiring_probability": 0.3},
                ),
                GraphGenerationSpec(
                    "stochastic_block_model",
                    6,
                    400 + seed,
                    {
                        "block_sizes": [3, 3],
                        "probability_matrix": [[0.8, 0.25], [0.25, 0.8]],
                    },
                ),
            ]
        )
    return specs


P1_SPECS = _p1_specs()
P1_RNG = np.random.default_rng(20261012)
P1_PARAMETERS = [
    (
        float(P1_RNG.uniform(0.0, 2.0 * np.pi)),
        float(P1_RNG.uniform(0.0, np.pi)),
    )
    for _ in P1_SPECS
]


@pytest.mark.parametrize(
    ("spec", "parameters"),
    list(zip(P1_SPECS, P1_PARAMETERS, strict=True)),
    ids=[f"{spec.family}-{spec.seed}" for spec in P1_SPECS],
)
def test_p1_cross_adapter_agreement(
    spec: GraphGenerationSpec,
    parameters: tuple[float, float],
) -> None:
    graph = generate_graph(spec)
    numpy_result = NumpyStatevectorEvaluator().evaluate(graph, 1, parameters)
    qiskit_result = QiskitStatevectorEvaluator().evaluate(graph, 1, parameters)

    assert qiskit_result.graph_id == numpy_result.graph_id
    assert qiskit_result.depth == numpy_result.depth
    assert qiskit_result.parameters == numpy_result.parameters
    assert qiskit_result.evaluation_id != numpy_result.evaluation_id
    assert qiskit_result.objective == pytest.approx(
        numpy_result.objective,
        abs=CROSS_ADAPTER_ABS_TOLERANCE,
        rel=0.0,
    )


def _p2_graphs() -> list[GraphRecord]:
    generated = generate_graph(
        GraphGenerationSpec(
            "erdos_renyi",
            6,
            20261012,
            {"edge_probability": 0.5},
        )
    )
    fixtures = [
        nx.path_graph(2),
        nx.path_graph(3),
        nx.complete_graph(3),
        nx.cycle_graph(4),
    ]
    return [
        *(from_networkx(graph, family="fixture", seed=None) for graph in fixtures),
        generated,
    ]


P2_GRAPHS = _p2_graphs()
P2_PARAMETERS = (
    (0.0, 0.0, 0.0, 0.0),
    (0.1, 0.2, 0.3, 0.4),
    (math.pi / 4, math.pi / 7, math.pi / 8, math.pi / 6),
)


@pytest.mark.parametrize(
    "graph",
    P2_GRAPHS,
    ids=("edge", "path-3", "triangle", "cycle-4", "generated-er"),
)
@pytest.mark.parametrize(
    "parameters",
    P2_PARAMETERS,
    ids=("zeros", "generic", "fractional-pi"),
)
def test_p2_cross_adapter_agreement(
    graph: GraphRecord,
    parameters: tuple[float, float, float, float],
) -> None:
    numpy_result = NumpyStatevectorEvaluator().evaluate(graph, 2, parameters)
    qiskit_result = QiskitStatevectorEvaluator().evaluate(graph, 2, parameters)
    assert qiskit_result.objective == pytest.approx(
        numpy_result.objective,
        abs=CROSS_ADAPTER_ABS_TOLERANCE,
        rel=0.0,
    )


@pytest.mark.parametrize(
    "evaluator",
    (NumpyStatevectorEvaluator(), QiskitStatevectorEvaluator()),
    ids=("numpy", "qiskit"),
)
def test_zero_second_layer_reduces_to_p1(evaluator) -> None:
    graph = from_networkx(nx.path_graph(4), family="fixture", seed=None)
    gamma = 0.41
    beta = 0.29
    p1 = evaluator.evaluate(graph, 1, (gamma, beta))
    p2 = evaluator.evaluate(graph, 2, (gamma, 0.0, beta, 0.0))
    assert p2.objective == pytest.approx(
        p1.objective,
        abs=CROSS_ADAPTER_ABS_TOLERANCE,
        rel=0.0,
    )
