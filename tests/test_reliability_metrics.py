"""Definitions and edge cases for T20 reliability metrics."""

from __future__ import annotations

import networkx as nx
import pytest

from qaoa_reliability.exact.maxcut import solve_exact_maxcut
from qaoa_reliability.graphs.schema import from_networkx
from qaoa_reliability.metrics import aggregate_seed_metrics, compute_run_metrics
from qaoa_reliability.optimization.schema import (
    OptimizationRunResult,
    TrajectoryRecord,
)


def _record(graph_id: str, seed: int, index: int, objective: float) -> TrajectoryRecord:
    return TrajectoryRecord(
        run_id=f"run-{seed}",
        evaluation_index=index,
        timestamp_utc=f"2026-10-17T00:00:0{index}+00:00",
        graph_id=graph_id,
        depth=1,
        optimizer_seed=seed,
        parameters=(0.1 * index, 0.2 * index),
        objective=objective,
        evaluation_id=f"evaluation-{seed}-{index}",
        evaluator="fixture",
        evaluator_version="1.0",
        backend_metadata={"source": "test"},
    )


def _run(graph_id: str, seed: int, objectives: tuple[float, ...]):
    records = tuple(
        _record(graph_id, seed, index, objective)
        for index, objective in enumerate(objectives, start=1)
    )
    return OptimizationRunResult(
        run_id=f"run-{seed}",
        graph_id=graph_id,
        depth=1,
        optimizer_seed=seed,
        max_evaluations=10,
        status="budget_reached",
        records=records,
    )


def test_run_metrics_use_only_checkpoint_prefix_and_record_exact_source() -> None:
    graph = from_networkx(nx.path_graph(2), family="fixture", seed=None)
    exact = solve_exact_maxcut(graph)
    run = _run(graph.graph_id, 7, (0.2, 0.4, 0.95, 0.8))

    metrics = compute_run_metrics(
        run,
        exact,
        checkpoints=(2, 4, 10),
        target_ratio=0.9,
    )

    assert [value.best_objective for value in metrics] == [0.4, 0.95, 0.95]
    assert [value.evaluations_available for value in metrics] == [2, 4, 4]
    assert metrics[0].regret == pytest.approx(0.6)
    assert metrics[0].normalized_gap == pytest.approx(0.6)
    assert metrics[0].success is False
    assert metrics[0].evaluations_to_target is None
    assert metrics[1].success is True
    assert metrics[1].evaluations_to_target == 3
    assert metrics[2].evaluations_to_target == 3
    assert metrics[0].exact_optimum == 1
    assert metrics[0].optimum_source == "exhaustive-symmetry-reduced@1.0"


def test_zero_optimum_has_zero_gap_and_immediate_success() -> None:
    graph = from_networkx(nx.empty_graph(1), family="fixture", seed=None)
    exact = solve_exact_maxcut(graph)
    metric = compute_run_metrics(
        _run(graph.graph_id, 1, (0.0,)),
        exact,
        checkpoints=(1,),
    )[0]

    assert metric.exact_optimum == 0
    assert metric.regret == 0.0
    assert metric.normalized_gap == 0.0
    assert metric.target_objective == 0.0
    assert metric.success is True
    assert metric.evaluations_to_target == 1


def test_seed_aggregation_quantifies_sensitivity_and_success_probability() -> None:
    graph = from_networkx(nx.path_graph(2), family="fixture", seed=None)
    exact = solve_exact_maxcut(graph)
    per_seed = []
    for seed, objectives in enumerate(
        ((0.2, 0.95), (0.3, 0.7), (0.4, 1.0)),
        start=1,
    ):
        per_seed.extend(
            compute_run_metrics(
                _run(graph.graph_id, seed, objectives),
                exact,
                checkpoints=(1, 2),
                target_ratio=0.9,
            )
        )

    summaries = aggregate_seed_metrics(per_seed)
    first, second = summaries
    assert first.n_seeds == 3
    assert first.mean_best_objective == pytest.approx(0.3)
    assert first.population_std_best_objective == pytest.approx(0.0816496580928)
    assert first.best_objective_range == pytest.approx(0.2)
    assert first.success_probability == 0.0
    assert first.mean_evaluations_to_target is None
    assert second.successes == 2
    assert second.success_probability == pytest.approx(2 / 3)
    assert second.mean_evaluations_to_target == 2.0
    assert second.mean_regret == pytest.approx((0.05 + 0.3 + 0.0) / 3)


def test_objective_above_exact_optimum_is_rejected() -> None:
    graph = from_networkx(nx.path_graph(2), family="fixture", seed=None)
    with pytest.raises(ValueError, match="exceeds"):
        compute_run_metrics(
            _run(graph.graph_id, 1, (1.1,)),
            solve_exact_maxcut(graph),
            checkpoints=(1,),
        )


def test_mismatched_exact_result_is_rejected() -> None:
    graph = from_networkx(nx.path_graph(2), family="fixture", seed=None)
    other = from_networkx(nx.path_graph(3), family="fixture", seed=None)
    with pytest.raises(ValueError, match="same graph"):
        compute_run_metrics(
            _run(graph.graph_id, 1, (0.5,)),
            solve_exact_maxcut(other),
            checkpoints=(1,),
        )


@pytest.mark.parametrize(
    "checkpoints",
    ((), (0,), (2, 1), (1, 1)),
)
def test_invalid_checkpoints_are_rejected(checkpoints) -> None:
    graph = from_networkx(nx.path_graph(2), family="fixture", seed=None)
    with pytest.raises(ValueError, match="checkpoints"):
        compute_run_metrics(
            _run(graph.graph_id, 1, (0.5,)),
            solve_exact_maxcut(graph),
            checkpoints=checkpoints,
        )


@pytest.mark.parametrize("target_ratio", (-0.1, 1.1, float("nan"), True))
def test_invalid_target_ratio_is_rejected(target_ratio) -> None:
    graph = from_networkx(nx.path_graph(2), family="fixture", seed=None)
    with pytest.raises(ValueError, match="target_ratio"):
        compute_run_metrics(
            _run(graph.graph_id, 1, (0.5,)),
            solve_exact_maxcut(graph),
            checkpoints=(1,),
            target_ratio=target_ratio,
        )


def test_duplicate_seed_rows_are_rejected() -> None:
    graph = from_networkx(nx.path_graph(2), family="fixture", seed=None)
    exact = solve_exact_maxcut(graph)
    metric = compute_run_metrics(
        _run(graph.graph_id, 1, (0.5,)),
        exact,
        checkpoints=(1,),
    )[0]
    with pytest.raises(ValueError, match="one row per seed"):
        aggregate_seed_metrics((metric, metric))
