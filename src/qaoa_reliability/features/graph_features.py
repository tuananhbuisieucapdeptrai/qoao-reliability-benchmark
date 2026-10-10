"""Documented, table-ready graph features for the QAOA reliability pilot."""

from __future__ import annotations

import math
import warnings
from dataclasses import asdict, dataclass

import networkx as nx
import numpy as np

from qaoa_reliability.graphs.schema import (
    GraphRecord,
    GraphValidationError,
    to_networkx,
)

FEATURE_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class GraphFeatureRecord:
    """One flat row of identity, topology, and structural graph features.

    Continuous features are dimensionless except degree statistics, which are
    measured in incident edges per vertex. Diameter is measured in edges.
    Undefined assortativity and disconnected-graph diameter are stored as
    ``None`` rather than being conflated with a meaningful numerical zero.
    """

    feature_schema_version: str
    graph_id: str
    family: str
    n_nodes: int
    n_edges: int
    density: float
    degree_mean: float
    degree_std: float
    degree_min: int
    degree_max: int
    triangle_count: int
    average_clustering: float
    degree_assortativity: float | None
    is_connected: bool
    n_connected_components: int
    diameter: int | None

    def __post_init__(self) -> None:
        if self.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise ValueError(
                f"feature_schema_version must be {FEATURE_SCHEMA_VERSION!r}"
            )
        if not self.graph_id.startswith("sha256:"):
            raise ValueError("graph_id must be a SHA-256 identifier")
        if self.n_nodes < 1:
            raise ValueError("n_nodes must be positive")
        if not 0 <= self.n_edges <= self.n_nodes * (self.n_nodes - 1) // 2:
            raise ValueError("n_edges is invalid for a simple undirected graph")
        if not 0.0 <= self.density <= 1.0:
            raise ValueError("density must be in [0, 1]")
        if self.degree_min < 0 or self.degree_max >= self.n_nodes:
            raise ValueError("degree bounds are invalid")
        if self.degree_min > self.degree_max:
            raise ValueError("degree_min must not exceed degree_max")
        if self.degree_std < 0:
            raise ValueError("degree_std must be non-negative")
        if self.triangle_count < 0:
            raise ValueError("triangle_count must be non-negative")
        if not 0.0 <= self.average_clustering <= 1.0:
            raise ValueError("average_clustering must be in [0, 1]")
        if self.degree_assortativity is not None and not math.isfinite(
            self.degree_assortativity
        ):
            raise ValueError("degree_assortativity must be finite or None")
        if self.n_connected_components < 1:
            raise ValueError("n_connected_components must be positive")
        if self.is_connected != (self.n_connected_components == 1):
            raise ValueError("connectivity fields are inconsistent")
        if self.is_connected and self.diameter is None:
            raise ValueError("connected graphs must have a diameter")
        if not self.is_connected and self.diameter is not None:
            raise ValueError("disconnected graphs must store diameter as None")
        if self.diameter is not None and self.diameter < 0:
            raise ValueError("diameter must be non-negative")

    def to_dict(self) -> dict[str, object]:
        """Return a new flat dictionary suitable for a table row."""

        return asdict(self)


def _degree_assortativity(graph: nx.Graph) -> float | None:
    """Return finite degree assortativity, or ``None`` when undefined."""

    # NetworkX/NumPy emits a RuntimeWarning when degree variance is zero. That
    # condition is expected for regular graphs and maps to our documented None.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        value = float(nx.degree_assortativity_coefficient(graph))
    return value if math.isfinite(value) else None


def extract_graph_features(record: GraphRecord) -> GraphFeatureRecord:
    """Calculate deterministic baseline features from canonical topology.

    Degree standard deviation uses the population convention (``ddof=0``).
    Total triangle count divides NetworkX's per-node triangle sum by three.
    Diameter is ``None`` for disconnected graphs, while mathematically
    undefined/non-finite degree assortativity is also represented by ``None``.
    """

    if record.n_nodes < 1:
        raise GraphValidationError("feature extraction requires at least one node")

    graph = to_networkx(record)
    degrees = np.asarray(
        [graph.degree[node] for node in range(record.n_nodes)],
        dtype=float,
    )
    is_connected = nx.is_connected(graph)
    n_connected_components = nx.number_connected_components(graph)
    triangle_count = sum(nx.triangles(graph).values()) // 3

    return GraphFeatureRecord(
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        graph_id=record.graph_id,
        family=record.family,
        n_nodes=record.n_nodes,
        n_edges=graph.number_of_edges(),
        density=float(nx.density(graph)),
        degree_mean=float(np.mean(degrees)),
        degree_std=float(np.std(degrees, ddof=0)),
        degree_min=int(np.min(degrees)),
        degree_max=int(np.max(degrees)),
        triangle_count=int(triangle_count),
        average_clustering=float(nx.average_clustering(graph)),
        degree_assortativity=_degree_assortativity(graph),
        is_connected=is_connected,
        n_connected_components=n_connected_components,
        diameter=nx.diameter(graph) if is_connected else None,
    )
