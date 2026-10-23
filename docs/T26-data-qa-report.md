# T26 full-pilot data QA report

The automated T26 audit passed with no errors and no pre-analysis exclusions.
It validated the completed T25 dataset against frozen manifest
`sha256:84a992b08c73e3988cf4773c2b919e930e5ac2e6bd361970bad411f6698d80f3`.

## Validated invariants

- All 40 canonical graphs joined one-to-one with the manifest and regenerated
  identically from their family, size, parameters, and seed.
- All 40 exact MaxCut rows were recomputed and matched their stored values.
- All 40 graph-feature rows were recomputed and matched their stored values.
- All 400 non-empty trajectory files had unique run IDs, known graph IDs,
  contiguous one-based evaluation indices, and no more than 100 calls.
- All 1,200 run-checkpoint rows joined to a trajectory and exact optimum, with
  `evaluations_available = min(budget, trajectory length)`.
- All 120 graph/depth/budget aggregates were unique, joined to known graphs, and
  contained all ten seeds.
- The analysis CSV contained all 120 expected aggregate rows.

The audit checksummed 446 execution and data files. Its dataset digest is
`06f09ab1aab89565893451216fca1c35458c6a2f818a76403f2e91a233e1f060`.
Individual file hashes are stored in
`releases/pilot-v0.1/qa/checksums.sha256`.

The exclusion register was frozen as an empty list before downstream analysis:
`releases/pilot-v0.1/qa/exclusions.json`. The machine-readable audit is
`releases/pilot-v0.1/qa/T26-qa-report.json`.
