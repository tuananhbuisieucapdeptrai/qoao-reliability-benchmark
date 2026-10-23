# QAOA Reliability Benchmark

An open-source benchmark for studying the reliability and sample efficiency of
shallow-QAOA parameter optimization under standardized objective-evaluation
budgets.

The initial pilot studies unweighted MaxCut across four graph families. It
records complete optimization trajectories, compares independently seeded
initializations, and evaluates whether graph properties predict reliability on
held-out graph families.

## Project status

The reference implementation, frozen v0.1 protocol, 40-graph/400-run pilot,
independent QA pass, and checksummed dataset release are complete. The scope is
documented in
[`docs/scope.md`](docs/scope.md), and the benchmark contract is documented in
[`docs/protocol.md`](docs/protocol.md).

## Development setup

Create and activate a virtual environment, then install the package with its
development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the quality checks:

```bash
ruff check .
ruff format --check .
pytest
```

Qiskit support is optional during the data-foundation stage:

```bash
python -m pip install -e ".[dev,qiskit]"
```

## Package areas

- `qaoa_reliability.graphs`: canonical graph records, generators, and
  serialization.
- `qaoa_reliability.exact`: exact reference solvers for pilot-sized instances.
- `qaoa_reliability.features`: documented, table-ready graph features.
- `qaoa_reliability.evaluators`: a common result contract, an exact NumPy
  statevector evaluator, and an independently cross-validated Qiskit adapter.
- `qaoa_reliability.optimization`: exact objective-call accounting, append-only
  JSONL trajectories, deterministic repeated seeds, and nested checkpoints.
- `qaoa_reliability.metrics`: regret, normalized gap, seed sensitivity, success
  probability, and evaluations-to-target with exact-optimum provenance.
- `qaoa_reliability.experiments`: validated, content-addressed pilot manifests.

The frozen mandatory pilot is documented in
[`docs/pilot-manifest.md`](docs/pilot-manifest.md) and defined by
[`experiments/manifests/pilot-v0.1.json`](experiments/manifests/pilot-v0.1.json).
The completed frozen full-pilot execution is summarized in
[`docs/T25-full-pilot-report.md`](docs/T25-full-pilot-report.md).
Its independent integrity audit is documented in
[`docs/T26-data-qa-report.md`](docs/T26-data-qa-report.md).
The self-contained, checksummed open dataset is staged in
[`releases/pilot-v0.1`](releases/pilot-v0.1), with release notes in
[`docs/T28-dataset-snapshot.md`](docs/T28-dataset-snapshot.md).
The three-figure descriptive analysis is documented in
[`docs/T29-descriptive-analysis.md`](docs/T29-descriptive-analysis.md).
Family-level reliability and the held-out-family predictive pilot are reported
in [`docs/T30-reliability-analysis.md`](docs/T30-reliability-analysis.md) and
[`docs/T31-predictive-pilot.md`](docs/T31-predictive-pilot.md).
The one-page proposal evidence memo and its claim ledger are available in
[`docs/T32-pilot-evidence-memo.md`](docs/T32-pilot-evidence-memo.md) and
[`docs/T32-claim-evidence.csv`](docs/T32-claim-evidence.csv).

Run the complete frozen pilot into a fresh output directory with:

```bash
PYTHONPATH=src python -m qaoa_reliability.experiments.full \
  --manifest experiments/manifests/pilot-v0.1.json \
  --output results/full-pilot-v0.1
```

After the full run completes, reproduce the T26 audit with:

```bash
PYTHONPATH=src python -m qaoa_reliability.experiments.qa \
  --manifest experiments/manifests/pilot-v0.1.json \
  --results results/full-pilot-v0.1
```

## Reproduce a smoke pilot

Install the research dependencies and run the frozen eight-graph smoke pilot
into a fresh directory:

```bash
python -m pip install -e ".[dev,research]"
PYTHONPATH=src python -m qaoa_reliability.experiments.smoke \
  --manifest experiments/manifests/pilot-v0.1.json \
  --output results/smoke-pilot-v0.1
```

The smoke command prints a completed execution record. The validated reference
run reported the following headline output:

```text
status: completed
qa_passed: true
graphs: 8
runs: 80
trajectory_records: 3264
run_checkpoint_metrics: 240
seed_aggregate_metrics: 24
runtime_seconds: 9.96
```

The exact number of trajectory records and runtime can vary with SciPy and the
execution environment because COBYLA may converge before the 100-call ceiling.
The graph identities, seeds, protocol, and maximum budgets remain fixed.

## Data-foundation example

```python
from qaoa_reliability.exact.maxcut import solve_exact_maxcut
from qaoa_reliability.features import extract_graph_features
from qaoa_reliability.graphs.generators import generate_graph
from qaoa_reliability.graphs.schema import GraphGenerationSpec

spec = GraphGenerationSpec(
    family="erdos_renyi",
    n_nodes=8,
    seed=42,
    parameters={"edge_probability": 0.4},
)

record = generate_graph(spec)
exact = solve_exact_maxcut(record)
features = extract_graph_features(record)

print(record.graph_id, exact.optimum, features.to_dict())
```

Undefined assortativity and disconnected-graph diameter are represented by
`None`; degree standard deviation uses the population convention (`ddof=0`).

## One counted QAOA objective evaluation

The following is one objective evaluation: one graph and one complete QAOA
parameter vector produce one expected cut value.

```python
from qaoa_reliability.evaluators import NumpyStatevectorEvaluator
from qaoa_reliability.graphs.generators import generate_graph
from qaoa_reliability.graphs.schema import GraphGenerationSpec

graph = generate_graph(
    GraphGenerationSpec(
        family="erdos_renyi",
        n_nodes=4,
        seed=42,
        parameters={"edge_probability": 0.6},
    )
)
result = NumpyStatevectorEvaluator().evaluate(
    graph=graph,
    depth=1,
    parameters=(0.7, 0.3),  # (gamma_1, beta_1)
)

print(result.objective)
print(result.evaluation_id)
```

The optional Qiskit implementation uses the same call and result schema:

```python
from qaoa_reliability.evaluators.qiskit_statevector import (
    QiskitStatevectorEvaluator,
)

qiskit_result = QiskitStatevectorEvaluator().evaluate(
    graph=graph,
    depth=1,
    parameters=(0.7, 0.3),
)
```

For depth `p`, parameters are ordered as all cost angles followed by all mixer
angles: `(gamma_1, ..., gamma_p, beta_1, ..., beta_p)`. The NumPy and Qiskit
implementations are tested against each other at both `p=1` and `p=2`.

This call consumes exactly one unit of the benchmark's objective-evaluation
budget. Internal edge summation still belongs to that one evaluation. Graph
generation, exact MaxCut calculation, feature extraction, logging, callbacks,
and serialization consume no objective-evaluation units. Repeating the call,
even with identical parameters, consumes another unit when it occurs inside an
optimization run; the deterministic `evaluation_id` identifies the request but
is not a budget counter.

## Fixed-budget optimization

One maximum-budget run can supply every smaller checkpoint without rerunning
the objective:

```python
from qaoa_reliability.optimization import run_multi_seed

experiment = run_multi_seed(
    graph=graph,
    evaluator=NumpyStatevectorEvaluator(),
    depth=1,
    optimizer_seeds=(0, 1, 2),
    max_evaluations=100,
    checkpoints=(25, 50, 100),
    trajectory_directory="results/trajectories",
)
```

Every completed evaluator call is flushed as a schema-validated JSONL record.
Callbacks, logging, persistence, and checkpoint summaries do not consume the
objective-evaluation budget.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
