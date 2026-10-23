# T27 exploratory p=2 report

This result is **exploratory, non-mandatory, and removable**. It does not alter
or extend the frozen p=1 pilot dataset. The run was allowed only after the T16
scope gate, successful T25 completion, and passing T26 data QA.

## Bounded design

- One graph from each of the eight family/size cells: 8 graphs total.
- The first five frozen optimizer seeds: 0, 1, 2, 3, and 4.
- QAOA depth p=2.
- Unchanged nested evaluation ceilings: 25, 50, and 100.
- NumPy statevector evaluator 1.0 and SciPy COBYLA.
- 40 runs and at most 4,000 objective evaluations.

This satisfies the task cap of 8–12 graphs by five seeds.

## Execution and QA

- Status: completed; QA passed with zero errors.
- Actual objective calls: 3,963.
- Per-run calls: minimum 66, median 100, mean 99.075, maximum 100.
- Outputs: 40 trajectories, 120 run-checkpoint rows, and 24 seed-summary rows.
- Runtime: 23.70 seconds in the recorded local environment.

## Exploratory comparison

For an apples-to-apples descriptive comparison, p=1 was restricted to the same
eight graphs and optimizer seeds 0–4. No inferential claim is made from this
small, selected subset.

| Budget | p=1 mean normalized gap | p=2 mean normalized gap | p=1 success | p=2 success |
| ---: | ---: | ---: | ---: | ---: |
| 25 | 0.21935 | 0.20876 | 0.0 | 0.0 |
| 50 | 0.21919 | 0.19795 | 0.0 | 0.0 |
| 100 | 0.21919 | 0.18928 | 0.0 | 0.0 |

The p=2 subset reduced mean normalized gap as the budget increased, but no run
reached the frozen 95%-of-exact target. Unlike p=1, 38 of 40 p=2 runs consumed
the full 100-call ceiling. This suggests added depth benefits from additional
search effort, but the subset is too small and selectively chosen to support a
general superiority claim.

The machine-readable artifacts live only under
`results/exploratory-p2-v0.1/`, keeping them separable from and removable without
affecting `results/full-pilot-v0.1/`.
