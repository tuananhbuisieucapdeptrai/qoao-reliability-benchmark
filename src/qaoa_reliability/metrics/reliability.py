"""Tested reliability metrics for budget-limited QAOA optimization."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from qaoa_reliability.exact.maxcut import ExactMaxCutResult
from qaoa_reliability.optimization.schema import OptimizationRunResult

OBJECTIVE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class RunCheckpointMetrics:
    """Metrics for one optimizer seed at one nested budget checkpoint."""

    run_id: str
    graph_id: str
    depth: int
    optimizer_seed: int
    budget: int
    evaluations_available: int
    best_objective: float
    best_evaluation_index: int
    exact_optimum: int
    optimum_source: str
    regret: float
    normalized_gap: float
    target_ratio: float
    target_objective: float
    success: bool
    evaluations_to_target: int | None


@dataclass(frozen=True)
class SeedAggregateMetrics:
    """Across-seed reliability summary at one budget checkpoint."""

    graph_id: str
    depth: int
    budget: int
    n_seeds: int
    exact_optimum: int
    optimum_source: str
    target_ratio: float
    mean_best_objective: float
    population_std_best_objective: float
    min_best_objective: float
    max_best_objective: float
    best_objective_range: float
    mean_regret: float
    mean_normalized_gap: float
    successes: int
    success_probability: float
    mean_evaluations_to_target: float | None


def _validate_checkpoints(checkpoints: Sequence[int]) -> tuple[int, ...]:
    values = tuple(checkpoints)
    if (
        not values
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in values
        )
        or tuple(sorted(set(values))) != values
    ):
        raise ValueError("checkpoints must be positive, unique, and increasing")
    return values


def _validate_target_ratio(target_ratio: float) -> float:
    if isinstance(target_ratio, bool) or not isinstance(target_ratio, (int, float)):
        raise ValueError("target_ratio must be a finite number in [0, 1]")
    value = float(target_ratio)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("target_ratio must be a finite number in [0, 1]")
    return value


def compute_run_metrics(
    run: OptimizationRunResult,
    exact: ExactMaxCutResult,
    *,
    checkpoints: Sequence[int],
    target_ratio: float = 0.95,
) -> tuple[RunCheckpointMetrics, ...]:
    """Derive per-seed checkpoint metrics without additional evaluations."""

    budgets = _validate_checkpoints(checkpoints)
    ratio = _validate_target_ratio(target_ratio)
    if run.graph_id != exact.graph_id:
        raise ValueError("run and exact result must refer to the same graph")
    if not run.records:
        raise ValueError("cannot compute metrics for an empty trajectory")
    if any(record.graph_id != run.graph_id for record in run.records):
        raise ValueError("trajectory contains a mismatched graph_id")

    optimum = exact.optimum
    source = f"{exact.solver}@{exact.solver_version}"
    target = ratio * optimum
    metrics: list[RunCheckpointMetrics] = []

    for budget in budgets:
        available = min(budget, len(run.records))
        prefix = run.records[:available]
        best = max(prefix, key=lambda record: record.objective)
        best_objective = best.objective
        if best_objective > optimum + OBJECTIVE_TOLERANCE:
            raise ValueError("observed objective exceeds the exact optimum")
        if best_objective > optimum:
            best_objective = float(optimum)

        regret = float(optimum - best_objective)
        normalized_gap = regret / optimum if optimum > 0 else 0.0
        first_target = next(
            (
                record.evaluation_index
                for record in prefix
                if record.objective + OBJECTIVE_TOLERANCE >= target
            ),
            None,
        )
        metrics.append(
            RunCheckpointMetrics(
                run_id=run.run_id,
                graph_id=run.graph_id,
                depth=run.depth,
                optimizer_seed=run.optimizer_seed,
                budget=budget,
                evaluations_available=available,
                best_objective=best_objective,
                best_evaluation_index=best.evaluation_index,
                exact_optimum=optimum,
                optimum_source=source,
                regret=regret,
                normalized_gap=normalized_gap,
                target_ratio=ratio,
                target_objective=target,
                success=first_target is not None,
                evaluations_to_target=first_target,
            )
        )
    return tuple(metrics)


def aggregate_seed_metrics(
    metrics: Sequence[RunCheckpointMetrics],
) -> tuple[SeedAggregateMetrics, ...]:
    """Aggregate per-run metrics into seed-sensitivity summaries by budget."""

    values = tuple(metrics)
    if not values:
        raise ValueError("metrics must not be empty")
    identity = {
        (
            value.graph_id,
            value.depth,
            value.exact_optimum,
            value.optimum_source,
            value.target_ratio,
        )
        for value in values
    }
    if len(identity) != 1:
        raise ValueError("all metrics must share graph, depth, optimum, and target")

    graph_id, depth, optimum, source, target_ratio = identity.pop()
    summaries: list[SeedAggregateMetrics] = []
    for budget in sorted({value.budget for value in values}):
        group = [value for value in values if value.budget == budget]
        seeds = {value.optimizer_seed for value in group}
        if len(seeds) != len(group):
            raise ValueError("each budget must contain at most one row per seed")
        objectives = [value.best_objective for value in group]
        reached = [
            value.evaluations_to_target
            for value in group
            if value.evaluations_to_target is not None
        ]
        successes = len(reached)
        summaries.append(
            SeedAggregateMetrics(
                graph_id=graph_id,
                depth=depth,
                budget=budget,
                n_seeds=len(group),
                exact_optimum=optimum,
                optimum_source=source,
                target_ratio=target_ratio,
                mean_best_objective=statistics.fmean(objectives),
                population_std_best_objective=statistics.pstdev(objectives),
                min_best_objective=min(objectives),
                max_best_objective=max(objectives),
                best_objective_range=max(objectives) - min(objectives),
                mean_regret=statistics.fmean(value.regret for value in group),
                mean_normalized_gap=statistics.fmean(
                    value.normalized_gap for value in group
                ),
                successes=successes,
                success_probability=successes / len(group),
                mean_evaluations_to_target=(
                    statistics.fmean(reached) if reached else None
                ),
            )
        )
    return tuple(summaries)
