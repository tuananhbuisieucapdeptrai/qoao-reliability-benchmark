"""Tests for exact budget accounting and trajectory persistence."""

from __future__ import annotations

from types import SimpleNamespace

import networkx as nx
import pytest

from qaoa_reliability.evaluators.base import (
    EvaluationResult,
    compute_evaluation_id,
    validate_evaluation_request,
)
from qaoa_reliability.evaluators.numpy_statevector import NumpyStatevectorEvaluator
from qaoa_reliability.graphs.schema import from_networkx
from qaoa_reliability.optimization.runner import FixedBudgetOptimizerRunner
from qaoa_reliability.optimization.serialization import load_trajectory_jsonl


class CountingEvaluator:
    evaluator_name = "counting"
    evaluator_version = "1.0"

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, graph, depth, parameters):
        theta = validate_evaluation_request(graph, depth, parameters)
        self.calls += 1
        objective = float(sum((index + 1) * value for index, value in enumerate(theta)))
        evaluation_id = compute_evaluation_id(
            graph_id=graph.graph_id,
            depth=depth,
            parameters=theta,
            evaluator=self.evaluator_name,
            evaluator_version=self.evaluator_version,
        )
        return EvaluationResult(
            graph_id=graph.graph_id,
            depth=depth,
            parameters=theta,
            objective=objective,
            evaluator=self.evaluator_name,
            evaluator_version=self.evaluator_version,
            evaluation_id=evaluation_id,
            metadata={"backend": "controlled-test-double"},
        )


def _graph():
    return from_networkx(nx.path_graph(3), family="fixture", seed=None)


def _budget_consuming_minimize(fun, x0, *, callback, options, **_kwargs):
    for index in range(options["maxiter"] + 1):
        values = x0 + 0.01 * index
        fun(values)
        callback(values)
    return SimpleNamespace(success=False)


def test_exact_budget_counts_only_objective_calls(tmp_path) -> None:
    evaluator = CountingEvaluator()
    callback_calls: list[tuple[tuple[float, ...], int]] = []
    path = tmp_path / "trajectory.jsonl"
    runner = FixedBudgetOptimizerRunner(minimize_fn=_budget_consuming_minimize)

    result = runner.run(
        graph=_graph(),
        evaluator=evaluator,
        depth=1,
        optimizer_seed=7,
        max_evaluations=5,
        trajectory_path=path,
        callback=lambda parameters, count: callback_calls.append((parameters, count)),
    )

    assert evaluator.calls == 5
    assert result.evaluations_used == 5
    assert result.status == "budget_reached"
    assert len(callback_calls) == 5
    assert [record.evaluation_index for record in result.records] == [1, 2, 3, 4, 5]
    assert load_trajectory_jsonl(path) == result.records


def test_every_repeated_parameter_call_is_counted() -> None:
    def repeat_minimize(fun, x0, **_kwargs):
        for _ in range(4):
            fun(x0)
        return SimpleNamespace(success=True)

    evaluator = CountingEvaluator()
    result = FixedBudgetOptimizerRunner(minimize_fn=repeat_minimize).run(
        graph=_graph(),
        evaluator=evaluator,
        depth=1,
        optimizer_seed=3,
        max_evaluations=4,
        parameters=(0.2, 0.3),
    )
    assert evaluator.calls == 4
    assert result.evaluations_used == 4
    assert len({record.evaluation_id for record in result.records}) == 1


def test_interrupted_run_leaves_valid_flushed_jsonl(tmp_path) -> None:
    def interrupted_minimize(fun, x0, **_kwargs):
        for index in range(3):
            fun(x0 + index)
        raise RuntimeError("simulated interruption")

    path = tmp_path / "interrupted.jsonl"
    runner = FixedBudgetOptimizerRunner(minimize_fn=interrupted_minimize)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        runner.run(
            graph=_graph(),
            evaluator=CountingEvaluator(),
            depth=1,
            optimizer_seed=5,
            max_evaluations=10,
            trajectory_path=path,
        )

    records = load_trajectory_jsonl(path)
    assert len(records) == 3
    assert [record.evaluation_index for record in records] == [1, 2, 3]
    assert all(record.backend_metadata["backend"] for record in records)


def test_run_id_is_stable_for_identical_configuration() -> None:
    runner = FixedBudgetOptimizerRunner(minimize_fn=_budget_consuming_minimize)
    first = runner.run(
        graph=_graph(),
        evaluator=CountingEvaluator(),
        depth=1,
        optimizer_seed=11,
        max_evaluations=3,
    )
    second = runner.run(
        graph=_graph(),
        evaluator=CountingEvaluator(),
        depth=1,
        optimizer_seed=11,
        max_evaluations=3,
    )
    assert first.run_id == second.run_id
    assert [record.parameters for record in first.records] == [
        record.parameters for record in second.records
    ]


def test_rejects_non_positive_budget() -> None:
    with pytest.raises(ValueError, match="max_evaluations"):
        FixedBudgetOptimizerRunner().run(
            graph=_graph(),
            evaluator=CountingEvaluator(),
            depth=1,
            optimizer_seed=1,
            max_evaluations=0,
        )


def test_real_cobyla_respects_objective_budget() -> None:
    result = FixedBudgetOptimizerRunner().run(
        graph=_graph(),
        evaluator=NumpyStatevectorEvaluator(),
        depth=1,
        optimizer_seed=42,
        max_evaluations=8,
    )
    assert 1 <= result.evaluations_used <= 8
    assert result.status in {"budget_reached", "optimizer_converged"}


def test_existing_trajectory_is_not_mixed_with_new_run(tmp_path) -> None:
    path = tmp_path / "existing.jsonl"
    path.write_text("existing\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        FixedBudgetOptimizerRunner().run(
            graph=_graph(),
            evaluator=CountingEvaluator(),
            depth=1,
            optimizer_seed=1,
            max_evaluations=2,
            trajectory_path=path,
        )
