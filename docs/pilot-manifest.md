# Pilot manifest v0.1

The executable pilot definition is
[`experiments/manifests/pilot-v0.1.json`](../experiments/manifests/pilot-v0.1.json).
Its content identity is:

```text
sha256:84a992b08c73e3988cf4773c2b919e930e5ac2e6bd361970bad411f6698d80f3
```

Any change to a graph seed, generator parameter, optimizer seed, depth, budget,
evaluator, optimizer, or target changes this identity and defines a different
experiment.

## Frozen design

| Dimension | Values |
| --- | --- |
| Graph families | Erdős–Rényi, random regular, Watts–Strogatz, SBM |
| Graph sizes | 8 and 10 nodes |
| Graphs per family/size cell | 5 explicitly listed seeds |
| Total graphs | 40 |
| QAOA depth | `p=1` |
| Optimizer seeds | 0 through 9 |
| Runs | 400 |
| Nested budgets | 25, 50, and 100 objective evaluations |
| Maximum objective calls | 40,000 |
| Evaluator | `numpy_statevector@1.0` |
| Optimizer | SciPy COBYLA |
| Success target | 95% of exact MaxCut optimum |

The smaller budgets are trajectory prefixes of the 100-evaluation run. They do
not create additional optimizer runs or objective evaluations.

## Graph parameters

- Erdős–Rényi: edge probability `0.4`.
- Random regular: degree `3`.
- Watts–Strogatz: neighborhood size `4`, rewiring probability `0.25`.
- Stochastic block model: two equal blocks, within-block probability `0.8`,
  between-block probability `0.2`.

All 40 listed specifications were generated twice during the T21 gate. The two
passes were identical, all graph IDs were unique, and every accepted graph was
connected.

## Compute estimate

Local planning measurements on 17 October 2026 gave approximately:

| Size | 100 NumPy `p=1` evaluations | Per evaluation |
| --- | ---: | ---: |
| 8 nodes | 0.234 s | 0.00234 s |
| 10 nodes | 0.720 s | 0.00720 s |

With 20 graphs at each size and 10 optimizer seeds, the raw evaluator estimate
is roughly 191 seconds for the full 40,000-call ceiling. Allowing for varying
edge counts, optimizer overhead, JSONL flushing, exact solutions, features, and
analysis, reserve **5–10 minutes of local CPU time** for the initial full pilot.
T22 must replace this planning estimate with an end-to-end smoke-pilot timing
before the full run is authorized.

## Scope boundary

The manifest contains only the mandatory `p=1` pilot. The optional `p=2` subset
authorized by T16 requires a separate manifest and cannot be silently added to
this experiment.
