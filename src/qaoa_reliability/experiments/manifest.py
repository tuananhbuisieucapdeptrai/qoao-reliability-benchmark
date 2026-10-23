"""Validated, content-addressed pilot experiment manifests."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from qaoa_reliability.graphs.generators import SUPPORTED_FAMILIES
from qaoa_reliability.graphs.schema import (
    GraphGenerationSpec,
    JSONValue,
)

PILOT_MANIFEST_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class GraphBatchSpec:
    """One graph family/size cell and its explicitly listed seeds."""

    family: str
    n_nodes: int
    seeds: tuple[int, ...]
    parameters: dict[str, JSONValue]

    def __post_init__(self) -> None:
        if self.family not in SUPPORTED_FAMILIES:
            raise ValueError(f"unsupported graph family: {self.family}")
        if (
            isinstance(self.n_nodes, bool)
            or not isinstance(self.n_nodes, int)
            or self.n_nodes < 1
        ):
            raise ValueError("n_nodes must be positive")
        if not self.seeds or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("graph seeds must be non-empty and unique within a batch")
        for seed in self.seeds:
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise ValueError("graph seeds must be integers")
        # Reuse the graph contract to validate JSON-compatible parameters.
        GraphGenerationSpec(self.family, self.n_nodes, self.seeds[0], self.parameters)

    def expand(self) -> tuple[GraphGenerationSpec, ...]:
        return tuple(
            GraphGenerationSpec(
                family=self.family,
                n_nodes=self.n_nodes,
                seed=seed,
                parameters=self.parameters,
            )
            for seed in self.seeds
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "family": self.family,
            "n_nodes": self.n_nodes,
            "seeds": list(self.seeds),
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class PilotManifest:
    """Immutable definition of the complete initial research pilot."""

    name: str
    protocol_version: str
    graph_batches: tuple[GraphBatchSpec, ...]
    optimizer_seeds: tuple[int, ...]
    depths: tuple[int, ...]
    budgets: tuple[int, ...]
    evaluator: str
    optimizer: str
    target_ratio: float
    schema_version: str = PILOT_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PILOT_MANIFEST_SCHEMA_VERSION:
            raise ValueError("unsupported pilot manifest schema version")
        if not self.name or not self.protocol_version:
            raise ValueError("name and protocol_version must be non-empty")
        if not self.graph_batches:
            raise ValueError("graph_batches must not be empty")
        cells = {(batch.family, batch.n_nodes) for batch in self.graph_batches}
        if len(cells) != len(self.graph_batches):
            raise ValueError("graph family/size cells must be unique")
        all_graph_seeds = [
            (batch.family, batch.n_nodes, seed)
            for batch in self.graph_batches
            for seed in batch.seeds
        ]
        if len(set(all_graph_seeds)) != len(all_graph_seeds):
            raise ValueError("expanded graph specifications must be unique")
        if (
            not self.optimizer_seeds
            or len(set(self.optimizer_seeds)) != len(self.optimizer_seeds)
            or any(
                isinstance(seed, bool) or not isinstance(seed, int)
                for seed in self.optimizer_seeds
            )
        ):
            raise ValueError("optimizer_seeds must be non-empty unique integers")
        if (
            not self.depths
            or any(
                isinstance(depth, bool) or not isinstance(depth, int) or depth < 1
                for depth in self.depths
            )
            or tuple(sorted(set(self.depths))) != self.depths
        ):
            raise ValueError("depths must be positive, unique, and increasing")
        if (
            not self.budgets
            or any(
                isinstance(budget, bool) or not isinstance(budget, int) or budget < 1
                for budget in self.budgets
            )
            or tuple(sorted(set(self.budgets))) != self.budgets
        ):
            raise ValueError("budgets must be positive, unique, and increasing")
        if not self.evaluator or not self.optimizer:
            raise ValueError("evaluator and optimizer must be non-empty")
        if (
            isinstance(self.target_ratio, bool)
            or not isinstance(self.target_ratio, (int, float))
            or not math.isfinite(self.target_ratio)
            or not 0 <= self.target_ratio <= 1
        ):
            raise ValueError("target_ratio must be finite and in [0, 1]")

    @property
    def graph_specs(self) -> tuple[GraphGenerationSpec, ...]:
        return tuple(spec for batch in self.graph_batches for spec in batch.expand())

    @property
    def graph_count(self) -> int:
        return len(self.graph_specs)

    @property
    def run_count(self) -> int:
        return self.graph_count * len(self.optimizer_seeds) * len(self.depths)

    @property
    def maximum_objective_evaluations(self) -> int:
        return self.run_count * self.budgets[-1]

    def identity_payload(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "protocol_version": self.protocol_version,
            "graph_batches": [batch.to_dict() for batch in self.graph_batches],
            "optimizer_seeds": list(self.optimizer_seeds),
            "depths": list(self.depths),
            "budgets": list(self.budgets),
            "evaluator": self.evaluator,
            "optimizer": self.optimizer,
            "target_ratio": self.target_ratio,
        }

    @property
    def manifest_id(self) -> str:
        encoded = json.dumps(
            self.identity_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def load_pilot_manifest(path: str | Path) -> PilotManifest:
    """Load, validate, and integrity-check a pilot JSON manifest."""

    with Path(path).open(encoding="utf-8") as stream:
        payload = json.load(stream)
    try:
        batches = tuple(
            GraphBatchSpec(
                family=batch["family"],
                n_nodes=batch["n_nodes"],
                seeds=tuple(batch["seeds"]),
                parameters=batch["parameters"],
            )
            for batch in payload["graph_batches"]
        )
        manifest = PilotManifest(
            schema_version=payload["schema_version"],
            name=payload["name"],
            protocol_version=payload["protocol_version"],
            graph_batches=batches,
            optimizer_seeds=tuple(payload["optimizer_seeds"]),
            depths=tuple(payload["depths"]),
            budgets=tuple(payload["budgets"]),
            evaluator=payload["evaluator"],
            optimizer=payload["optimizer"],
            target_ratio=float(payload["target_ratio"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid pilot manifest") from error
    if payload.get("manifest_id") != manifest.manifest_id:
        raise ValueError("pilot manifest_id does not match its content")
    return manifest
