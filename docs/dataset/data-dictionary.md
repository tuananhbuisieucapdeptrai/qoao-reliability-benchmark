# Pilot v0.1 data dictionary

All identifiers beginning with `sha256:` are lowercase SHA-256 content or
request identifiers. Angles are radians. Objective values are expected
unweighted MaxCut values; larger is better. Null means unavailable or not
reached, never numerical zero.

## `graphs/*.json`

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Graph-record schema version. |
| `graph_id` | string | Hash of canonical node count and sorted undirected edges. |
| `family` | string | Generator family. |
| `n_nodes` | integer | Number of labeled vertices, numbered `0..n_nodes-1`. |
| `edges` | array | Canonical sorted `[u, v]` pairs with `u < v`. |
| `generation_seed` | integer | Seed from the frozen manifest. |
| `generation_parameters` | object | Family-specific generator parameters. |

## `exact/exact-results.jsonl`

| Field | Type | Meaning |
| --- | --- | --- |
| `graph_id` | string | Join key to the graph record. |
| `optimum` | integer | Exact maximum cut value. |
| `representative_bitstring` | array | Lexicographically first optimum with vertex 0 fixed to 0. |
| `n_optimal_assignments` | integer | Count in the full bitstring space, including complements. |
| `assignments_evaluated` | integer | Symmetry-reduced assignments enumerated. |
| `solver`, `solver_version` | string | Exact-solver provenance. |

## `features/graph-features.jsonl`

| Field | Type | Meaning |
| --- | --- | --- |
| `feature_schema_version` | string | Feature schema version. |
| `graph_id`, `family`, `n_nodes` | mixed | Graph join key and provenance. |
| `n_edges`, `density` | numeric | Edge count and simple-graph density. |
| `degree_mean`, `degree_std`, `degree_min`, `degree_max` | numeric | Population degree statistics (`ddof=0`). |
| `triangle_count` | integer | Number of undirected triangles. |
| `average_clustering` | number | Mean local clustering coefficient. |
| `degree_assortativity` | number or null | Degree assortativity; null when undefined. |
| `is_connected`, `n_connected_components` | mixed | Connectivity summary. |
| `diameter` | integer or null | Diameter in edges; null for disconnected graphs. |

## `trajectories/**/seed-*.jsonl`

Each line is one counted objective evaluation.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Trajectory schema version. |
| `run_id` | string | Join key for one graph/depth/seed/budget run. |
| `evaluation_index` | integer | One-based counted call order within the run. |
| `timestamp_utc` | string | ISO 8601 completion timestamp. |
| `graph_id` | string | Join key to graph, exact, and feature rows. |
| `depth` | integer | QAOA depth `p`. |
| `optimizer_seed` | integer | Initial-parameter seed. |
| `parameters` | array | All gammas followed by all betas; length `2 * depth`. |
| `objective` | number | Expected cut value returned by the evaluator. |
| `evaluation_id` | string | Deterministic hash of the evaluation request. |
| `evaluator`, `evaluator_version` | string | Objective implementation provenance. |
| `backend_metadata` | object | Evaluator-specific execution metadata. |

## `metrics/run-checkpoints.jsonl`

| Field | Type | Meaning |
| --- | --- | --- |
| `run_id`, `graph_id`, `depth`, `optimizer_seed` | mixed | Run and graph joins. |
| `budget` | integer | Requested nested checkpoint ceiling. |
| `evaluations_available` | integer | `min(budget, completed trajectory length)`. |
| `best_objective`, `best_evaluation_index` | numeric | Best prefix result and first index attaining it. |
| `exact_optimum`, `optimum_source` | mixed | Joined exact reference and solver provenance. |
| `regret` | number | `exact_optimum - best_objective`. |
| `normalized_gap` | number | Regret divided by positive exact optimum. |
| `target_ratio`, `target_objective` | number | Frozen success threshold and absolute target. |
| `success` | boolean | Whether the prefix reached the target. |
| `evaluations_to_target` | integer or null | First reaching index, or null if never reached. |

## `metrics/seed-summaries.jsonl`

One row summarizes all optimizer seeds for a graph, depth, and budget.

| Field | Type | Meaning |
| --- | --- | --- |
| `graph_id`, `depth`, `budget` | mixed | Unique aggregate key. |
| `n_seeds` | integer | Number of included optimizer seeds. |
| `exact_optimum`, `optimum_source`, `target_ratio` | mixed | Shared references. |
| `mean_best_objective`, `population_std_best_objective` | number | Across-seed objective statistics. |
| `min_best_objective`, `max_best_objective`, `best_objective_range` | number | Across-seed bounds and range. |
| `mean_regret`, `mean_normalized_gap` | number | Across-seed error summaries. |
| `successes`, `success_probability` | numeric | Successful seeds and their proportion. |
| `mean_evaluations_to_target` | number or null | Success-conditioned mean reaching time. |

## `analysis/full-summary.csv`

This is the flat analysis form of `seed-summaries.jsonl`. It adds `manifest_id`,
`family`, `n_nodes`, and `graph_seed` so each aggregate row directly exposes its
protocol and graph provenance.

## Row tracing

For a run-checkpoint row, join `run_id` to a trajectory file, then join its
`graph_id` to graph, exact, and feature rows. For an aggregate row, join its
`graph_id` to those same graph-level tables and use `depth` plus `budget` as the
analysis key. `dataset-metadata.json` binds every file to the frozen manifest,
protocol version, evaluator, optimizer, seed set, and licensing statement.
