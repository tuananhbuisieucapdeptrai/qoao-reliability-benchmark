"""Unit tests for preliminary trajectory analysis."""

from qaoa_reliability.analysis.trajectory_figure import best_so_far
from qaoa_reliability.optimization.schema import TrajectoryRecord


def _record(index: int, objective: float) -> TrajectoryRecord:
    return TrajectoryRecord(
        run_id="run",
        evaluation_index=index,
        timestamp_utc="2026-10-17T00:00:00+00:00",
        graph_id="sha256:" + "a" * 64,
        depth=1,
        optimizer_seed=0,
        parameters=(0.1, 0.2),
        objective=objective,
        evaluation_id=f"evaluation-{index}",
        evaluator="fixture",
        evaluator_version="1.0",
        backend_metadata={},
    )


def test_best_so_far_is_monotone_and_preserves_incumbent() -> None:
    records = (_record(1, 1.0), _record(2, 0.5), _record(3, 1.5))

    assert best_so_far(records) == (1.0, 1.0, 1.5)
