"""Deterministic multi-seed runs and nested budget summaries."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from qaoa_reliability.evaluators.base import Evaluator
from qaoa_reliability.graphs.schema import GraphRecord
from qaoa_reliability.optimization.runner import FixedBudgetOptimizerRunner
from qaoa_reliability.optimization.schema import (
    BudgetCheckpoint,
    OptimizationRunResult,
    TrajectoryRecord,
)


def summarize_checkpoints(
    records: Sequence[TrajectoryRecord],
    checkpoints: Sequence[int],
) -> tuple[BudgetCheckpoint, ...]:
    """Derive nested best-so-far results without re-evaluating the objective."""

    normalized = tuple(checkpoints)
    if not normalized or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in normalized
    ):
        raise ValueError("checkpoints must be positive integers")
    if tuple(sorted(set(normalized))) != normalized:
        raise ValueError("checkpoints must be unique and increasing")

    summaries: list[BudgetCheckpoint] = []
    for budget in normalized:
        if budget > len(records):
            continue
        best = max(records[:budget], key=lambda record: record.objective)
        summaries.append(
            BudgetCheckpoint(
                budget=budget,
                best_objective=best.objective,
                best_evaluation_index=best.evaluation_index,
            )
        )
    return tuple(summaries)


@dataclass(frozen=True)
class MultiSeedResult:
    graph_id: str
    depth: int
    max_evaluations: int
    checkpoints: tuple[int, ...]
    runs: tuple[OptimizationRunResult, ...]


def run_multi_seed(
    *,
    graph: GraphRecord,
    evaluator: Evaluator,
    depth: int,
    optimizer_seeds: Sequence[int],
    max_evaluations: int,
    checkpoints: Sequence[int],
    trajectory_directory: str | Path | None = None,
    runner: FixedBudgetOptimizerRunner | None = None,
) -> MultiSeedResult:
    """Run each unique seed once at max budget and derive all checkpoints."""

    seeds = tuple(optimizer_seeds)
    if (
        not seeds
        or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError("optimizer_seeds must be non-empty, unique integers")
    normalized_checkpoints = tuple(checkpoints)
    if not normalized_checkpoints or normalized_checkpoints[-1] > max_evaluations:
        raise ValueError("checkpoints must end at or below max_evaluations")
    summarize_checkpoints((), normalized_checkpoints)

    active_runner = runner or FixedBudgetOptimizerRunner()
    results: list[OptimizationRunResult] = []
    for seed in seeds:
        path = None
        if trajectory_directory is not None:
            path = Path(trajectory_directory) / f"seed-{seed}.jsonl"
        result = active_runner.run(
            graph=graph,
            evaluator=evaluator,
            depth=depth,
            optimizer_seed=seed,
            max_evaluations=max_evaluations,
            trajectory_path=path,
        )
        results.append(
            OptimizationRunResult(
                run_id=result.run_id,
                graph_id=result.graph_id,
                depth=result.depth,
                optimizer_seed=result.optimizer_seed,
                max_evaluations=result.max_evaluations,
                status=result.status,
                records=result.records,
                checkpoints=summarize_checkpoints(
                    result.records, normalized_checkpoints
                ),
            )
        )

    return MultiSeedResult(
        graph_id=graph.graph_id,
        depth=depth,
        max_evaluations=max_evaluations,
        checkpoints=normalized_checkpoints,
        runs=tuple(results),
    )
