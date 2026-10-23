"""Fixed-objective-budget SciPy optimizer runner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

from qaoa_reliability.evaluators.base import Evaluator
from qaoa_reliability.graphs.schema import GraphRecord
from qaoa_reliability.optimization.schema import (
    OptimizationRunResult,
    TrajectoryRecord,
)
from qaoa_reliability.optimization.serialization import save_trajectory_record

OptimizerCallback = Callable[[tuple[float, ...], int], None]
MinimizeFunction = Callable[..., Any]


class _BudgetExhausted(RuntimeError):
    pass


def _run_id(
    graph: GraphRecord,
    evaluator: Evaluator,
    depth: int,
    optimizer_seed: int,
    max_evaluations: int,
    optimizer: str,
) -> str:
    payload = {
        "depth": depth,
        "evaluator": evaluator.evaluator_name,
        "evaluator_version": evaluator.evaluator_version,
        "graph_id": graph.graph_id,
        "max_evaluations": max_evaluations,
        "optimizer": optimizer,
        "optimizer_seed": optimizer_seed,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def initial_parameters(depth: int, seed: int) -> tuple[float, ...]:
    """Generate deterministic angles in the protocol's provisional domains."""

    if depth < 1:
        raise ValueError("depth must be positive")
    rng = np.random.default_rng(seed)
    gammas = rng.uniform(0.0, 2.0 * np.pi, size=depth)
    betas = rng.uniform(0.0, np.pi, size=depth)
    return tuple(float(value) for value in np.concatenate((gammas, betas)))


class FixedBudgetOptimizerRunner:
    """Maximize the evaluator objective with an exact call-count ceiling."""

    def __init__(self, *, minimize_fn: MinimizeFunction = minimize) -> None:
        self._minimize = minimize_fn

    def run(
        self,
        *,
        graph: GraphRecord,
        evaluator: Evaluator,
        depth: int,
        optimizer_seed: int,
        max_evaluations: int,
        parameters: Sequence[float] | None = None,
        trajectory_path: str | Path | None = None,
        callback: OptimizerCallback | None = None,
    ) -> OptimizationRunResult:
        if max_evaluations < 1:
            raise ValueError("max_evaluations must be positive")
        if trajectory_path is not None and Path(trajectory_path).exists():
            raise FileExistsError(
                f"trajectory path already exists: {Path(trajectory_path)}"
            )
        theta0 = (
            tuple(parameters)
            if parameters is not None
            else initial_parameters(depth, optimizer_seed)
        )
        run_id = _run_id(
            graph,
            evaluator,
            depth,
            optimizer_seed,
            max_evaluations,
            "COBYLA",
        )
        records: list[TrajectoryRecord] = []

        def objective(values: Sequence[float]) -> float:
            if len(records) >= max_evaluations:
                raise _BudgetExhausted
            result = evaluator.evaluate(graph, depth, values)
            record = TrajectoryRecord(
                run_id=run_id,
                evaluation_index=len(records) + 1,
                timestamp_utc=datetime.now(UTC).isoformat(),
                graph_id=graph.graph_id,
                depth=depth,
                optimizer_seed=optimizer_seed,
                parameters=result.parameters,
                objective=result.objective,
                evaluation_id=result.evaluation_id,
                evaluator=result.evaluator,
                evaluator_version=result.evaluator_version,
                backend_metadata=result.metadata,
            )
            records.append(record)
            if trajectory_path is not None:
                save_trajectory_record(record, trajectory_path)
            return -result.objective

        def optimizer_callback(values: Sequence[float]) -> None:
            if callback is not None:
                callback(tuple(float(value) for value in values), len(records))

        status = "optimizer_stopped"
        try:
            result = self._minimize(
                objective,
                np.asarray(theta0, dtype=float),
                method="COBYLA",
                callback=optimizer_callback,
                options={"maxiter": max_evaluations},
            )
            status = "optimizer_converged" if bool(result.success) else "budget_reached"
        except _BudgetExhausted:
            status = "budget_reached"

        return OptimizationRunResult(
            run_id=run_id,
            graph_id=graph.graph_id,
            depth=depth,
            optimizer_seed=optimizer_seed,
            max_evaluations=max_evaluations,
            status=status,
            records=tuple(records),
        )
