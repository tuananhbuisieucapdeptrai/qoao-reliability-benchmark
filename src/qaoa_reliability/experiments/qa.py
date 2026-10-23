"""T26 integrity, completeness, join, and reproducibility audit."""

from __future__ import annotations

import csv
import hashlib
import json
from argparse import ArgumentParser
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from qaoa_reliability.exact.maxcut import solve_exact_maxcut
from qaoa_reliability.experiments.manifest import load_pilot_manifest
from qaoa_reliability.features import extract_graph_features
from qaoa_reliability.graphs.generators import generate_graph
from qaoa_reliability.graphs.serialization import load_graph_record
from qaoa_reliability.optimization.serialization import load_trajectory_jsonl

DATA_QA_SCHEMA_VERSION = "1.0"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from error
            if not isinstance(row, dict):
                raise ValueError(f"non-object JSON row at {path}:{line_number}")
            rows.append(row)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _json_round_trip(payload: Any) -> Any:
    """Normalize tuples and other JSON-compatible containers as stored on disk."""

    return json.loads(json.dumps(payload, allow_nan=False))


def _check_unique(values: Sequence[str], label: str, errors: list[str]) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate {label}: {duplicates[:5]}")


def run_data_qa(
    manifest_path: str | Path,
    results_directory: str | Path,
) -> dict[str, Any]:
    """Audit a completed full-pilot directory and emit stable checksums."""

    manifest = load_pilot_manifest(manifest_path)
    results = Path(results_directory)
    qa_directory = results / "qa"
    qa_directory.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    checks: dict[str, Any] = {}

    execution = json.loads((results / "execution.json").read_text(encoding="utf-8"))
    if execution.get("status") != "completed" or not execution.get("qa_passed"):
        errors.append("T25 execution is not completed with passing execution QA")
    if execution.get("manifest_id") != manifest.manifest_id:
        errors.append("execution manifest_id does not match the supplied manifest")
    if execution.get("scope") != "full":
        errors.append("T26 requires a full-pilot execution")

    graph_paths = sorted((results / "graphs").glob("*.json"))
    graphs = [load_graph_record(path) for path in graph_paths]
    graph_by_id = {graph.graph_id: graph for graph in graphs}
    _check_unique([graph.graph_id for graph in graphs], "graph_id", errors)
    if len(graphs) != manifest.graph_count:
        errors.append(f"graph count is {len(graphs)}; expected {manifest.graph_count}")

    specs = {
        (spec.family, spec.n_nodes, spec.seed): spec for spec in manifest.graph_specs
    }
    regenerated = 0
    for graph in graphs:
        key = (graph.family, graph.n_nodes, graph.generation_seed)
        spec = specs.get(key)
        if spec is None:
            errors.append(f"graph provenance is absent from manifest: {graph.graph_id}")
            continue
        if generate_graph(spec) != graph:
            errors.append(f"graph regeneration mismatch: {graph.graph_id}")
        else:
            regenerated += 1
    checks["reproducibly_regenerated_graphs"] = regenerated

    exact_rows = _load_jsonl(results / "exact" / "exact-results.jsonl")
    feature_rows = _load_jsonl(results / "features" / "graph-features.jsonl")
    _check_unique(
        [str(row.get("graph_id")) for row in exact_rows], "exact graph_id", errors
    )
    _check_unique(
        [str(row.get("graph_id")) for row in feature_rows],
        "feature graph_id",
        errors,
    )
    exact_by_graph = {str(row["graph_id"]): row for row in exact_rows}
    feature_by_graph = {str(row["graph_id"]): row for row in feature_rows}
    if set(exact_by_graph) != set(graph_by_id):
        errors.append("exact-result graph join is not one-to-one and complete")
    if set(feature_by_graph) != set(graph_by_id):
        errors.append("feature graph join is not one-to-one and complete")
    exact_recomputed = 0
    features_recomputed = 0
    for graph_id, graph in graph_by_id.items():
        expected_exact = _json_round_trip(asdict(solve_exact_maxcut(graph)))
        if exact_by_graph.get(graph_id) == expected_exact:
            exact_recomputed += 1
        else:
            errors.append(f"exact-result reproducibility mismatch: {graph_id}")
        if feature_by_graph.get(graph_id) == extract_graph_features(graph).to_dict():
            features_recomputed += 1
        else:
            errors.append(f"feature reproducibility mismatch: {graph_id}")
    checks["recomputed_exact_results"] = exact_recomputed
    checks["recomputed_feature_rows"] = features_recomputed

    trajectory_paths = sorted((results / "trajectories").glob("**/*.jsonl"))
    runs: dict[str, tuple] = {}
    total_evaluations = 0
    for path in trajectory_paths:
        records = load_trajectory_jsonl(path)
        if not records:
            errors.append(f"empty trajectory: {path.relative_to(results)}")
            continue
        run_ids = {record.run_id for record in records}
        if len(run_ids) != 1:
            errors.append(f"multiple run IDs in {path.relative_to(results)}")
            continue
        run_id = next(iter(run_ids))
        if run_id in runs:
            errors.append(f"duplicate run_id: {run_id}")
        runs[run_id] = records
        total_evaluations += len(records)
        if records[0].graph_id not in graph_by_id:
            errors.append(f"trajectory graph join failed: {run_id}")
        if tuple(record.evaluation_index for record in records) != tuple(
            range(1, len(records) + 1)
        ):
            errors.append(f"non-contiguous trajectory: {run_id}")
        if len(records) > manifest.budgets[-1]:
            errors.append(f"trajectory exceeds maximum budget: {run_id}")

    expected_runs = manifest.run_count
    if len(runs) != expected_runs:
        errors.append(f"run count is {len(runs)}; expected {expected_runs}")
    checks["trajectory_files"] = len(trajectory_paths)
    checks["objective_evaluations"] = total_evaluations

    metric_rows = _load_jsonl(results / "metrics" / "run-checkpoints.jsonl")
    metric_keys: list[str] = []
    for row in metric_rows:
        run_id = str(row.get("run_id"))
        budget = int(row.get("budget", -1))
        metric_keys.append(f"{run_id}:{budget}")
        records = runs.get(run_id)
        if records is None:
            errors.append(f"metric run join failed: {run_id}")
            continue
        if row.get("graph_id") != records[0].graph_id:
            errors.append(f"metric graph join failed: {run_id}:{budget}")
        if row.get("exact_optimum") != exact_by_graph[records[0].graph_id]["optimum"]:
            errors.append(f"metric exact join failed: {run_id}:{budget}")
        if row.get("evaluations_available") != min(budget, len(records)):
            errors.append(f"metric budget count failed: {run_id}:{budget}")
    _check_unique(metric_keys, "run/budget metric key", errors)
    expected_metric_rows = expected_runs * len(manifest.budgets)
    if len(metric_rows) != expected_metric_rows:
        errors.append(
            f"run metric count is {len(metric_rows)}; expected {expected_metric_rows}"
        )

    aggregate_rows = _load_jsonl(results / "metrics" / "seed-summaries.jsonl")
    aggregate_keys = [
        f"{row.get('graph_id')}:{row.get('depth')}:{row.get('budget')}"
        for row in aggregate_rows
    ]
    _check_unique(aggregate_keys, "graph/depth/budget aggregate key", errors)
    expected_aggregates = (
        manifest.graph_count * len(manifest.depths) * len(manifest.budgets)
    )
    if len(aggregate_rows) != expected_aggregates:
        errors.append(
            f"aggregate count is {len(aggregate_rows)}; expected {expected_aggregates}"
        )
    for row in aggregate_rows:
        if row.get("graph_id") not in graph_by_id:
            errors.append(f"aggregate graph join failed: {row.get('graph_id')}")
        if row.get("n_seeds") != len(manifest.optimizer_seeds):
            errors.append(f"aggregate seed count failed: {row.get('graph_id')}")

    with (results / "analysis" / "full-summary.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        summary_rows = list(csv.DictReader(stream))
    if len(summary_rows) != expected_aggregates:
        errors.append(
            f"analysis CSV count is {len(summary_rows)}; expected {expected_aggregates}"
        )

    checksum_roots = (
        results / "execution.json",
        results / "graphs",
        results / "exact",
        results / "features",
        results / "trajectories",
        results / "metrics",
        results / "analysis",
    )
    checksum_paths: list[Path] = []
    for root in checksum_roots:
        if root.is_file():
            checksum_paths.append(root)
        else:
            checksum_paths.extend(path for path in root.rglob("*") if path.is_file())
    checksum_paths = sorted(set(checksum_paths))
    checksum_lines = [
        f"{_sha256(path)}  {path.relative_to(results).as_posix()}"
        for path in checksum_paths
    ]
    checksum_path = qa_directory / "checksums.sha256"
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    dataset_digest = hashlib.sha256("\n".join(checksum_lines).encode()).hexdigest()

    exclusions: list[dict[str, str]] = []
    _write_json(qa_directory / "exclusions.json", exclusions)
    report = {
        "schema_version": DATA_QA_SCHEMA_VERSION,
        "passed": not errors,
        "manifest_id": manifest.manifest_id,
        "dataset_sha256": dataset_digest,
        "checksummed_files": len(checksum_lines),
        "checks": checks,
        "expected": {
            "graphs": manifest.graph_count,
            "runs": expected_runs,
            "run_checkpoint_metrics": expected_metric_rows,
            "seed_aggregate_metrics": expected_aggregates,
            "maximum_objective_evaluations": manifest.maximum_objective_evaluations,
        },
        "exclusions": exclusions,
        "errors": errors,
    }
    _write_json(qa_directory / "T26-qa-report.json", report)
    if errors:
        raise RuntimeError("T26 data QA failed; see qa/T26-qa-report.json")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Run T26 full-pilot data QA")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/manifests/pilot-v0.1.json"),
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("results/full-pilot-v0.1"),
    )
    args = parser.parse_args(argv)
    report = run_data_qa(args.manifest, args.results)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
