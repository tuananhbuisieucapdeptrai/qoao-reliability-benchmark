"""Tests for deterministic multi-seed runs and nested budget checkpoints."""

from __future__ import annotations

from types import SimpleNamespace

import networkx as nx
import pytest

from qaoa_reliability.graphs.schema import from_networkx
from qaoa_reliability.optimization.orchestration import (
    run_multi_seed,
    summarize_checkpoints,
)
from qaoa_reliability.optimization.runner import FixedBudgetOptimizerRunner
from qaoa_reliability.optimization.serialization import load_trajectory_jsonl
from tests.test_optimization_runner import CountingEvaluator


def _exact_budget_minimize(fun, x0, *, callback, options, **_kwargs):
    for index in range(options["maxiter"]):
        values = x0 + 0.05 * index
        fun(values)
        callback(values)
    return SimpleNamespace(success=False)


def _graph():
    return from_networkx(nx.cycle_graph(4), family="fixture", seed=None)


def test_multi_seed_runs_once_at_max_budget_and_derives_checkpoints(tmp_path) -> None:
    evaluator = CountingEvaluator()
    result = run_multi_seed(
        graph=_graph(),
        evaluator=evaluator,
        depth=1,
        optimizer_seeds=(10, 20, 30),
        max_evaluations=6,
        checkpoints=(2, 4, 6),
        trajectory_directory=tmp_path,
        runner=FixedBudgetOptimizerRunner(minimize_fn=_exact_budget_minimize),
    )

    assert evaluator.calls == 3 * 6
    assert len(result.runs) == 3
    for run in result.runs:
        assert run.evaluations_used == 6
        assert [checkpoint.budget for checkpoint in run.checkpoints] == [2, 4, 6]
        assert run.checkpoints[-1].best_objective == run.best_record.objective
        persisted = load_trajectory_jsonl(tmp_path / f"seed-{run.optimizer_seed}.jsonl")
        assert persisted == run.records


def test_seeded_initialization_is_reproducible() -> None:
    runner = FixedBudgetOptimizerRunner(minimize_fn=_exact_budget_minimize)
    kwargs = {
        "graph": _graph(),
        "evaluator": CountingEvaluator(),
        "depth": 2,
        "optimizer_seeds": (17, 23),
        "max_evaluations": 4,
        "checkpoints": (2, 4),
        "runner": runner,
    }
    first = run_multi_seed(**kwargs)
    kwargs["evaluator"] = CountingEvaluator()
    second = run_multi_seed(**kwargs)

    assert [[record.parameters for record in run.records] for run in first.runs] == [
        [record.parameters for record in run.records] for run in second.runs
    ]
    assert [[record.objective for record in run.records] for run in first.runs] == [
        [record.objective for record in run.records] for run in second.runs
    ]


def test_checkpoint_best_is_computed_from_prefix_only() -> None:
    run = FixedBudgetOptimizerRunner(minimize_fn=_exact_budget_minimize).run(
        graph=_graph(),
        evaluator=CountingEvaluator(),
        depth=1,
        optimizer_seed=2,
        max_evaluations=5,
    )
    checkpoints = summarize_checkpoints(run.records, (1, 3, 5))
    for checkpoint in checkpoints:
        prefix = run.records[: checkpoint.budget]
        expected = max(prefix, key=lambda record: record.objective)
        assert checkpoint.best_objective == expected.objective
        assert checkpoint.best_evaluation_index == expected.evaluation_index


@pytest.mark.parametrize(
    "checkpoints",
    ((2, 2), (3, 1), (0, 2), ()),
)
def test_invalid_checkpoints_are_rejected(checkpoints) -> None:
    with pytest.raises(ValueError, match="checkpoints"):
        summarize_checkpoints((), checkpoints)


def test_duplicate_seeds_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        run_multi_seed(
            graph=_graph(),
            evaluator=CountingEvaluator(),
            depth=1,
            optimizer_seeds=(4, 4),
            max_evaluations=5,
            checkpoints=(5,),
        )
