"""Exact unweighted-MaxCut reference solver."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product

from qaoa_reliability.graphs.schema import GraphRecord, GraphValidationError

EXACT_MAXCUT_SOLVER = "exhaustive-symmetry-reduced"
EXACT_MAXCUT_SOLVER_VERSION = "1.0"
DEFAULT_MAX_EXACT_NODES = 20


class ExactSolverSizeError(ValueError):
    """Raised when a graph exceeds the configured exhaustive-search limit."""


@dataclass(frozen=True)
class ExactMaxCutResult:
    """Exact MaxCut ground truth for one canonical graph.

    ``n_optimal_assignments`` counts assignments in the full bitstring space,
    including complementary assignments. The solver itself evaluates only the
    half-space in which vertex zero is assigned bit zero.
    """

    graph_id: str
    optimum: int
    representative_bitstring: tuple[int, ...]
    n_optimal_assignments: int
    assignments_evaluated: int
    solver: str = EXACT_MAXCUT_SOLVER
    solver_version: str = EXACT_MAXCUT_SOLVER_VERSION

    def __post_init__(self) -> None:
        prefix = "sha256:"
        digest = self.graph_id.removeprefix(prefix)
        if (
            not isinstance(self.graph_id, str)
            or not self.graph_id.startswith(prefix)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("graph_id must be a lowercase SHA-256 identifier")
        if isinstance(self.optimum, bool) or not isinstance(self.optimum, int):
            raise ValueError("optimum must be an integer")
        if self.optimum < 0:
            raise ValueError("optimum must be non-negative")
        if (
            isinstance(self.assignments_evaluated, bool)
            or not isinstance(self.assignments_evaluated, int)
            or self.assignments_evaluated < 1
        ):
            raise ValueError("assignments_evaluated must be a positive integer")
        if (
            isinstance(self.n_optimal_assignments, bool)
            or not isinstance(self.n_optimal_assignments, int)
            or self.n_optimal_assignments < 1
        ):
            raise ValueError("n_optimal_assignments must be a positive integer")
        if not self.representative_bitstring:
            raise ValueError("representative_bitstring must not be empty")
        if any(
            isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1)
            for bit in self.representative_bitstring
        ):
            raise ValueError("representative_bitstring must contain integer bits")
        if self.representative_bitstring[0] != 0:
            raise ValueError("representative_bitstring must fix vertex zero to zero")
        if self.solver != EXACT_MAXCUT_SOLVER:
            raise ValueError(f"solver must be {EXACT_MAXCUT_SOLVER!r}")
        if self.solver_version != EXACT_MAXCUT_SOLVER_VERSION:
            raise ValueError(f"solver_version must be {EXACT_MAXCUT_SOLVER_VERSION!r}")


def cut_value(record: GraphRecord, bitstring: Sequence[int]) -> int:
    """Return the number of graph edges crossing a proposed bipartition.

    Bitstring position ``i`` corresponds to graph vertex ``i``. Values must be
    the integers zero or one; Booleans are rejected to keep serialized results
    unambiguous.
    """

    try:
        bits = tuple(bitstring)
    except TypeError as error:
        raise GraphValidationError("bitstring must be a sequence of bits") from error

    if len(bits) != record.n_nodes:
        raise GraphValidationError(
            "bitstring length must equal the graph's number of nodes"
        )

    for index, bit in enumerate(bits):
        if isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1):
            raise GraphValidationError(
                f"bitstring entry {index} must be integer 0 or 1"
            )

    return sum(1 for u, v in record.edges if bits[u] != bits[v])


def solve_exact_maxcut(
    record: GraphRecord,
    *,
    max_nodes: int = DEFAULT_MAX_EXACT_NODES,
) -> ExactMaxCutResult:
    """Solve unweighted MaxCut by exhaustive symmetry-reduced enumeration.

    Complementary bitstrings define the same cut, so vertex zero is fixed to
    zero and only ``2 ** (n_nodes - 1)`` assignments are evaluated. The
    representative is the lexicographically smallest optimal bitstring in that
    reduced search space.
    """

    if record.n_nodes < 1:
        raise GraphValidationError("exact MaxCut requires at least one node")
    if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or max_nodes < 1:
        raise ValueError("max_nodes must be a positive integer")
    if record.n_nodes > max_nodes:
        raise ExactSolverSizeError(
            f"graph has {record.n_nodes} nodes; "
            f"configured exact-solver limit is {max_nodes}"
        )

    best_value = -1
    best_bitstring: tuple[int, ...] | None = None
    reduced_optimum_count = 0
    assignments_evaluated = 0

    for remaining_bits in product((0, 1), repeat=record.n_nodes - 1):
        bitstring = (0, *remaining_bits)
        value = cut_value(record, bitstring)
        assignments_evaluated += 1

        if value > best_value:
            best_value = value
            best_bitstring = bitstring
            reduced_optimum_count = 1
        elif value == best_value:
            reduced_optimum_count += 1

    if best_bitstring is None:
        raise RuntimeError("exact enumeration produced no assignments")

    return ExactMaxCutResult(
        graph_id=record.graph_id,
        optimum=best_value,
        representative_bitstring=best_bitstring,
        n_optimal_assignments=2 * reduced_optimum_count,
        assignments_evaluated=assignments_evaluated,
    )
