"""Lightweight exact QAOA statevector evaluator implemented with NumPy."""

from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import version

import numpy as np
from numpy.typing import NDArray

from qaoa_reliability.evaluators.base import (
    EvaluationResult,
    EvaluationValidationError,
    compute_evaluation_id,
    validate_evaluation_request,
)
from qaoa_reliability.graphs.schema import GraphRecord

NUMPY_EVALUATOR_NAME = "numpy_statevector"
NUMPY_EVALUATOR_VERSION = "1.0"
DEFAULT_MAX_STATEVECTOR_QUBITS = 20


def _cut_values(graph: GraphRecord) -> NDArray[np.float64]:
    """Return C_G(z) for every little-endian computational-basis index."""

    basis = np.arange(1 << graph.n_nodes, dtype=np.uint64)
    values = np.zeros(basis.size, dtype=np.float64)
    for u, v in graph.edges:
        values += ((basis >> u) & 1) != ((basis >> v) & 1)
    return values


def _apply_mixer(
    state: NDArray[np.complex128],
    *,
    beta: float,
    n_qubits: int,
) -> None:
    """Apply exp(-i beta sum X_i) to a statevector in place."""

    cosine = np.cos(beta)
    minus_i_sine = -1j * np.sin(beta)
    for qubit in range(n_qubits):
        stride = 1 << qubit
        for block_start in range(0, state.size, 2 * stride):
            zero_indices = slice(block_start, block_start + stride)
            one_indices = slice(block_start + stride, block_start + 2 * stride)
            zero = state[zero_indices].copy()
            one = state[one_indices].copy()
            state[zero_indices] = cosine * zero + minus_i_sine * one
            state[one_indices] = minus_i_sine * zero + cosine * one


class NumpyStatevectorEvaluator:
    """Evaluate exact unweighted-MaxCut QAOA expectations on a CPU."""

    evaluator_name = NUMPY_EVALUATOR_NAME
    evaluator_version = NUMPY_EVALUATOR_VERSION

    def __init__(
        self,
        *,
        max_qubits: int = DEFAULT_MAX_STATEVECTOR_QUBITS,
    ) -> None:
        if (
            isinstance(max_qubits, bool)
            or not isinstance(max_qubits, int)
            or max_qubits < 1
        ):
            raise ValueError("max_qubits must be a positive integer")
        self.max_qubits = max_qubits

    def evaluate(
        self,
        graph: GraphRecord,
        depth: int,
        parameters: Sequence[float],
    ) -> EvaluationResult:
        """Return the positive expected cut value for one complete request."""

        theta = validate_evaluation_request(graph, depth, parameters)
        if graph.n_nodes > self.max_qubits:
            raise EvaluationValidationError(
                f"graph has {graph.n_nodes} nodes; evaluator limit is {self.max_qubits}"
            )

        gammas = theta[:depth]
        betas = theta[depth:]
        dimension = 1 << graph.n_nodes
        state = np.full(
            dimension,
            1.0 / np.sqrt(dimension),
            dtype=np.complex128,
        )
        costs = _cut_values(graph)

        # One QAOA layer is U_B(beta_j) U_C(gamma_j): cost acts first.
        for gamma, beta in zip(gammas, betas, strict=True):
            state *= np.exp(-1j * gamma * costs)
            _apply_mixer(state, beta=beta, n_qubits=graph.n_nodes)

        probabilities = np.abs(state) ** 2
        objective = float(np.dot(probabilities, costs))
        # Remove harmless floating-point excursions at the physical boundaries.
        if abs(objective) < 1e-14:
            objective = 0.0
        if abs(objective - len(graph.edges)) < 1e-14:
            objective = float(len(graph.edges))

        evaluation_id = compute_evaluation_id(
            graph_id=graph.graph_id,
            depth=depth,
            parameters=theta,
            evaluator=self.evaluator_name,
            evaluator_version=self.evaluator_version,
        )
        return EvaluationResult(
            graph_id=graph.graph_id,
            depth=depth,
            parameters=theta,
            objective=objective,
            evaluator=self.evaluator_name,
            evaluator_version=self.evaluator_version,
            evaluation_id=evaluation_id,
            metadata={
                "numpy_version": version("numpy"),
                "statevector_qubit_order": "little_endian_vertex_index",
                "objective_convention": "positive_expected_cut_value",
            },
        )
