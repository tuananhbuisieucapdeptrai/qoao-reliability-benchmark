# QAOA Reliability Pilot v0.1 dataset

This immutable snapshot contains the validated mandatory p=1 pilot only. Start
with `dataset-metadata.json`, `manifest.json`, and
`documentation/data-dictionary.md`. Join run rows through `run_id`, graph-level
rows through `graph_id`, and aggregate rows through `(graph_id, depth, budget)`.

Run `sha256sum -c SNAPSHOT.sha256` from this directory to verify every packaged
file. The data and accompanying documentation are released under the MIT
license in `LICENSE`. Exploratory p=2 results are intentionally excluded.
