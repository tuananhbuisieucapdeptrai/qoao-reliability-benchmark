"""Create the three application-ready T29 descriptive pilot figures."""

from __future__ import annotations

import csv
import hashlib
import json
from argparse import ArgumentParser
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

FAMILY_ORDER = (
    "erdos_renyi",
    "random_regular",
    "watts_strogatz",
    "stochastic_block_model",
)
FAMILY_LABELS = {
    "erdos_renyi": "Erdős–Rényi",
    "random_regular": "Random regular",
    "watts_strogatz": "Watts–Strogatz",
    "stochastic_block_model": "Stochastic block",
}
FAMILY_COLORS = {
    "erdos_renyi": "#2878B5",
    "random_regular": "#2A9D6F",
    "watts_strogatz": "#E9A23B",
    "stochastic_block_model": "#C44E52",
}
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261018


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Return mean and deterministic percentile bootstrap bounds."""

    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size < 2 or not np.all(np.isfinite(array)):
        raise ValueError("bootstrap values must contain at least two finite numbers")
    if not 0.0 < confidence < 1.0 or n_resamples < 1:
        raise ValueError("invalid bootstrap configuration")
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(n_resamples, array.size), replace=True)
    means = np.mean(samples, axis=1)
    alpha = (1.0 - confidence) / 2.0
    low, high = np.quantile(means, (alpha, 1.0 - alpha))
    return float(np.mean(array)), float(low), float(high)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"expected non-empty object JSONL: {path}")
    return rows


def _graph_metadata(snapshot: Path) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for path in sorted((snapshot / "graphs").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        metadata[str(row["graph_id"])] = row
    return metadata


def _graph_level_rows(
    run_rows: Sequence[dict[str, Any]],
    graph_metadata: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in run_rows:
        grouped[(str(row["graph_id"]), int(row["budget"]))].append(row)

    graph_rows: list[dict[str, Any]] = []
    for (graph_id, budget), rows in sorted(grouped.items()):
        graph = graph_metadata[graph_id]
        if len(rows) != 10:
            raise ValueError(
                f"expected ten seeds for graph {graph_id}, budget {budget}"
            )
        graph_rows.append(
            {
                "graph_id": graph_id,
                "family": graph["family"],
                "n_nodes": graph["n_nodes"],
                "budget": budget,
                "mean_best_objective": float(
                    np.mean([float(row["best_objective"]) for row in rows])
                ),
                "mean_normalized_gap": float(
                    np.mean([float(row["normalized_gap"]) for row in rows])
                ),
            }
        )
    return graph_rows


def _style_axis(axis) -> None:
    axis.grid(axis="y", color="#D9D9D9", linewidth=0.7, alpha=0.7)
    axis.spines[["top", "right"]].set_visible(False)


def _save_figure(figure, output_stem: Path) -> tuple[Path, Path]:
    png = output_stem.with_suffix(".png")
    svg = output_stem.with_suffix(".svg")
    figure.savefig(png, dpi=200, bbox_inches="tight")
    figure.savefig(svg, bbox_inches="tight")
    return png, svg


def create_pilot_figures(
    snapshot_directory: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Render objective, regret, and family-distribution figures from T28."""

    import matplotlib.pyplot as plt

    snapshot = Path(snapshot_directory)
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"analysis output already exists: {output}")
    output.mkdir(parents=True)

    metadata = json.loads(
        (snapshot / "dataset-metadata.json").read_text(encoding="utf-8")
    )
    if metadata.get("scope") != "mandatory-p1-only":
        raise ValueError("T29 requires the mandatory p=1 snapshot")
    run_metrics_path = snapshot / "metrics" / "run-checkpoints.jsonl"
    run_rows = _load_jsonl(run_metrics_path)
    graph_metadata = _graph_metadata(snapshot)
    graph_rows = _graph_level_rows(run_rows, graph_metadata)
    budgets = tuple(sorted({int(row["budget"]) for row in graph_rows}))
    if budgets != (25, 50, 100):
        raise ValueError(f"unexpected budget checkpoints: {budgets}")

    outputs: list[Path] = []

    figure_data_path = output / "figure-data.csv"
    with figure_data_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(graph_rows[0]))
        writer.writeheader()
        writer.writerows(graph_rows)

    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharex=True)
    for size_index, (axis, n_nodes) in enumerate(zip(axes, (8, 10), strict=True)):
        for family_index, family in enumerate(FAMILY_ORDER):
            means: list[float] = []
            lows: list[float] = []
            highs: list[float] = []
            for budget_index, budget in enumerate(budgets):
                values = [
                    row["mean_best_objective"]
                    for row in graph_rows
                    if row["family"] == family
                    and row["n_nodes"] == n_nodes
                    and row["budget"] == budget
                ]
                mean, low, high = bootstrap_mean_ci(
                    values,
                    seed=BOOTSTRAP_SEED
                    + 100 * size_index
                    + 10 * family_index
                    + budget_index,
                )
                means.append(mean)
                lows.append(low)
                highs.append(high)
            axis.plot(
                budgets,
                means,
                marker="o",
                linewidth=2,
                color=FAMILY_COLORS[family],
                label=FAMILY_LABELS[family],
            )
            axis.fill_between(
                budgets,
                lows,
                highs,
                color=FAMILY_COLORS[family],
                alpha=0.16,
                linewidth=0,
            )
        axis.set_title(f"n = {n_nodes} (5 graphs per family)")
        axis.set_xlabel("Objective-evaluation budget")
        axis.set_xticks(budgets)
        _style_axis(axis)
    axes[0].set_ylabel("Mean best-so-far expected cut value")
    axes[1].legend(frameon=False, fontsize=9, loc="lower right")
    figure.suptitle("Best-so-far QAOA objective versus evaluation budget", fontsize=14)
    png, svg = _save_figure(figure, output / "figure-1-objective-vs-budget")
    outputs.extend((png, svg))
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    for family_index, family in enumerate(FAMILY_ORDER):
        means = []
        lows = []
        highs = []
        for budget_index, budget in enumerate(budgets):
            values = [
                row["mean_normalized_gap"]
                for row in graph_rows
                if row["family"] == family and row["budget"] == budget
            ]
            mean, low, high = bootstrap_mean_ci(
                values,
                seed=BOOTSTRAP_SEED + 1000 + 10 * family_index + budget_index,
            )
            means.append(mean)
            lows.append(low)
            highs.append(high)
        axis.plot(
            budgets,
            means,
            marker="o",
            linewidth=2,
            color=FAMILY_COLORS[family],
            label=FAMILY_LABELS[family],
        )
        axis.fill_between(
            budgets,
            lows,
            highs,
            color=FAMILY_COLORS[family],
            alpha=0.16,
            linewidth=0,
        )
    axis.set(
        title="Normalized regret versus evaluation budget",
        xlabel="Objective-evaluation budget",
        ylabel="Mean normalized gap to exact optimum",
    )
    axis.set_xticks(budgets)
    axis.legend(frameon=False, fontsize=9)
    _style_axis(axis)
    png, svg = _save_figure(figure, output / "figure-2-regret-vs-budget")
    outputs.extend((png, svg))
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9.2, 5.4), constrained_layout=True)
    distribution_values = [
        [
            float(row["normalized_gap"])
            for row in run_rows
            if row["budget"] == 100
            and graph_metadata[row["graph_id"]]["family"] == family
        ]
        for family in FAMILY_ORDER
    ]
    boxplot = axis.boxplot(
        distribution_values,
        tick_labels=[FAMILY_LABELS[family] for family in FAMILY_ORDER],
        patch_artist=True,
        widths=0.58,
        showfliers=False,
        medianprops={"color": "#202020", "linewidth": 1.8},
    )
    for patch_item, family in zip(boxplot["boxes"], FAMILY_ORDER, strict=True):
        patch_item.set_facecolor(FAMILY_COLORS[family])
        patch_item.set_alpha(0.33)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    for family_index, family in enumerate(FAMILY_ORDER, start=1):
        graph_values = [
            row["mean_normalized_gap"]
            for row in graph_rows
            if row["family"] == family and row["budget"] == 100
        ]
        jitter = rng.uniform(-0.12, 0.12, size=len(graph_values))
        axis.scatter(
            family_index + jitter,
            graph_values,
            s=25,
            color=FAMILY_COLORS[family],
            edgecolor="white",
            linewidth=0.5,
            zorder=3,
            label="Graph mean" if family_index == 1 else None,
        )
    axis.set(
        title="Final-budget normalized-gap distributions by graph family",
        xlabel="Graph family (100 runs; 10 graph means per family)",
        ylabel="Normalized gap at budget 100",
    )
    axis.tick_params(axis="x", labelrotation=12)
    axis.legend(frameon=False, loc="upper left")
    _style_axis(axis)
    png, svg = _save_figure(figure, output / "figure-3-family-distributions")
    outputs.extend((png, svg))
    plt.close(figure)

    provenance = {
        "analysis": "T29 descriptive pilot figures",
        "manifest_id": metadata["manifest_id"],
        "source_dataset_sha256": metadata["source_dataset_sha256"],
        "input_run_metrics": str(run_metrics_path),
        "input_run_metrics_sha256": _sha256(run_metrics_path),
        "sample_counts": {
            "graphs": len(graph_metadata),
            "runs": len({row["run_id"] for row in run_rows}),
            "run_checkpoint_rows": len(run_rows),
            "graphs_per_family": 10,
            "runs_per_family": 100,
        },
        "uncertainty": {
            "method": "percentile bootstrap of graph-level seed means",
            "confidence": 0.95,
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
        },
        "outputs": [{"path": str(path), "sha256": _sha256(path)} for path in outputs],
        "figure_data": {
            "path": str(figure_data_path),
            "sha256": _sha256(figure_data_path),
            "rows": len(graph_rows),
        },
    }
    (output / "figure-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return provenance


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Create the T29 pilot figure suite")
    parser.add_argument("--snapshot", type=Path, default=Path("releases/pilot-v0.1"))
    parser.add_argument("--output", type=Path, default=Path("results/T29-analysis"))
    args = parser.parse_args(argv)
    provenance = create_pilot_figures(args.snapshot, args.output)
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
