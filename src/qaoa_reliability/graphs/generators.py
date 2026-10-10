"""Deterministic NetworkX graph generators for the benchmark pilot."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable

import networkx as nx

from qaoa_reliability.graphs.schema import (
    GraphGenerationError,
    GraphGenerationSpec,
    GraphRecord,
    GraphValidationError,
    JSONValue,
    from_networkx,
)

DEFAULT_MAX_ATTEMPTS = 100
SUPPORTED_FAMILIES = frozenset(
    {
        "erdos_renyi",
        "random_regular",
        "watts_strogatz",
        "stochastic_block_model",
    }
)

Generator = Callable[[GraphGenerationSpec], GraphRecord]


def _reject_unknown_parameters(
    spec: GraphGenerationSpec,
    *,
    required: set[str],
    optional: set[str],
) -> None:
    supplied = set(spec.parameters)
    missing = sorted(required - supplied)
    unknown = sorted(supplied - required - optional)
    if missing:
        raise GraphValidationError(
            f"{spec.family} is missing required parameters: {', '.join(missing)}"
        )
    if unknown:
        raise GraphValidationError(
            f"{spec.family} contains unknown parameters: {', '.join(unknown)}"
        )


def _number_parameter(spec: GraphGenerationSpec, name: str) -> float:
    value = spec.parameters[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GraphValidationError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise GraphValidationError(f"{name} must be a finite number")
    return result


def _integer_parameter(spec: GraphGenerationSpec, name: str) -> int:
    value = spec.parameters[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise GraphValidationError(f"{name} must be an integer")
    return value


def _bool_parameter(
    spec: GraphGenerationSpec,
    name: str,
    *,
    default: bool,
) -> bool:
    value = spec.parameters.get(name, default)
    if not isinstance(value, bool):
        raise GraphValidationError(f"{name} must be a boolean")
    return value


def _max_attempts(spec: GraphGenerationSpec) -> int:
    value = spec.parameters.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GraphValidationError("max_attempts must be a positive integer")
    return value


def _attempt_seed(requested_seed: int, attempt: int) -> int:
    """Derive a stable unsigned 32-bit seed without using global RNG state."""

    encoded = f"qaoa-reliability:{requested_seed}:{attempt}".encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:4], "big")


def _generate_with_connectivity_policy(
    spec: GraphGenerationSpec,
    factory: Callable[[int], nx.Graph],
) -> GraphRecord:
    require_connected = _bool_parameter(
        spec,
        "require_connected",
        default=True,
    )
    max_attempts = _max_attempts(spec)

    for attempt in range(max_attempts):
        effective_seed = _attempt_seed(spec.seed, attempt)
        graph = factory(effective_seed)
        if not require_connected or nx.is_connected(graph):
            provenance: dict[str, JSONValue] = dict(spec.parameters)
            provenance.update(
                {
                    "require_connected": require_connected,
                    "max_attempts": max_attempts,
                    "effective_seed": effective_seed,
                    "accepted_attempt": attempt,
                }
            )
            return from_networkx(
                graph,
                family=spec.family,
                seed=spec.seed,
                parameters=provenance,
            )

    raise GraphGenerationError(
        f"could not generate a connected {spec.family} graph after "
        f"{max_attempts} deterministic attempts for seed {spec.seed}"
    )


def generate_erdos_renyi(spec: GraphGenerationSpec) -> GraphRecord:
    """Generate a seeded Erdős-Rényi ``G(n, p)`` graph."""

    if spec.family != "erdos_renyi":
        raise GraphValidationError("expected family 'erdos_renyi'")
    _reject_unknown_parameters(
        spec,
        required={"edge_probability"},
        optional={"require_connected", "max_attempts"},
    )
    edge_probability = _number_parameter(spec, "edge_probability")
    if not 0.0 <= edge_probability <= 1.0:
        raise GraphValidationError("edge_probability must be in [0, 1]")

    return _generate_with_connectivity_policy(
        spec,
        lambda seed: nx.gnp_random_graph(
            n=spec.n_nodes,
            p=edge_probability,
            seed=seed,
            directed=False,
        ),
    )


def generate_random_regular(spec: GraphGenerationSpec) -> GraphRecord:
    """Generate a seeded simple random ``d``-regular graph."""

    if spec.family != "random_regular":
        raise GraphValidationError("expected family 'random_regular'")
    _reject_unknown_parameters(
        spec,
        required={"degree"},
        optional={"require_connected", "max_attempts"},
    )
    degree = _integer_parameter(spec, "degree")
    if not 0 <= degree < spec.n_nodes:
        raise GraphValidationError("degree must satisfy 0 <= degree < n_nodes")
    if spec.n_nodes * degree % 2:
        raise GraphValidationError("n_nodes * degree must be even")

    require_connected = _bool_parameter(
        spec,
        "require_connected",
        default=True,
    )
    if require_connected and spec.n_nodes > 1 and degree == 0:
        raise GraphValidationError("a zero-degree graph cannot be connected")
    if require_connected and spec.n_nodes > 2 and degree == 1:
        raise GraphValidationError(
            "a one-regular graph with more than two nodes cannot be connected"
        )

    return _generate_with_connectivity_policy(
        spec,
        lambda seed: nx.random_regular_graph(
            d=degree,
            n=spec.n_nodes,
            seed=seed,
        ),
    )


def generate_watts_strogatz(spec: GraphGenerationSpec) -> GraphRecord:
    """Generate a seeded Watts-Strogatz small-world graph."""

    if spec.family != "watts_strogatz":
        raise GraphValidationError("expected family 'watts_strogatz'")
    _reject_unknown_parameters(
        spec,
        required={"neighborhood_size", "rewiring_probability"},
        optional={"require_connected", "max_attempts"},
    )
    neighborhood_size = _integer_parameter(spec, "neighborhood_size")
    rewiring_probability = _number_parameter(spec, "rewiring_probability")
    if not 0 < neighborhood_size < spec.n_nodes:
        raise GraphValidationError(
            "neighborhood_size must satisfy 0 < neighborhood_size < n_nodes"
        )
    if neighborhood_size % 2:
        raise GraphValidationError("neighborhood_size must be even")
    if not 0.0 <= rewiring_probability <= 1.0:
        raise GraphValidationError("rewiring_probability must be in [0, 1]")

    return _generate_with_connectivity_policy(
        spec,
        lambda seed: nx.watts_strogatz_graph(
            n=spec.n_nodes,
            k=neighborhood_size,
            p=rewiring_probability,
            seed=seed,
        ),
    )


def _validate_block_model_parameters(
    spec: GraphGenerationSpec,
) -> tuple[list[int], list[list[float]]]:
    raw_sizes = spec.parameters["block_sizes"]
    if not isinstance(raw_sizes, list) or not raw_sizes:
        raise GraphValidationError("block_sizes must be a non-empty list")
    if any(
        isinstance(size, bool) or not isinstance(size, int) or size < 1
        for size in raw_sizes
    ):
        raise GraphValidationError("every block size must be a positive integer")
    block_sizes = list(raw_sizes)
    if sum(block_sizes) != spec.n_nodes:
        raise GraphValidationError("block_sizes must sum to n_nodes")

    raw_matrix = spec.parameters["probability_matrix"]
    n_blocks = len(block_sizes)
    if not isinstance(raw_matrix, list) or len(raw_matrix) != n_blocks:
        raise GraphValidationError("probability_matrix must have one row per block")

    probability_matrix: list[list[float]] = []
    for row_index, raw_row in enumerate(raw_matrix):
        if not isinstance(raw_row, list) or len(raw_row) != n_blocks:
            raise GraphValidationError("probability_matrix must be a square matrix")
        row: list[float] = []
        for column_index, raw_probability in enumerate(raw_row):
            if isinstance(raw_probability, bool) or not isinstance(
                raw_probability, (int, float)
            ):
                raise GraphValidationError(
                    "probability_matrix entries must be finite numbers"
                )
            probability = float(raw_probability)
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise GraphValidationError(
                    "probability_matrix entries must be in [0, 1]"
                )
            row.append(probability)
            if column_index < row_index and not math.isclose(
                probability,
                probability_matrix[column_index][row_index],
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise GraphValidationError("probability_matrix must be symmetric")
        probability_matrix.append(row)

    return block_sizes, probability_matrix


def generate_stochastic_block_model(spec: GraphGenerationSpec) -> GraphRecord:
    """Generate a seeded undirected stochastic-block-model graph."""

    if spec.family != "stochastic_block_model":
        raise GraphValidationError("expected family 'stochastic_block_model'")
    _reject_unknown_parameters(
        spec,
        required={"block_sizes", "probability_matrix"},
        optional={"require_connected", "max_attempts"},
    )
    block_sizes, probability_matrix = _validate_block_model_parameters(spec)

    return _generate_with_connectivity_policy(
        spec,
        lambda seed: nx.stochastic_block_model(
            sizes=block_sizes,
            p=probability_matrix,
            seed=seed,
            directed=False,
            selfloops=False,
        ),
    )


_GENERATORS: dict[str, Generator] = {
    "erdos_renyi": generate_erdos_renyi,
    "random_regular": generate_random_regular,
    "watts_strogatz": generate_watts_strogatz,
    "stochastic_block_model": generate_stochastic_block_model,
}


def generate_graph(spec: GraphGenerationSpec) -> GraphRecord:
    """Dispatch a validated generation specification to its graph family."""

    try:
        generator = _GENERATORS[spec.family]
    except KeyError as error:
        supported = ", ".join(sorted(SUPPORTED_FAMILIES))
        raise GraphValidationError(
            f"unsupported graph family {spec.family!r}; supported: {supported}"
        ) from error
    return generator(spec)
