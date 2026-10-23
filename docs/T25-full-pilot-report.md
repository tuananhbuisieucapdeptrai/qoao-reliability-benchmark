# T25 full-pilot execution report

The frozen p=1 pilot completed successfully on 17 October 2026. The execution
used manifest
`sha256:84a992b08c73e3988cf4773c2b919e930e5ac2e6bd361970bad411f6698d80f3`
without changing its graph matrix, optimizer seeds, depth, budgets, evaluator,
optimizer, or success target.

## Execution and QA

- Status: completed; QA passed with zero logged errors.
- Coverage: 40 graphs across all four families and both graph sizes.
- Optimization: 400 p=1 runs using ten optimizer seeds per graph.
- Objective calls: 16,370 actual calls under the 40,000-call ceiling.
- Persisted outputs: 400 trajectories, 1,200 run-checkpoint rows, and 120
  graph/budget seed-summary rows.
- Per-run calls: minimum 30, median 40, mean 40.925, maximum 100.
- Runtime: 53.49 seconds in the recorded local environment.

No generation, exact-solver, evaluator, optimizer-persistence, schema, identity,
join, or row-count failure was observed. Early COBYLA convergence explains why
the actual call count is lower than the ceiling and is valid under the frozen
maximum-budget protocol.

## Preliminary full-pilot signal

Across the 40 graph summaries, mean success probability at the frozen 95% target
was 0.0 at budgets 25, 50, and 100. Mean normalized gap decreased from 0.22726
at budget 25 to 0.22584 at budget 50 and 0.22554 at budget 100.

At budget 100, mean normalized gap by family was:

| Family | Mean normalized gap |
| --- | ---: |
| Erdős–Rényi | 0.23313 |
| Random regular | 0.20730 |
| Stochastic block model | 0.23629 |
| Watts–Strogatz | 0.22546 |

These values are descriptive outputs of the frozen pilot. In particular, the
absence of 95%-target successes must be reported rather than addressed through
a post-hoc threshold change.

## Artifacts

The public execution record is `releases/pilot-v0.1/execution.json`, the
acceptance record is `releases/pilot-v0.1/qa/qa-report.json`, and the primary
analysis table is `releases/pilot-v0.1/analysis/full-summary.csv`. Canonical
graphs, exact optima, graph features, complete trajectories, per-run metrics,
and seed-level summaries are stored in the same checksummed release.
