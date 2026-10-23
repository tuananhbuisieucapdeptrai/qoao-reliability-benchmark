"""T31 leakage-safe leave-one-family-out predictive pilot."""

from __future__ import annotations

import csv
import hashlib
import json
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from qaoa_reliability.analysis.pilot_figures import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    FAMILY_COLORS,
    FAMILY_LABELS,
    FAMILY_ORDER,
)

BASELINE_FEATURES = ("n_nodes", "density")
INTERPRETABLE_FEATURES = (
    "n_nodes",
    "density",
    "degree_std",
    "triangle_count",
    "average_clustering",
    "degree_assortativity",
    "diameter",
)
TARGET = "mean_normalized_gap_at_budget_100"


def paired_mae_improvement_ci(
    baseline_errors: Sequence[float],
    expanded_errors: Sequence[float],
    *,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Bootstrap baseline-minus-expanded absolute-error improvement."""

    baseline = np.asarray(baseline_errors, dtype=float)
    expanded = np.asarray(expanded_errors, dtype=float)
    if (
        baseline.shape != expanded.shape
        or baseline.ndim != 1
        or baseline.size < 2
        or not np.all(np.isfinite(baseline))
        or not np.all(np.isfinite(expanded))
    ):
        raise ValueError("paired errors must be equal-length finite vectors")
    differences = baseline - expanded
    rng = np.random.default_rng(seed)
    samples = rng.choice(
        differences, size=(n_resamples, differences.size), replace=True
    )
    means = np.mean(samples, axis=1)
    low, high = np.quantile(means, (0.025, 0.975))
    return float(np.mean(differences)), float(low), float(high)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matrix(rows: Sequence[dict[str, Any]], features: Sequence[str]) -> np.ndarray:
    return np.asarray(
        [
            [
                np.nan if row.get(feature) is None else float(row[feature])
                for feature in features
            ]
            for row in rows
        ],
        dtype=float,
    )


def _pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=1.0)),
        ]
    )


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "r2": float(r2_score(actual, predicted)),
    }


def create_predictive_analysis(
    snapshot_directory: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Compare baseline and interpretable models under held-out-family CV."""

    import matplotlib.pyplot as plt

    snapshot = Path(snapshot_directory)
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"analysis output already exists: {output}")
    output.mkdir(parents=True)

    metadata = json.loads(
        (snapshot / "dataset-metadata.json").read_text(encoding="utf-8")
    )
    features_path = snapshot / "features" / "graph-features.jsonl"
    targets_path = snapshot / "metrics" / "seed-summaries.jsonl"
    feature_rows = _load_jsonl(features_path)
    target_rows = [row for row in _load_jsonl(targets_path) if row["budget"] == 100]
    target_by_graph = {
        row["graph_id"]: row["mean_normalized_gap"] for row in target_rows
    }
    rows = [row for row in feature_rows if row["graph_id"] in target_by_graph]
    if len(rows) != 40 or len(target_by_graph) != 40:
        raise ValueError("T31 requires exactly 40 joined graph outcomes")

    actual = np.asarray([float(target_by_graph[row["graph_id"]]) for row in rows])
    predictions = {
        "size_density_baseline": np.full(len(rows), np.nan),
        "interpretable_graph_features": np.full(len(rows), np.nan),
    }
    feature_sets = {
        "size_density_baseline": BASELINE_FEATURES,
        "interpretable_graph_features": INTERPRETABLE_FEATURES,
    }
    fold_rows: list[dict[str, Any]] = []
    coefficient_rows: list[dict[str, Any]] = []

    for family in FAMILY_ORDER:
        test_indices = np.asarray(
            [index for index, row in enumerate(rows) if row["family"] == family]
        )
        train_indices = np.asarray(
            [index for index, row in enumerate(rows) if row["family"] != family]
        )
        if len(test_indices) != 10 or len(train_indices) != 30:
            raise ValueError("each held-out-family fold must contain 30/10 graphs")

        for model_name, model_features in feature_sets.items():
            matrix = _matrix(rows, model_features)
            model = _pipeline()
            model.fit(matrix[train_indices], actual[train_indices])
            predicted = model.predict(matrix[test_indices])
            predictions[model_name][test_indices] = predicted
            fold_rows.append(
                {
                    "held_out_family": family,
                    "model": model_name,
                    "n_train": len(train_indices),
                    "n_test": len(test_indices),
                    **_metrics(actual[test_indices], predicted),
                }
            )
            coefficients = model.named_steps["ridge"].coef_
            for feature, coefficient in zip(model_features, coefficients, strict=True):
                coefficient_rows.append(
                    {
                        "held_out_family": family,
                        "model": model_name,
                        "feature": feature,
                        "standardized_coefficient": float(coefficient),
                    }
                )

    if any(np.any(~np.isfinite(values)) for values in predictions.values()):
        raise RuntimeError("leave-one-family-out predictions are incomplete")

    prediction_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        prediction_rows.append(
            {
                "graph_id": row["graph_id"],
                "family": row["family"],
                "n_nodes": row["n_nodes"],
                "actual_mean_normalized_gap": actual[index],
                "baseline_prediction": predictions["size_density_baseline"][index],
                "expanded_prediction": predictions["interpretable_graph_features"][
                    index
                ],
            }
        )

    pooled_metrics = {
        model_name: _metrics(actual, predicted)
        for model_name, predicted in predictions.items()
    }
    baseline_errors = np.abs(actual - predictions["size_density_baseline"])
    expanded_errors = np.abs(actual - predictions["interpretable_graph_features"])
    improvement, improvement_low, improvement_high = paired_mae_improvement_ci(
        baseline_errors, expanded_errors
    )

    def write_csv(path: Path, values: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)

    predictions_path = output / "held-out-family-predictions.csv"
    folds_path = output / "fold-metrics.csv"
    coefficients_path = output / "standardized-coefficients.csv"
    write_csv(predictions_path, prediction_rows)
    write_csv(folds_path, fold_rows)
    write_csv(coefficients_path, coefficient_rows)

    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.8), sharex=True, sharey=True)
    limits = (
        float(min(np.min(actual), *(np.min(value) for value in predictions.values()))),
        float(max(np.max(actual), *(np.max(value) for value in predictions.values()))),
    )
    padding = 0.04 * (limits[1] - limits[0])
    limits = (limits[0] - padding, limits[1] + padding)
    for axis, (model_name, predicted) in zip(axes, predictions.items(), strict=True):
        for family in FAMILY_ORDER:
            indices = [
                index for index, row in enumerate(rows) if row["family"] == family
            ]
            axis.scatter(
                actual[indices],
                predicted[indices],
                s=42,
                alpha=0.82,
                color=FAMILY_COLORS[family],
                edgecolor="white",
                linewidth=0.5,
                label=FAMILY_LABELS[family],
            )
        axis.plot(limits, limits, "--", color="#303030", linewidth=1.2)
        axis.set(
            title=(
                "Size + density baseline"
                if model_name == "size_density_baseline"
                else "Interpretable graph features"
            ),
            xlabel="Observed mean normalized gap",
            xlim=limits,
            ylim=limits,
        )
        axis.grid(color="#D9D9D9", linewidth=0.7, alpha=0.7)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Held-out-family prediction")
    axes[1].legend(frameon=False, fontsize=8, loc="upper left")
    figure.suptitle("Leave-one-family-out reliability prediction", fontsize=14)
    figure_path_png = output / "held-out-family-predictions.png"
    figure_path_svg = output / "held-out-family-predictions.svg"
    figure.savefig(figure_path_png, dpi=200, bbox_inches="tight")
    figure.savefig(figure_path_svg, bbox_inches="tight")
    plt.close(figure)

    report = {
        "analysis": "T31 held-out-family predictive pilot",
        "target": TARGET,
        "manifest_id": metadata["manifest_id"],
        "source_dataset_sha256": metadata["source_dataset_sha256"],
        "validation": {
            "method": "leave-one-family-out",
            "folds": 4,
            "train_graphs_per_fold": 30,
            "test_graphs_per_fold": 10,
            "preprocessing": (
                "median imputation and standardization fit on training fold only"
            ),
            "estimator": "Ridge(alpha=1.0)",
        },
        "feature_sets": {name: list(values) for name, values in feature_sets.items()},
        "pooled_metrics": pooled_metrics,
        "paired_mae_improvement_baseline_minus_expanded": {
            "mean": improvement,
            "ci95_low": improvement_low,
            "ci95_high": improvement_high,
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
        },
        "artifacts": {
            path.name: _sha256(path)
            for path in (
                predictions_path,
                folds_path,
                coefficients_path,
                figure_path_png,
                figure_path_svg,
            )
        },
        "inputs": {
            "features_sha256": _sha256(features_path),
            "seed_summaries_sha256": _sha256(targets_path),
        },
    }
    (output / "predictive-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Create the T31 predictive pilot")
    parser.add_argument("--snapshot", type=Path, default=Path("releases/pilot-v0.1"))
    parser.add_argument("--output", type=Path, default=Path("results/T31-analysis"))
    args = parser.parse_args(argv)
    report = create_predictive_analysis(args.snapshot, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
