# T28 open dataset snapshot

The validated mandatory p=1 pilot has been staged at `releases/pilot-v0.1/` as
a self-contained repository dataset. It is ready for a later GitHub release but
has not been uploaded or published externally.

## Snapshot contents

- Frozen manifest and protocol identity.
- Dataset-level metadata and machine-readable schema field inventory.
- 40 canonical graph records, 40 exact results, and 40 feature rows.
- 400 complete optimization trajectories containing 16,370 evaluations.
- 1,200 run-checkpoint rows and 120 across-seed summary rows.
- Flat analysis CSV.
- T25 execution provenance and T26 QA artifacts.
- Empty pre-analysis exclusion register.
- Human-readable data dictionary and schema/join documentation.
- MIT license.
- Per-file snapshot checksum inventory.

The snapshot includes 457 checksummed files. Every checksum was verified after
staging. The checksum-inventory digest reported by the staging command is
`3eb9d0737bf49d49f04efec6b3a06e8dadcee9b1044e82800cd88730f88c45df`.
The source T26 dataset digest remains
`06f09ab1aab89565893451216fca1c35458c6a2f818a76403f2e91a233e1f060`.

## Traceability

Every analysis row can be traced through `run_id` or `graph_id` to a trajectory,
canonical graph, exact optimum, graph features, generator seed and parameters,
evaluator/version, optimizer seed, depth, budget, frozen manifest, and protocol
version. The exact join route and every field definition are documented in the
packaged data dictionary.

Exploratory p=2 results are explicitly excluded. Deleting
`results/exploratory-p2-v0.1/` would not change any staged snapshot file or
checksum.

## Reproduction

Recreate the snapshot from a passing T26 dataset with:

```bash
PYTHONPATH=src python -m qaoa_reliability.experiments.release \
  --results results/full-pilot-v0.1 \
  --manifest experiments/manifests/pilot-v0.1.json \
  --license LICENSE \
  --data-dictionary docs/dataset/data-dictionary.md \
  --schemas docs/dataset/schemas.md \
  --destination releases/pilot-v0.1
```

The command refuses to overwrite an existing destination or package a source
that did not pass T26.
