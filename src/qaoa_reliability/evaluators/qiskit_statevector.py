"""Exact QAOA statevector evaluation through Qiskit 2.x."""

from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import version

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector

from qaoa_reliability.evaluators.base import (
    EvaluationResult,
    EvaluationValidationError,
    compute_evaluation_id,
    validate_evaluation_request,
)
from qaoa_reliability.graphs.schema import GraphRecord

QISKIT_EVALUATOR_NAME = "qiskit_statevector"
QISKIT_EVALUATOR_VERSION = "1.0"
DEFAULT_MAX_STATEVECTOR_QUBITS = 20
IMAGINARY_TOLERANCE = 1e-12


def _build_maxcut_observable(graph: GraphRecord) -> SparsePauliOp:
    """Build sum_(u,v) (I - Z_u Z_v) / 2 in sparse Pauli form."""

    if not graph.edges:
        return SparsePauliOp.from_sparse_list(
            [("I", [0], 0.0)],
            num_qubits=graph.n_nodes,
        )

    terms: list[tuple[str, list[int], float]] = []
    for u, v in graph.edges:
        terms.append(("II", [u, v], 0.5))
        terms.append(("ZZ", [u, v], -0.5))
    return SparsePauliOp.from_sparse_list(
        terms,
        num_qubits=graph.n_nodes,
    ).simplify()


def _build_qaoa_circuit(
    graph: GraphRecord,
    depth: int,
    parameters: tuple[float, ...],
) -> QuantumCircuit:
    """Build the circuit using the benchmark's explicit sign conventions."""

    gammas = parameters[:depth]
    betas = parameters[depth:]
    circuit = QuantumCircuit(graph.n_nodes)
    circuit.h(range(graph.n_nodes))

    for gamma, beta in zip(gammas, betas, strict=True):
        # RZZ(theta) = exp(-i theta ZZ / 2).  Using -gamma implements
        # exp(+i gamma ZZ / 2), equal to exp(-i gamma (I-ZZ)/2)
        # up to an objective-irrelevant global phase.
        for u, v in graph.edges:
            circuit.rzz(-gamma, u, v)
        # RX(theta) = exp(-i theta X / 2), so theta=2*beta implements U_B.
        for qubit in range(graph.n_nodes):
            circuit.rx(2.0 * beta, qubit)

    return circuit


class QiskitStatevectorEvaluator:
    """Evaluate exact unweighted-MaxCut QAOA expectations with Qiskit."""

    evaluator_name = QISKIT_EVALUATOR_NAME
    evaluator_version = QISKIT_EVALUATOR_VERSION

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

        circuit = _build_qaoa_circuit(graph, depth, theta)
        observable = _build_maxcut_observable(graph)
        state = Statevector.from_instruction(circuit)
        raw_objective = state.expectation_value(observable)
        imaginary = float(np.imag(raw_objective))
        if abs(imaginary) > IMAGINARY_TOLERANCE:
            raise RuntimeError(
                f"Qiskit returned a non-negligible imaginary expectation: {imaginary}"
            )
        objective = float(np.real(raw_objective))
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
                "qiskit_version": version("qiskit"),
                "numpy_version": version("numpy"),
                "simulation_method": "Statevector.from_instruction",
                "statevector_qubit_order": "little_endian_vertex_index",
                "objective_convention": "positive_expected_cut_value",
            },
        )
