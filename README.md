# QAOA Reliability Benchmark

An open-source benchmark for studying the reliability and sample efficiency of
shallow-QAOA parameter optimization under standardized objective-evaluation
budgets.

The initial pilot studies unweighted MaxCut on several graph families. It will
record complete optimization trajectories, compare independently seeded
initializations, and evaluate whether graph properties predict reliability on
held-out graph families.

## Project status

The benchmark protocol is being specified and the Python reference
implementation is under development. The current scope is documented in
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

## Planned package areas

- `qaoa_reliability.graphs`: canonical graph records, generators, and
  serialization.
- `qaoa_reliability.exact`: exact reference solvers for pilot-sized instances.
- `qaoa_reliability.features`: documented, table-ready graph features.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).

