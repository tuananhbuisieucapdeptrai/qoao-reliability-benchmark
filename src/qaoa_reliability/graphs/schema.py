"""Canonical graph schema and structural identity.

NetworkX remains the in-memory graph engine. This module defines the small,
portable data contract used to identify graphs and preserve their provenance.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

import networkx as nx

SCHEMA_VERSION = "1.0"
IDENTITY_VERSION = "graph-identity-v1"

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
CanonicalEdges: TypeAlias = tuple[tuple[int, int], ...]


class GraphValidationError(ValueError):
    """Raised when a graph violates the benchmark graph contract."""


class GraphSerializationError(ValueError):
    """Raised when serialized graph data is missing or malformed."""


class GraphIntegrityError(ValueError):
    """Raised when a stored graph ID does not match its topology."""


class GraphGenerationError(RuntimeError):
    """Raised when a requested valid graph cannot be generated."""


def _validate_n_nodes(n_nodes: int, *, allow_empty: bool = True) -> None:
    if isinstance(n_nodes, bool) or not isinstance(n_nodes, int):
        raise GraphValidationError("n_nodes must be an integer")
    minimum = 0 if allow_empty else 1
    if n_nodes < minimum:
        qualifier = "non-negative" if allow_empty else "positive"
        raise GraphValidationError(f"n_nodes must be {qualifier}")


def _validate_json_value(value: object, *, path: str) -> None:
    """Reject values that cannot be represented portably as strict JSON."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GraphValidationError(f"{path} must not contain NaN or infinity")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise GraphValidationError(f"{path} keys must be strings")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise GraphValidationError(
        f"{path} contains unsupported value of type {type(value).__name__}"
    )


def _copy_json_object(parameters: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    """Validate and defensively copy a JSON-compatible mapping."""

    if not isinstance(parameters, Mapping):
        raise GraphValidationError("generation_parameters must be a mapping")
    copied = dict(parameters)
    _validate_json_value(copied, path="generation_parameters")
    # The JSON round trip also copies nested mutable lists and dictionaries.
    return json.loads(json.dumps(copied, allow_nan=False))


@dataclass(frozen=True)
class GraphGenerationSpec:
    """A reproducible request for one graph generator.

    The spec says how to request a graph. It does not contain the generated
    topology; that belongs in :class:`GraphRecord`.
    """

    family: str
    n_nodes: int
    seed: int
    parameters: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.family, str) or not self.family.strip():
            raise GraphValidationError("family must be a non-empty string")
        _validate_n_nodes(self.n_nodes, allow_empty=False)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise GraphValidationError("seed must be an integer")
        object.__setattr__(self, "family", self.family.strip())
        object.__setattr__(self, "parameters", _copy_json_object(self.parameters))


def canonicalize_edges(
    n_nodes: int,
    edges: Iterable[tuple[int, int]],
) -> CanonicalEdges:
    """Validate and sort the edges of a simple undirected labeled graph.

    Every edge is oriented as ``(min(u, v), max(u, v))``. Duplicate
    undirected edges are rejected rather than silently discarded.
    """

    _validate_n_nodes(n_nodes)
    canonical: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    try:
        iterator = iter(edges)
    except TypeError as error:
        raise GraphValidationError(
            "edges must be an iterable of endpoint pairs"
        ) from error

    for index, edge in enumerate(iterator):
        try:
            endpoints = tuple(edge)
        except TypeError as error:
            raise GraphValidationError(
                f"edge {index} must contain two endpoints"
            ) from error
        if len(endpoints) != 2:
            raise GraphValidationError(
                f"edge {index} must contain exactly two endpoints"
            )

        u, v = endpoints
        if (
            isinstance(u, bool)
            or isinstance(v, bool)
            or not isinstance(u, int)
            or not isinstance(v, int)
        ):
            raise GraphValidationError(f"edge {index} endpoints must be integers")
        if not 0 <= u < n_nodes or not 0 <= v < n_nodes:
            raise GraphValidationError(
                f"edge {index} endpoint is outside the range 0..{n_nodes - 1}"
            )
        if u == v:
            raise GraphValidationError(f"self-loop ({u}, {v}) is not allowed")

        normalized = (min(u, v), max(u, v))
        if normalized in seen:
            raise GraphValidationError(f"duplicate undirected edge {normalized}")
        seen.add(normalized)
        canonical.append(normalized)

    return tuple(sorted(canonical))


def canonical_identity_payload(
    n_nodes: int,
    edges: Iterable[tuple[int, int]],
) -> dict[str, JSONValue]:
    """Return the minimal, versioned payload that defines graph identity."""

    canonical_edges = canonicalize_edges(n_nodes, edges)
    return {
        "identity_version": IDENTITY_VERSION,
        "n_nodes": n_nodes,
        "edges": [[u, v] for u, v in canonical_edges],
    }


def compute_graph_id(
    n_nodes: int,
    edges: Iterable[tuple[int, int]],
) -> str:
    """Compute a stable SHA-256 ID for normalized labeled topology."""

    payload = canonical_identity_payload(n_nodes, edges)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class GraphRecord:
    """Canonical graph topology plus the provenance used to create it.

    ``graph_id`` identifies normalized labeled topology. It is not an
    isomorphism-canonical identifier, so relabeling vertices may change it.
    """

    schema_version: str
    graph_id: str
    family: str
    n_nodes: int
    edges: CanonicalEdges
    generation_seed: int | None
    generation_parameters: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise GraphValidationError(
                f"unsupported schema_version {self.schema_version!r}; "
                f"expected {SCHEMA_VERSION!r}"
            )
        if not isinstance(self.family, str) or not self.family.strip():
            raise GraphValidationError("family must be a non-empty string")
        if self.generation_seed is not None and (
            isinstance(self.generation_seed, bool)
            or not isinstance(self.generation_seed, int)
        ):
            raise GraphValidationError("generation_seed must be an integer or None")

        canonical_edges = canonicalize_edges(self.n_nodes, self.edges)
        expected_id = compute_graph_id(self.n_nodes, canonical_edges)
        if self.graph_id != expected_id:
            raise GraphIntegrityError(
                f"graph_id does not match topology: expected {expected_id!r}"
            )

        object.__setattr__(self, "family", self.family.strip())
        object.__setattr__(self, "edges", canonical_edges)
        object.__setattr__(
            self,
            "generation_parameters",
            _copy_json_object(self.generation_parameters),
        )

    @classmethod
    def from_topology(
        cls,
        *,
        family: str,
        n_nodes: int,
        edges: Iterable[tuple[int, int]],
        generation_seed: int | None,
        generation_parameters: Mapping[str, JSONValue] | None = None,
    ) -> GraphRecord:
        """Construct a valid record while computing its structural ID."""

        canonical_edges = canonicalize_edges(n_nodes, edges)
        return cls(
            schema_version=SCHEMA_VERSION,
            graph_id=compute_graph_id(n_nodes, canonical_edges),
            family=family,
            n_nodes=n_nodes,
            edges=canonical_edges,
            generation_seed=generation_seed,
            generation_parameters=dict(generation_parameters or {}),
        )


def from_networkx(
    graph: nx.Graph,
    *,
    family: str,
    seed: int | None,
    parameters: Mapping[str, JSONValue] | None = None,
) -> GraphRecord:
    """Convert a simple NetworkX graph with nodes ``0..n-1`` to a record."""

    if graph.is_directed():
        raise GraphValidationError("directed graphs are not supported")
    if graph.is_multigraph():
        raise GraphValidationError("multigraphs are not supported")

    n_nodes = graph.number_of_nodes()
    if set(graph.nodes) != set(range(n_nodes)):
        raise GraphValidationError(
            "graph nodes must be consecutive integers from 0 to n_nodes - 1"
        )

    return GraphRecord.from_topology(
        family=family,
        n_nodes=n_nodes,
        edges=graph.edges,
        generation_seed=seed,
        generation_parameters=parameters,
    )


def to_networkx(record: GraphRecord) -> nx.Graph:
    """Reconstruct a NetworkX graph, preserving isolated vertices."""

    graph = nx.Graph()
    graph.add_nodes_from(range(record.n_nodes))
    graph.add_edges_from(record.edges)
    return graph
