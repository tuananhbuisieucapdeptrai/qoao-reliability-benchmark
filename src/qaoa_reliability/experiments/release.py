"""Stage a self-contained, checksummed T28 pilot dataset snapshot."""

from __future__ import annotations

import hashlib
import json
import shutil
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA_VERSION = "1.0"
DATA_DIRECTORIES = (
    "graphs",
    "exact",
    "features",
    "trajectories",
    "metrics",
    "analysis",
)

SCHEMA_FIELDS = {
    "graph_record": {
        "version": "1.0",
        "required": [
            "schema_version",
            "graph_id",
            "family",
            "n_nodes",
            "edges",
            "generation_seed",
            "generation_parameters",
        ],
    },
    "trajectory_record": {
        "version": "1.0",
        "required": [
            "schema_version",
            "run_id",
            "evaluation_index",
            "timestamp_utc",
            "graph_id",
            "depth",
            "optimizer_seed",
            "parameters",
            "objective",
            "evaluation_id",
            "evaluator",
            "evaluator_version",
            "backend_metadata",
        ],
    },
    "exact_result": {
        "version": "1.0",
        "required": [
            "graph_id",
            "optimum",
            "representative_bitstring",
            "n_optimal_assignments",
            "assignments_evaluated",
            "solver",
            "solver_version",
        ],
    },
    "graph_feature": {
        "version": "1.0",
        "required": [
            "feature_schema_version",
            "graph_id",
            "family",
            "n_nodes",
            "n_edges",
        ],
    },
    "run_checkpoint_metrics": {
        "version": "1.0",
        "required": [
            "run_id",
            "graph_id",
            "depth",
            "optimizer_seed",
            "budget",
            "evaluations_available",
            "best_objective",
            "exact_optimum",
            "regret",
            "normalized_gap",
            "success",
        ],
    },
    "seed_aggregate_metrics": {
        "version": "1.0",
        "required": [
            "graph_id",
            "depth",
            "budget",
            "n_seeds",
            "mean_best_objective",
            "mean_normalized_gap",
            "success_probability",
        ],
    },
}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_dataset_snapshot(
    *,
    results_directory: str | Path,
    manifest_path: str | Path,
    license_path: str | Path,
    data_dictionary_path: str | Path,
    schemas_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Copy only validated mandatory-pilot files into a fresh release directory."""

    source = Path(results_directory)
    target = Path(destination)
    if target.exists():
        raise FileExistsError(f"snapshot destination already exists: {target}")

    qa_report = json.loads(
        (source / "qa" / "T26-qa-report.json").read_text(encoding="utf-8")
    )
    exclusions = json.loads(
        (source / "qa" / "exclusions.json").read_text(encoding="utf-8")
    )
    execution = json.loads((source / "execution.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not qa_report.get("passed") or qa_report.get("errors"):
        raise ValueError("source dataset has not passed T26 QA")
    if exclusions != qa_report.get("exclusions"):
        raise ValueError("exclusion register does not match the T26 QA report")
    if manifest.get("manifest_id") != qa_report.get("manifest_id"):
        raise ValueError("manifest does not match the validated source dataset")
    if execution.get("scope") != "full" or execution.get("status") != "completed":
        raise ValueError("source is not a completed full-pilot execution")

    target.mkdir(parents=True)
    for directory in DATA_DIRECTORIES:
        shutil.copytree(source / directory, target / directory)
    shutil.copytree(source / "qa", target / "qa")
    shutil.copy2(source / "execution.json", target / "execution.json")
    shutil.copy2(manifest_path, target / "manifest.json")
    shutil.copy2(license_path, target / "LICENSE")
    documentation = target / "documentation"
    documentation.mkdir()
    shutil.copy2(data_dictionary_path, documentation / "data-dictionary.md")
    shutil.copy2(schemas_path, documentation / "schemas.md")
    _write_json(target / "schema-versions.json", SCHEMA_FIELDS)

    metadata = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "name": "qaoa-reliability-pilot-v0.1",
        "scope": "mandatory-p1-only",
        "manifest_id": manifest["manifest_id"],
        "protocol_version": manifest["protocol_version"],
        "graph_count": execution["counts"]["graphs"],
        "run_count": execution["counts"]["runs"],
        "objective_evaluations": execution["counts"]["trajectory_records"],
        "optimizer_seeds": execution["optimizer_seeds"],
        "depths": execution["depths"],
        "budgets": execution["budgets"],
        "evaluator": execution["evaluator"],
        "optimizer": execution["optimizer"],
        "target_ratio": execution["target_ratio"],
        "source_dataset_sha256": qa_report["dataset_sha256"],
        "exclusion_count": len(exclusions),
        "license": "MIT",
        "exploratory_p2_included": False,
    }
    _write_json(target / "dataset-metadata.json", metadata)

    readme = """# QAOA Reliability Pilot v0.1 dataset

This immutable snapshot contains the validated mandatory p=1 pilot only. Start
with `dataset-metadata.json`, `manifest.json`, and
`documentation/data-dictionary.md`. Join run rows through `run_id`, graph-level
rows through `graph_id`, and aggregate rows through `(graph_id, depth, budget)`.

Run `sha256sum -c SNAPSHOT.sha256` from this directory to verify every packaged
file. The data and accompanying documentation are released under the MIT
license in `LICENSE`. Exploratory p=2 results are intentionally excluded.
"""
    (target / "README.md").write_text(readme, encoding="utf-8")

    packaged_files = sorted(
        path
        for path in target.rglob("*")
        if path.is_file() and path.name != "SNAPSHOT.sha256"
    )
    checksum_lines = [
        f"{_sha256(path)}  {path.relative_to(target).as_posix()}"
        for path in packaged_files
    ]
    (target / "SNAPSHOT.sha256").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    snapshot_sha256 = hashlib.sha256("\n".join(checksum_lines).encode()).hexdigest()
    return {
        "destination": str(target),
        "manifest_id": metadata["manifest_id"],
        "packaged_files": len(packaged_files),
        "snapshot_sha256": snapshot_sha256,
        "exclusions": exclusions,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Stage the T28 pilot dataset snapshot")
    parser.add_argument("--results", type=Path, default=Path("results/full-pilot-v0.1"))
    parser.add_argument(
        "--manifest", type=Path, default=Path("experiments/manifests/pilot-v0.1.json")
    )
    parser.add_argument("--license", type=Path, default=Path("LICENSE"))
    parser.add_argument(
        "--data-dictionary",
        type=Path,
        default=Path("docs/dataset/data-dictionary.md"),
    )
    parser.add_argument("--schemas", type=Path, default=Path("docs/dataset/schemas.md"))
    parser.add_argument("--destination", type=Path, default=Path("releases/pilot-v0.1"))
    args = parser.parse_args(argv)
    result = stage_dataset_snapshot(
        results_directory=args.results,
        manifest_path=args.manifest,
        license_path=args.license,
        data_dictionary_path=args.data_dictionary,
        schemas_path=args.schemas,
        destination=args.destination,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
