# Pilot v0.1 schema and validation contract

The snapshot uses strict JSON for JSON/JSONL artifacts and UTF-8 CSV with a
header row for the analysis table. JSONL contains exactly one JSON object per
non-empty line. NaN and infinity are forbidden.

Machine-readable field inventories and schema versions are included in
`schema-versions.json`. The normative validators live in these package modules:

- graph identity and records: `qaoa_reliability.graphs.schema`;
- trajectory records: `qaoa_reliability.optimization.schema`;
- exact results: `qaoa_reliability.exact.maxcut`;
- feature records: `qaoa_reliability.features.graph_features`;
- run and aggregate metrics: `qaoa_reliability.metrics.reliability`;
- frozen experiment contract: `qaoa_reliability.experiments.manifest`.

Relational keys are:

- `graph_id` for graph-level tables;
- `run_id` for run-level metrics and trajectories;
- `(run_id, budget)` for checkpoint rows;
- `(graph_id, depth, budget)` for seed aggregates.

The release is accepted only after the T26 validator recomputes graph, exact,
and feature outputs; validates all joins and budget counts; declares exclusions;
and emits file checksums.
