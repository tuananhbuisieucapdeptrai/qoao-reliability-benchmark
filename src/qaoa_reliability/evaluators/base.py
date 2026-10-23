"""Common evaluator interface and result schema."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from qaoa_reliability.graphs.schema import GraphRecord, JSONValue

EVALUATION_SCHEMA_VERSION = "1.0"


class EvaluationValidationError(ValueError):
    """Raised when an evaluation request or result violates the contract."""


def validate_evaluation_request(
    graph: GraphRecord,
    depth: int,
    parameters: Sequence[float],
) -> tuple[float, ...]:
    """Validate a QAOA request and return an immutable parameter vector."""

    if not isinstance(graph, GraphRecord):
        raise EvaluationValidationError("graph must be a GraphRecord")
    return validate_evaluation_request_parameters(depth, parameters)


def compute_evaluation_id(
    *,
    graph_id: str,
    depth: int,
    parameters: Sequence[float],
    evaluator: str,
    evaluator_version: str,
) -> str:
    """Return a stable identity for one evaluator request."""

    payload = {
        "depth": depth,
        "evaluator": evaluator,
        "evaluator_version": evaluator_version,
        "graph_id": graph_id,
        "parameters": list(parameters),
        "schema_version": EVALUATION_SCHEMA_VERSION,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _copy_metadata(metadata: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    if not isinstance(metadata, Mapping):
        raise EvaluationValidationError("metadata must be a mapping")
    try:
        return json.loads(json.dumps(dict(metadata), allow_nan=False))
    except (TypeError, ValueError) as error:
        raise EvaluationValidationError(
            "metadata must contain only finite JSON-compatible values"
        ) from error


@dataclass(frozen=True)
class EvaluationResult:
    """Portable output from one exact QAOA objective evaluation."""

    graph_id: str
    depth: int
    parameters: tuple[float, ...]
    objective: float
    evaluator: str
    evaluator_version: str
    evaluation_id: str
    metadata: dict[str, JSONValue] = field(default_factory=dict)
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVALUATION_SCHEMA_VERSION:
            raise EvaluationValidationError(
                f"schema_version must be {EVALUATION_SCHEMA_VERSION!r}"
            )
        digest = (
            self.graph_id.removeprefix("sha256:")
            if isinstance(self.graph_id, str)
            else ""
        )
        if (
            not isinstance(self.graph_id, str)
            or not self.graph_id.startswith("sha256:")
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise EvaluationValidationError("graph_id must be a SHA-256 identifier")
        parameters = validate_evaluation_request_parameters(
            self.depth,
            self.parameters,
        )
        if isinstance(self.objective, bool) or not isinstance(
            self.objective, (int, float)
        ):
            raise EvaluationValidationError("objective must be a finite real number")
        objective = float(self.objective)
        if not math.isfinite(objective):
            raise EvaluationValidationError("objective must be a finite real number")
        if not isinstance(self.evaluator, str) or not self.evaluator:
            raise EvaluationValidationError("evaluator must be a non-empty string")
        if not isinstance(self.evaluator_version, str) or not self.evaluator_version:
            raise EvaluationValidationError(
                "evaluator_version must be a non-empty string"
            )

        expected_id = compute_evaluation_id(
            graph_id=self.graph_id,
            depth=self.depth,
            parameters=parameters,
            evaluator=self.evaluator,
            evaluator_version=self.evaluator_version,
        )
        if self.evaluation_id != expected_id:
            raise EvaluationValidationError(
                "evaluation_id does not match the evaluation request"
            )

        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "metadata", _copy_metadata(self.metadata))

    def to_dict(self) -> dict[str, JSONValue]:
        """Return a strict JSON-compatible representation."""

        return {
            "schema_version": self.schema_version,
            "evaluation_id": self.evaluation_id,
            "graph_id": self.graph_id,
            "depth": self.depth,
            "parameters": list(self.parameters),
            "objective": self.objective,
            "evaluator": self.evaluator,
            "evaluator_version": self.evaluator_version,
            "metadata": _copy_metadata(self.metadata),
        }


def validate_evaluation_request_parameters(
    depth: int,
    parameters: Sequence[float],
) -> tuple[float, ...]:
    """Validate result parameters without requiring a graph instance."""

    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise EvaluationValidationError("depth must be a positive integer")
    try:
        values = tuple(parameters)
    except TypeError as error:
        raise EvaluationValidationError("parameters must be a sequence") from error
    if len(values) != 2 * depth:
        raise EvaluationValidationError(
            f"depth {depth} requires {2 * depth} parameters; got {len(values)}"
        )
    normalized: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvaluationValidationError(
                f"parameter {index} must be a finite real number"
            )
        number = float(value)
        if not math.isfinite(number):
            raise EvaluationValidationError(
                f"parameter {index} must be a finite real number"
            )
        normalized.append(number)
    return tuple(normalized)


@runtime_checkable
class Evaluator(Protocol):
    """Implementation-independent exact QAOA evaluator contract."""

    evaluator_name: str
    evaluator_version: str

    def evaluate(
        self,
        graph: GraphRecord,
        depth: int,
        parameters: Sequence[float],
    ) -> EvaluationResult:
        """Evaluate one graph and complete QAOA parameter vector."""
        ...
