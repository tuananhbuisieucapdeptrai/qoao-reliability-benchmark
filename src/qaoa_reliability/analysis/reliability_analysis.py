"""T30 family-level seed sensitivity and success analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from qaoa_reliability.analysis.pilot_figures import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    FAMILY_COLORS,
    FAMILY_LABELS,
    FAMILY_ORDER,
    bootstrap_mean_ci,
)


def wilson_interval(
    successes: int, trials: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Return a two-sided Wilson binomial proportion interval."""

    if trials < 1 or not 0 <= successes <= trials:
        raise ValueError("successes and trials are inconsistent")
    proportion = successes / trials
    denominator = 1.0 + z**2 / trials
    center = (proportion + z**2 / (2.0 * trials)) / denominator
    half_width = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / trials + z**2 / (4.0 * trials**2))
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_reliability_analysis(
    snapshot_directory: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Create T30 tables, figure, and provenance from the mandatory snapshot."""

    import matplotlib.pyplot as plt

    snapshot = Path(snapshot_directory)
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"analysis output already exists: {output}")
    output.mkdir(parents=True)

    metadata = json.loads(
        (snapshot / "dataset-metadata.json").read_text(encoding="utf-8")
    )
    features = _load_jsonl(snapshot / "features" / "graph-features.jsonl")
    aggregates_path = snapshot / "metrics" / "seed-summaries.jsonl"
    runs_path = snapshot / "metrics" / "run-checkpoints.jsonl"
    aggregates = _load_jsonl(aggregates_path)
    runs = _load_jsonl(runs_path)
    family_by_graph = {row["graph_id"]: row["family"] for row in features}
    budgets = tuple(sorted({int(row["budget"]) for row in aggregates}))

    table_rows: list[dict[str, Any]] = []
    for family_index, family in enumerate(FAMILY_ORDER):
        for budget_index, budget in enumerate(budgets):
            graph_rows = [
                row
                for row in aggregates
                if family_by_graph[row["graph_id"]] == family
                and row["budget"] == budget
            ]
            run_rows = [
                row
                for row in runs
                if family_by_graph[row["graph_id"]] == family
                and row["budget"] == budget
            ]
            if len(graph_rows) != 10 or len(run_rows) != 100:
                raise ValueError("unexpected family sample counts")

            gap_mean, gap_low, gap_high = bootstrap_mean_ci(
                [float(row["mean_normalized_gap"]) for row in graph_rows],
                seed=BOOTSTRAP_SEED + 100 * family_index + budget_index,
            )
            normalized_ranges = [
                float(row["best_objective_range"]) / float(row["exact_optimum"])
                for row in graph_rows
            ]
            range_mean, range_low, range_high = bootstrap_mean_ci(
                normalized_ranges,
                seed=BOOTSTRAP_SEED + 1000 + 100 * family_index + budget_index,
            )
            successes = sum(bool(row["success"]) for row in run_rows)
            success_low, success_high = wilson_interval(successes, len(run_rows))
            evaluations_to_target = [
                int(row["evaluations_to_target"])
                for row in run_rows
                if row["evaluations_to_target"] is not None
            ]
            table_rows.append(
                {
                    "family": family,
                    "budget": budget,
                    "n_graphs": len(graph_rows),
                    "n_runs": len(run_rows),
                    "n_optimizer_seeds_per_graph": graph_rows[0]["n_seeds"],
                    "mean_normalized_gap": gap_mean,
                    "mean_normalized_gap_ci95_low": gap_low,
                    "mean_normalized_gap_ci95_high": gap_high,
                    "mean_normalized_seed_range": range_mean,
                    "mean_normalized_seed_range_ci95_low": range_low,
                    "mean_normalized_seed_range_ci95_high": range_high,
                    "successes": successes,
                    "success_probability": successes / len(run_rows),
                    "success_probability_wilson95_low": success_low,
                    "success_probability_wilson95_high": success_high,
                    "successful_evaluations_to_target_count": len(
                        evaluations_to_target
                    ),
                    "mean_evaluations_to_target": (
                        sum(evaluations_to_target) / len(evaluations_to_target)
                        if evaluations_to_target
                        else None
                    ),
                }
            )

    table_path = output / "family-reliability.csv"
    with table_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table_rows[0]))
        writer.writeheader()
        writer.writerows(table_rows)

    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.8), constrained_layout=True)
    for family in FAMILY_ORDER:
        rows = [row for row in table_rows if row["family"] == family]
        x = [row["budget"] for row in rows]
        y = [row["mean_normalized_seed_range"] for row in rows]
        low = [row["mean_normalized_seed_range_ci95_low"] for row in rows]
        high = [row["mean_normalized_seed_range_ci95_high"] for row in rows]
        axes[0].plot(
            x,
            y,
            marker="o",
            linewidth=2,
            color=FAMILY_COLORS[family],
            label=FAMILY_LABELS[family],
        )
        axes[0].fill_between(x, low, high, color=FAMILY_COLORS[family], alpha=0.16)
    axes[0].set(
        title="Seed sensitivity by family",
        xlabel="Objective-evaluation budget",
        ylabel="Mean normalized best-objective range",
    )
    axes[0].set_xticks(budgets)
    axes[0].legend(frameon=False, fontsize=8)

    final_rows = [row for row in table_rows if row["budget"] == 100]
    x_positions = list(range(len(FAMILY_ORDER)))
    probabilities = [row["success_probability"] for row in final_rows]
    lower = [row["success_probability_wilson95_low"] for row in final_rows]
    upper = [row["success_probability_wilson95_high"] for row in final_rows]
    axes[1].bar(
        x_positions,
        probabilities,
        color=[FAMILY_COLORS[family] for family in FAMILY_ORDER],
        alpha=0.55,
    )
    axes[1].errorbar(
        x_positions,
        probabilities,
        yerr=[
            [
                max(0.0, probability - bound)
                for probability, bound in zip(probabilities, lower, strict=True)
            ],
            [
                max(0.0, bound - probability)
                for probability, bound in zip(probabilities, upper, strict=True)
            ],
        ],
        fmt="none",
        ecolor="#303030",
        capsize=5,
        linewidth=1.5,
    )
    axes[1].set(
        title="95%-target success at budget 100",
        ylabel="Success probability (Wilson 95% interval)",
        xticks=x_positions,
        xticklabels=[FAMILY_LABELS[family] for family in FAMILY_ORDER],
    )
    axes[1].tick_params(axis="x", labelrotation=18)
    axes[1].set_ylim(0.0, max(0.05, max(upper) * 1.25))
    for axis in axes:
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.7, alpha=0.7)
        axis.spines[["top", "right"]].set_visible(False)

    figure_path_png = output / "reliability-by-family.png"
    figure_path_svg = output / "reliability-by-family.svg"
    figure.savefig(figure_path_png, dpi=200, bbox_inches="tight")
    figure.savefig(figure_path_svg, bbox_inches="tight")
    plt.close(figure)

    report = {
        "analysis": "T30 reliability analysis",
        "manifest_id": metadata["manifest_id"],
        "source_dataset_sha256": metadata["source_dataset_sha256"],
        "sample_counts": {
            "graphs": 40,
            "runs": 400,
            "graphs_per_family": 10,
            "runs_per_family": 100,
            "seeds_per_graph": 10,
        },
        "uncertainty": {
            "gap_and_seed_sensitivity": "95% graph-level percentile bootstrap",
            "success_probability": "95% run-level Wilson interval",
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "total_successes": sum(bool(row["success"]) for row in runs),
        "evaluations_to_target_estimable": any(
            row["evaluations_to_target"] is not None for row in runs
        ),
        "artifacts": {
            "table": {"path": str(table_path), "sha256": _sha256(table_path)},
            "png": {
                "path": str(figure_path_png),
                "sha256": _sha256(figure_path_png),
            },
            "svg": {
                "path": str(figure_path_svg),
                "sha256": _sha256(figure_path_svg),
            },
        },
        "inputs": {
            "seed_summaries_sha256": _sha256(aggregates_path),
            "run_checkpoints_sha256": _sha256(runs_path),
        },
    }
    (output / "reliability-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Create the T30 reliability analysis")
    parser.add_argument("--snapshot", type=Path, default=Path("releases/pilot-v0.1"))
    parser.add_argument("--output", type=Path, default=Path("results/T30-analysis"))
    args = parser.parse_args(argv)
    report = create_reliability_analysis(args.snapshot, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
