"""Generate the T24 preliminary best-so-far trajectory figure."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from qaoa_reliability.optimization.schema import TrajectoryRecord
from qaoa_reliability.optimization.serialization import load_trajectory_jsonl

FAMILY_LABELS = {
    "erdos_renyi": "Erdős–Rényi",
    "random_regular": "random regular",
    "watts_strogatz": "Watts–Strogatz",
    "stochastic_block_model": "stochastic block model",
}


def best_so_far(records: Sequence[TrajectoryRecord]) -> tuple[float, ...]:
    """Return the maximization incumbent after every objective evaluation."""

    if not records:
        raise ValueError("trajectory must not be empty")
    values: list[float] = []
    incumbent = float("-inf")
    for record in records:
        incumbent = max(incumbent, record.objective)
        values.append(incumbent)
    return tuple(values)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _find_graph_id(results_directory: Path, family: str, n_nodes: int) -> str:
    feature_rows = _load_jsonl(results_directory / "features" / "graph-features.jsonl")
    matches = [
        row["graph_id"]
        for row in feature_rows
        if row["family"] == family and row["n_nodes"] == n_nodes
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one smoke graph for {family}, n={n_nodes}; got {len(matches)}"
        )
    return str(matches[0])


def create_preliminary_trajectory_figure(
    results_directory: str | Path,
    output_stem: str | Path,
    *,
    family: str = "erdos_renyi",
    n_nodes: int = 10,
) -> dict[str, Any]:
    """Render PNG/SVG trajectory exports plus a machine-readable provenance file."""

    import matplotlib.pyplot as plt

    results = Path(results_directory)
    stem = Path(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    execution = json.loads((results / "execution.json").read_text(encoding="utf-8"))
    graph_id = _find_graph_id(results, family, n_nodes)
    exact_rows = _load_jsonl(results / "exact" / "exact-results.jsonl")
    exact = next((row for row in exact_rows if row["graph_id"] == graph_id), None)
    if exact is None:
        raise ValueError("selected graph has no exact-result row")

    graph_directory = next(
        (
            path
            for path in (results / "trajectories").glob(f"{family}-n{n_nodes}-g*/p1")
            if path.is_dir()
        ),
        None,
    )
    if graph_directory is None:
        raise ValueError("selected graph has no p=1 trajectory directory")
    trajectory_paths = sorted(graph_directory.glob("seed-*.jsonl"))
    if not trajectory_paths:
        raise ValueError("selected graph has no trajectory files")

    figure, axis = plt.subplots(figsize=(8.4, 5.2), constrained_layout=True)
    for path in trajectory_paths:
        records = load_trajectory_jsonl(path)
        values = best_so_far(records)
        axis.step(
            range(1, len(values) + 1),
            values,
            where="post",
            color="#2878B5",
            linewidth=1.25,
            alpha=0.46,
        )

    optimum = float(exact["optimum"])
    target_ratio = float(execution.get("target_ratio", 0.95))
    axis.axhline(
        optimum,
        color="#222222",
        linewidth=1.5,
        linestyle="--",
        label=f"Exact optimum ({optimum:g})",
    )
    axis.axhline(
        target_ratio * optimum,
        color="#D9534F",
        linewidth=1.5,
        linestyle=":",
        label=f"{target_ratio:.0%} target",
    )
    family_label = FAMILY_LABELS.get(family, family.replace("_", " "))
    axis.set(
        title=f"QAOA p=1 best-so-far trajectories: {family_label}, n={n_nodes}",
        xlabel="Counted objective evaluations",
        ylabel="Expected cut value (best so far)",
    )
    axis.grid(axis="both", color="#D9D9D9", linewidth=0.7, alpha=0.65)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, loc="lower right")

    png_path = stem.with_suffix(".png")
    svg_path = stem.with_suffix(".svg")
    figure.savefig(png_path, dpi=180)
    figure.savefig(svg_path)
    plt.close(figure)

    provenance = {
        "figure": "preliminary best-so-far QAOA trajectory",
        "manifest_id": execution["manifest_id"],
        "results_directory": str(results),
        "graph_id": graph_id,
        "family": family,
        "n_nodes": n_nodes,
        "depth": 1,
        "optimizer_seeds": execution["optimizer_seeds"],
        "trajectory_files": [str(path) for path in trajectory_paths],
        "exact_optimum": exact["optimum"],
        "target_ratio": target_ratio,
        "png": str(png_path),
        "svg": str(svg_path),
    }
    provenance_path = stem.with_suffix(".provenance.json")
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return provenance


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Create the T24 preliminary trajectory figure")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-stem", type=Path, required=True)
    parser.add_argument("--family", default="erdos_renyi")
    parser.add_argument("--n-nodes", type=int, default=10)
    args = parser.parse_args(argv)
    provenance = create_preliminary_trajectory_figure(
        args.results,
        args.output_stem,
        family=args.family,
        n_nodes=args.n_nodes,
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
