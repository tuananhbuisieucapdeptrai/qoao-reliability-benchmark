"""Portable schemas for optimization trajectories and budget checkpoints."""

from __future__ import annotations

import math
from dataclasses import dataclass

from qaoa_reliability.graphs.schema import JSONValue

TRAJECTORY_SCHEMA_VERSION = "1.0"


def _require_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class TrajectoryRecord:
    """One counted objective evaluation in execution order."""

    run_id: str
    evaluation_index: int
    timestamp_utc: str
    graph_id: str
    depth: int
    optimizer_seed: int
    parameters: tuple[float, ...]
    objective: float
    evaluation_id: str
    evaluator: str
    evaluator_version: str
    backend_metadata: dict[str, JSONValue]
    schema_version: str = TRAJECTORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != TRAJECTORY_SCHEMA_VERSION:
            raise ValueError("unsupported trajectory schema version")
        for value, name in (
            (self.run_id, "run_id"),
            (self.timestamp_utc, "timestamp_utc"),
            (self.graph_id, "graph_id"),
            (self.evaluation_id, "evaluation_id"),
            (self.evaluator, "evaluator"),
            (self.evaluator_version, "evaluator_version"),
        ):
            _require_non_empty(value, name)
        if self.evaluation_index < 1:
            raise ValueError("evaluation_index must be positive")
        if self.depth < 1 or len(self.parameters) != 2 * self.depth:
            raise ValueError("parameters must contain exactly 2 * depth values")
        if not all(math.isfinite(value) for value in self.parameters):
            raise ValueError("parameters must be finite")
        if not math.isfinite(self.objective):
            raise ValueError("objective must be finite")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "evaluation_index": self.evaluation_index,
            "timestamp_utc": self.timestamp_utc,
            "graph_id": self.graph_id,
            "depth": self.depth,
            "optimizer_seed": self.optimizer_seed,
            "parameters": list(self.parameters),
            "objective": self.objective,
            "evaluation_id": self.evaluation_id,
            "evaluator": self.evaluator,
            "evaluator_version": self.evaluator_version,
            "backend_metadata": self.backend_metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> TrajectoryRecord:
        try:
            return cls(
                schema_version=str(payload["schema_version"]),
                run_id=str(payload["run_id"]),
                evaluation_index=int(payload["evaluation_index"]),
                timestamp_utc=str(payload["timestamp_utc"]),
                graph_id=str(payload["graph_id"]),
                depth=int(payload["depth"]),
                optimizer_seed=int(payload["optimizer_seed"]),
                parameters=tuple(float(value) for value in payload["parameters"]),
                objective=float(payload["objective"]),
                evaluation_id=str(payload["evaluation_id"]),
                evaluator=str(payload["evaluator"]),
                evaluator_version=str(payload["evaluator_version"]),
                backend_metadata=dict(payload["backend_metadata"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid trajectory record") from error


@dataclass(frozen=True)
class BudgetCheckpoint:
    """Best observed objective after a nested evaluation budget."""

    budget: int
    best_objective: float
    best_evaluation_index: int


@dataclass(frozen=True)
class OptimizationRunResult:
    """Summary and complete in-memory trajectory for one optimizer run."""

    run_id: str
    graph_id: str
    depth: int
    optimizer_seed: int
    max_evaluations: int
    status: str
    records: tuple[TrajectoryRecord, ...]
    checkpoints: tuple[BudgetCheckpoint, ...] = ()

    @property
    def evaluations_used(self) -> int:
        return len(self.records)

    @property
    def best_record(self) -> TrajectoryRecord:
        if not self.records:
            raise ValueError("run contains no objective evaluations")
        return max(self.records, key=lambda record: record.objective)
