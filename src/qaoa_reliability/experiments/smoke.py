"""Validated pilot execution shared by the T22 smoke and T25 full runs."""

from __future__ import annotations

import csv
import json
from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from qaoa_reliability.evaluators import (
    NumpyStatevectorEvaluator,
)
from qaoa_reliability.exact.maxcut import solve_exact_maxcut
from qaoa_reliability.experiments import (
    PilotManifest,
    load_pilot_manifest,
)
from qaoa_reliability.features import extract_graph_features
from qaoa_reliability.graphs.generators import generate_graph
from qaoa_reliability.graphs.serialization import (
    save_graph_record,
)
from qaoa_reliability.metrics import (
    aggregate_seed_metrics,
    compute_run_metrics,
)
from qaoa_reliability.optimization import run_multi_seed
from qaoa_reliability.optimization.runner import FixedBudgetOptimizerRunner
from qaoa_reliability.optimization.serialization import load_trajectory_jsonl

EXPECTED_PILOT_MANIFEST_ID = (
    "sha256:84a992b08c73e3988cf4773c2b919e930e5ac2e6bd361970bad411f6698d80f3"
)

SMOKE_SCHEMA_VERSION = "1.0"


def select_smoke_specs(manifest: PilotManifest):
    """Select the first graph from every family/size cell."""

    specs = tuple(batch.expand()[0] for batch in manifest.graph_batches)

    if len(specs) != 8:
        raise ValueError(f"smoke pilot requires 8 graph cells; got {len(specs)}")

    cells = {(spec.family, spec.n_nodes) for spec in specs}

    expected_cells = {
        ("erdos_renyi", 8),
        ("erdos_renyi", 10),
        ("random_regular", 8),
        ("random_regular", 10),
        ("watts_strogatz", 8),
        ("watts_strogatz", 10),
        ("stochastic_block_model", 8),
        ("stochastic_block_model", 10),
    }

    if cells != expected_cells:
        raise ValueError("smoke specifications do not cover every family/size cell")

    return specs


def prepare_output_directories(output_directory: Path):
    if output_directory.exists():
        raise FileExistsError(f"pilot output already exists: {output_directory}")

    paths = {
        "root": output_directory,
        "graphs": output_directory / "graphs",
        "exact": output_directory / "exact",
        "features": output_directory / "features",
        "trajectories": output_directory / "trajectories",
        "metrics": output_directory / "metrics",
        "analysis": output_directory / "analysis",
        "qa": output_directory / "qa",
    }

    for path in paths.values():
        path.mkdir(parents=True, exist_ok=False)

    return paths


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, payload: dict) -> None:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    with path.open("a", encoding="utf-8") as stream:
        stream.write(encoded + "\n")
        stream.flush()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _trajectory_directory(paths: dict[str, Path], graph, depth: int) -> Path:
    return (
        paths["trajectories"]
        / f"{graph.family}-n{graph.n_nodes}-g{graph.generation_seed}"
        / f"p{depth}"
    )


def _write_summary_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty smoke summary")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _run_pilot(
    manifest_path: str | Path,
    output_directory: str | Path,
    *,
    scope: str,
    evaluator=None,
    runner: FixedBudgetOptimizerRunner | None = None,
    optimizer_seeds: Sequence[int] | None = None,
    budgets: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Execute and validate a selected scope of the frozen pilot matrix.

    ``optimizer_seeds`` and ``budgets`` are test hooks. Production callers
    should leave them unset so the frozen manifest controls the workload.
    """

    manifest = load_pilot_manifest(manifest_path)
    if manifest.manifest_id != EXPECTED_PILOT_MANIFEST_ID:
        raise ValueError("pilot execution requires the frozen pilot-v0.1 manifest")
    if scope not in {"smoke", "full", "exploratory-p2"}:
        raise ValueError("unsupported pilot execution scope")

    selected_specs = (
        select_smoke_specs(manifest)
        if scope in {"smoke", "exploratory-p2"}
        else manifest.graph_specs
    )
    default_seeds = (
        manifest.optimizer_seeds[:5]
        if scope == "exploratory-p2"
        else manifest.optimizer_seeds
    )
    seeds = tuple(default_seeds if optimizer_seeds is None else optimizer_seeds)
    active_budgets = tuple(manifest.budgets if budgets is None else budgets)
    active_depths = (2,) if scope == "exploratory-p2" else manifest.depths
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("optimizer seeds must be non-empty and unique")
    if (
        not active_budgets
        or tuple(sorted(set(active_budgets))) != active_budgets
        or any(value < 1 for value in active_budgets)
    ):
        raise ValueError("budgets must be positive, unique, and increasing")

    output = Path(output_directory)
    paths = prepare_output_directories(output)
    execution_path = paths["root"] / "execution.json"
    started_at = _utc_now()
    started_clock = perf_counter()
    execution: dict[str, Any] = {
        "schema_version": SMOKE_SCHEMA_VERSION,
        "status": "running",
        "scope": scope,
        "started_at_utc": started_at,
        "manifest_path": str(Path(manifest_path)),
        "manifest_id": manifest.manifest_id,
        "graph_count": len(selected_specs),
        "optimizer_seeds": list(seeds),
        "depths": list(active_depths),
        "budgets": list(active_budgets),
        "evaluator": manifest.evaluator,
        "optimizer": manifest.optimizer,
        "target_ratio": manifest.target_ratio,
    }
    write_json(execution_path, execution)

    exact_path = paths["exact"] / "exact-results.jsonl"
    feature_path = paths["features"] / "graph-features.jsonl"
    run_metrics_path = paths["metrics"] / "run-checkpoints.jsonl"
    aggregate_path = paths["metrics"] / "seed-summaries.jsonl"
    active_evaluator = evaluator or NumpyStatevectorEvaluator()
    active_runner = runner or FixedBudgetOptimizerRunner()

    graph_count = 0
    run_count = 0
    trajectory_record_count = 0
    run_metric_count = 0
    aggregate_count = 0
    summary_rows: list[dict[str, Any]] = []
    seen_graph_ids: set[str] = set()
    qa_errors: list[str] = []

    try:
        for spec in selected_specs:
            graph = generate_graph(spec)
            graph_count += 1
            if graph.graph_id in seen_graph_ids:
                qa_errors.append(f"duplicate graph_id: {graph.graph_id}")
            seen_graph_ids.add(graph.graph_id)

            graph_name = f"{spec.family}-n{spec.n_nodes}-seed{spec.seed}.json"
            save_graph_record(graph, paths["graphs"] / graph_name)

            exact = solve_exact_maxcut(graph)
            append_jsonl(exact_path, asdict(exact))
            features = extract_graph_features(graph)
            append_jsonl(feature_path, features.to_dict())

            for depth in active_depths:
                trajectory_directory = _trajectory_directory(paths, graph, depth)
                multi_seed = run_multi_seed(
                    graph=graph,
                    evaluator=active_evaluator,
                    depth=depth,
                    optimizer_seeds=seeds,
                    max_evaluations=active_budgets[-1],
                    checkpoints=active_budgets,
                    trajectory_directory=trajectory_directory,
                    runner=active_runner,
                )
                all_run_metrics = []
                for run in multi_seed.runs:
                    run_count += 1
                    trajectory_path = (
                        trajectory_directory / f"seed-{run.optimizer_seed}.jsonl"
                    )
                    persisted = load_trajectory_jsonl(trajectory_path)
                    if persisted != run.records:
                        qa_errors.append(
                            f"trajectory round-trip mismatch: {run.run_id}"
                        )
                    if not 1 <= len(run.records) <= active_budgets[-1]:
                        qa_errors.append(
                            f"trajectory has {len(run.records)} records outside "
                            f"the allowed range 1..{active_budgets[-1]}: {run.run_id}"
                        )
                    expected_indices = tuple(range(1, len(run.records) + 1))
                    observed_indices = tuple(
                        record.evaluation_index for record in run.records
                    )
                    if observed_indices != expected_indices:
                        qa_errors.append(
                            f"non-contiguous evaluation indices: {run.run_id}"
                        )
                    trajectory_record_count += len(run.records)

                    metrics = compute_run_metrics(
                        run,
                        exact,
                        checkpoints=active_budgets,
                        target_ratio=manifest.target_ratio,
                    )
                    all_run_metrics.extend(metrics)
                    for metric in metrics:
                        append_jsonl(run_metrics_path, asdict(metric))
                        run_metric_count += 1

                aggregates = aggregate_seed_metrics(all_run_metrics)
                for aggregate in aggregates:
                    append_jsonl(aggregate_path, asdict(aggregate))
                    aggregate_count += 1
                    row = {
                        "manifest_id": manifest.manifest_id,
                        "family": graph.family,
                        "n_nodes": graph.n_nodes,
                        "graph_seed": graph.generation_seed,
                        **asdict(aggregate),
                    }
                    summary_rows.append(row)

        expected_runs = graph_count * len(active_depths) * len(seeds)
        maximum_records = expected_runs * active_budgets[-1]
        expected_run_metrics = expected_runs * len(active_budgets)
        expected_aggregates = graph_count * len(active_depths) * len(active_budgets)
        observed = {
            "graphs": graph_count,
            "exact_results": graph_count,
            "feature_records": graph_count,
            "runs": run_count,
            "trajectory_records": trajectory_record_count,
            "run_checkpoint_metrics": run_metric_count,
            "seed_aggregate_metrics": aggregate_count,
        }
        expected = {
            "graphs": len(selected_specs),
            "exact_results": len(selected_specs),
            "feature_records": len(selected_specs),
            "runs": expected_runs,
            "run_checkpoint_metrics": expected_run_metrics,
            "seed_aggregate_metrics": expected_aggregates,
        }
        for key, expected_value in expected.items():
            if observed[key] != expected_value:
                qa_errors.append(
                    f"{key}: observed {observed[key]}, expected {expected_value}"
                )
        if not expected_runs <= trajectory_record_count <= maximum_records:
            qa_errors.append(
                "trajectory_records: observed "
                f"{trajectory_record_count}, allowed {expected_runs}..{maximum_records}"
            )

        _write_summary_csv(paths["analysis"] / f"{scope}-summary.csv", summary_rows)
        qa_report = {
            "schema_version": SMOKE_SCHEMA_VERSION,
            "passed": not qa_errors,
            "manifest_id": manifest.manifest_id,
            "expected": expected,
            "maximum_objective_evaluations": maximum_records,
            "observed": observed,
            "errors": qa_errors,
        }
        write_json(paths["qa"] / "qa-report.json", qa_report)
        if qa_errors:
            raise RuntimeError("pilot QA failed; see qa/qa-report.json")

        execution.update(
            {
                "status": "completed",
                "completed_at_utc": _utc_now(),
                "runtime_seconds": perf_counter() - started_clock,
                "counts": observed,
                "qa_passed": True,
            }
        )
        write_json(execution_path, execution)
        return execution
    except Exception as error:
        execution.update(
            {
                "status": "failed",
                "completed_at_utc": _utc_now(),
                "runtime_seconds": perf_counter() - started_clock,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        write_json(execution_path, execution)
        raise


def run_smoke_pilot(
    manifest_path: str | Path,
    output_directory: str | Path,
    *,
    evaluator=None,
    runner: FixedBudgetOptimizerRunner | None = None,
    optimizer_seeds: Sequence[int] | None = None,
    budgets: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Execute one graph from every frozen pilot family/size cell."""

    return _run_pilot(
        manifest_path,
        output_directory,
        scope="smoke",
        evaluator=evaluator,
        runner=runner,
        optimizer_seeds=optimizer_seeds,
        budgets=budgets,
    )


def run_full_pilot(
    manifest_path: str | Path,
    output_directory: str | Path,
    *,
    evaluator=None,
    runner: FixedBudgetOptimizerRunner | None = None,
    optimizer_seeds: Sequence[int] | None = None,
    budgets: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Execute every graph and run in the frozen pilot manifest."""

    return _run_pilot(
        manifest_path,
        output_directory,
        scope="full",
        evaluator=evaluator,
        runner=runner,
        optimizer_seeds=optimizer_seeds,
        budgets=budgets,
    )


def run_exploratory_p2(
    manifest_path: str | Path,
    output_directory: str | Path,
    *,
    evaluator=None,
    runner: FixedBudgetOptimizerRunner | None = None,
    optimizer_seeds: Sequence[int] | None = None,
    budgets: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Run the removable T27 p=2 subset: eight graphs by five seeds."""

    return _run_pilot(
        manifest_path,
        output_directory,
        scope="exploratory-p2",
        evaluator=evaluator,
        runner=runner,
        optimizer_seeds=optimizer_seeds,
        budgets=budgets,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Run the frozen T22 smoke pilot")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/manifests/pilot-v0.1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/smoke-pilot-v0.1"),
    )
    args = parser.parse_args(argv)
    execution = run_smoke_pilot(args.manifest, args.output)
    print(json.dumps(execution, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
