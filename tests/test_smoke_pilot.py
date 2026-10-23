"""Integration tests for the T22 eight-cell smoke-pilot executor."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from qaoa_reliability.experiments import load_pilot_manifest
from qaoa_reliability.experiments.smoke import (
    EXPECTED_PILOT_MANIFEST_ID,
    prepare_output_directories,
    run_exploratory_p2,
    run_full_pilot,
    run_smoke_pilot,
    select_smoke_specs,
)
from qaoa_reliability.optimization import FixedBudgetOptimizerRunner

MANIFEST_PATH = Path("experiments/manifests/pilot-v0.1.json")


def _exact_budget_minimize(fun, x0, *, callback, options, **_kwargs):
    for index in range(options["maxiter"]):
        values = x0 + 0.05 * index
        fun(values)
        callback(values)
    return SimpleNamespace(success=False)


def test_smoke_selection_covers_every_family_size_cell() -> None:
    manifest = load_pilot_manifest(MANIFEST_PATH)
    specs = select_smoke_specs(manifest)

    assert manifest.manifest_id == EXPECTED_PILOT_MANIFEST_ID
    assert len(specs) == 8
    assert {(spec.family, spec.n_nodes) for spec in specs} == {
        (batch.family, batch.n_nodes) for batch in manifest.graph_batches
    }
    assert [spec.seed for spec in specs] == [
        batch.seeds[0] for batch in manifest.graph_batches
    ]


def test_existing_output_directory_is_never_overwritten(tmp_path) -> None:
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        prepare_output_directories(output)


def test_reduced_smoke_executes_all_eight_cells_and_passes_qa(tmp_path) -> None:
    output = tmp_path / "smoke"
    execution = run_smoke_pilot(
        MANIFEST_PATH,
        output,
        optimizer_seeds=(0, 1),
        budgets=(2, 4),
        runner=FixedBudgetOptimizerRunner(minimize_fn=_exact_budget_minimize),
    )

    assert execution["status"] == "completed"
    assert execution["qa_passed"] is True
    assert execution["counts"] == {
        "graphs": 8,
        "exact_results": 8,
        "feature_records": 8,
        "runs": 16,
        "trajectory_records": 64,
        "run_checkpoint_metrics": 32,
        "seed_aggregate_metrics": 16,
    }

    qa = json.loads((output / "qa" / "qa-report.json").read_text())
    assert qa["passed"] is True
    assert qa["errors"] == []
    assert qa["maximum_objective_evaluations"] == 64
    assert len(list((output / "graphs").glob("*.json"))) == 8
    assert len(list((output / "trajectories").glob("**/*.jsonl"))) == 16
    with (output / "analysis" / "smoke-summary.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 16


def test_reduced_full_pilot_executes_all_forty_graphs(tmp_path) -> None:
    output = tmp_path / "full"
    execution = run_full_pilot(
        MANIFEST_PATH,
        output,
        optimizer_seeds=(0,),
        budgets=(2,),
        runner=FixedBudgetOptimizerRunner(minimize_fn=_exact_budget_minimize),
    )

    assert execution["scope"] == "full"
    assert execution["counts"] == {
        "graphs": 40,
        "exact_results": 40,
        "feature_records": 40,
        "runs": 40,
        "trajectory_records": 80,
        "run_checkpoint_metrics": 40,
        "seed_aggregate_metrics": 40,
    }
    with (output / "analysis" / "full-summary.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 40


def test_reduced_exploratory_p2_is_bounded_and_labeled(tmp_path) -> None:
    output = tmp_path / "p2"
    execution = run_exploratory_p2(
        MANIFEST_PATH,
        output,
        optimizer_seeds=(0,),
        budgets=(2,),
        runner=FixedBudgetOptimizerRunner(minimize_fn=_exact_budget_minimize),
    )

    assert execution["scope"] == "exploratory-p2"
    assert execution["depths"] == [2]
    assert execution["counts"]["graphs"] == 8
    assert execution["counts"]["runs"] == 8
    assert execution["counts"]["trajectory_records"] == 16
