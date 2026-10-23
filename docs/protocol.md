# QAOA Optimization-Reliability Benchmark Protocol

**Protocol version:** 0.1  
**Date:** 9 October 2026  
**Status:** Draft / Frozen  
**Related scope:** `docs/scope.md`  
**Primary problem:** Unweighted MaxCut  

## 1. Purpose

This protocol defines a reproducible procedure for measuring the
reliability and sample efficiency of shallow-QAOA parameter optimization
across structurally different graph instances.

The protocol standardizes:

- graph generation;
- exact MaxCut reference solutions;
- QAOA parameter conventions;
- objective-evaluation accounting;
- optimizer initialization;
- optimization-trajectory recording;
- reliability metrics;
- graph-feature extraction;
- held-out-family analysis;
- software and experiment metadata.

The primary purpose is controlled comparison across graph instances. The
objective-evaluation budget is an experimental control and a measure of
optimizer query efficiency. It is not intended to represent a complete
quantum-hardware cost model.

## 2. Research question

> Which graph properties predict the reliability and sample efficiency
> of shallow-QAOA parameter optimization, and do these relationships
> generalize to unseen graph families?

The principal outcomes are:

1. best-so-far approximation ratio;
2. normalized optimization regret;
3. sensitivity to parameter initialization;
4. probability of reaching a predefined performance target;
5. evaluations required to reach that target.

## 3. Benchmark terminology

### 3.1 Graph instance

A graph instance is one concrete undirected, unweighted graph:

\[
G=(V,E).
\]

Every graph is assigned a deterministic `graph_id` derived from its
canonical serialized representation or a stable content hash.

### 3.2 Parameter vector

For QAOA depth \(p\), the complete parameter vector is

\[
\boldsymbol{\theta}
=
(\gamma_1,\ldots,\gamma_p,\beta_1,\ldots,\beta_p).
\]

The ordering and units of all parameters must be identical across
evaluator implementations.

### 3.3 Objective evaluation

One objective evaluation is one request to compute

\[
F_G(\boldsymbol{\theta})
=
\langle\psi_G(\boldsymbol{\theta})|
C_G
|\psi_G(\boldsymbol{\theta})\rangle
\]

for one graph \(G\) and one complete QAOA parameter vector
\(\boldsymbol{\theta}\).

Each call counts as one evaluation, including repeated calls using an
identical parameter vector.

The following do not count as additional objective evaluations:

- optimizer bookkeeping;
- logging;
- serialization;
- callback execution;
- graph-feature calculation;
- exact MaxCut calculation;
- calculation of derived benchmark metrics.

Internally summing the expectation contributions of multiple edges also
counts as one objective evaluation because one complete objective value
is returned to the optimizer.

### 3.4 Optimization run

One optimization run is the optimization of one graph instance using one
combination of:

- QAOA depth;
- evaluator implementation;
- optimizer configuration;
- parameter-initialization seed;
- maximum objective-evaluation budget.

### 3.5 Experiment

An experiment is a versioned collection of optimization runs generated
from one immutable experiment manifest.

## 4. MaxCut objective convention

For a bit string \(z\in\{0,1\}^{|V|}\), the cut value is

\[
C_G(z)
=
\sum_{(u,v)\in E}
\mathbb{1}[z_u\neq z_v].
\]

The exact optimum is

\[
C_{\max}(G)
=
\max_{z\in\{0,1\}^{|V|}} C_G(z).
\]

The MaxCut cost Hamiltonian is defined as

\[
C_G
=
\sum_{(u,v)\in E}
\frac{1-Z_uZ_v}{2}.
\]

Higher objective values represent better solutions.

The evaluator returns the expected cut value, not its negative. If a
classical optimizer expects minimization, the optimizer wrapper may
return \(-F_G(\boldsymbol{\theta})\), but the stored trajectory must
retain the positive expected cut value.

## 5. QAOA state convention

The initial state is

\[
|+\rangle^{\otimes n}.
\]

The problem unitary for layer \(j\) is

\[
U_C(\gamma_j)=e^{-i\gamma_j C_G},
\]

and the mixer unitary is

\[
U_B(\beta_j)=e^{-i\beta_j\sum_i X_i}.
\]

The complete state is

\[
|\psi_G(\boldsymbol{\gamma},\boldsymbol{\beta})\rangle
=
\prod_{j=1}^{p}
U_B(\beta_j)U_C(\gamma_j)
|+\rangle^{\otimes n}.
\]

The exact multiplication order used in code must be tested explicitly
because library conventions may differ.

### Initial parameter domains

Provisional domains are:

\[
\gamma_j\in[0,2\pi),
\qquad
\beta_j\in[0,\pi).
\]

If smaller symmetry-reduced domains are used, they must be justified and
applied identically across all graph families and evaluators.

## 6. Evaluator implementations

The initial benchmark contains two evaluator implementations:

1. a lightweight NumPy statevector evaluator;
2. a Qiskit 2.x exact-statevector evaluator.

Both implementations must expose the same conceptual operation:

```python
result = evaluator.evaluate(
    graph=graph,
    depth=p,
    parameters=theta,
)
```

The evaluator interface is independent of NumPy, Qiskit, and any future
backend. Every implementation returns the same result fields:

- `schema_version`;
- deterministic `evaluation_id`;
- `graph_id`;
- QAOA `depth`;
- the complete normalized parameter vector;
- the positive expected-cut `objective`;
- evaluator name and evaluator version;
- JSON-compatible implementation metadata, including relevant dependency
  versions.

The parameter vector has exactly `2 * depth` finite real entries in the order
defined in Section 3.2. The deterministic `evaluation_id` identifies a request;
it does not deduplicate calls or alter objective-evaluation accounting. Two
identical calls during an optimization run still consume two evaluations.

The NumPy reference maps graph vertex `i` to little-endian statevector bit `i`.
This representation detail must not alter the returned scalar objective, but it
is recorded in evaluator metadata and protected by convention tests.

## 7. Fixed-budget optimization

The reference runner maximizes the positive expected-cut objective with SciPy
COBYLA. Its `max_evaluations` value is a hard ceiling on calls to
`evaluator.evaluate`; optimizer callbacks, logging, checkpoint calculation, and
serialization never increment this counter. Repeated requests for an identical
parameter vector are separate counted evaluations.

The classical minimizer receives the negative expected cut, while every stored
trajectory record retains the positive expected cut. Optimizer initialization
is deterministic for a given integer seed. Cost angles are drawn from
`[0, 2π)` and mixer angles from `[0, π)` in the parameter order defined in
Section 3.2.

An optimizer may converge before exhausting its ceiling. Such a run records its
actual number of evaluations and must not invent additional calls to fill the
budget.

## 8. Trajectory records

Every completed objective call is immediately appended as one strict JSONL
record containing:

- schema and run IDs;
- one-based evaluation order and UTC timestamp;
- graph ID, QAOA depth, and optimizer seed;
- the complete parameter vector and positive expected-cut objective;
- evaluation ID, evaluator name, and evaluator version;
- evaluator/backend metadata.

Each JSONL line is independently parseable and schema-valid. Consequently, an
unexpected interruption may omit the in-progress call but preserves every
previous completed evaluation. A new run refuses to append to an existing path
so records from different executions cannot be silently mixed.

## 9. Repeated seeds and nested budgets

Multi-seed orchestration is deterministic and sequential in the reference
implementation. Every unique optimizer seed is run once at the maximum budget.
Metrics for smaller checkpoints are derived from prefixes of that same
trajectory. For checkpoint `b`, best-so-far is computed only from evaluation
records `1..b`; the objective is never rerun for checkpoint calculation.

Checkpoints must be positive, unique, increasing, and no larger than the
maximum configured budget. If an optimizer converges before a checkpoint, that
checkpoint is unavailable rather than fabricated.

## 10. Reliability metrics

All metrics use the best positive expected-cut objective observed within a
trajectory prefix. Let `B_b` be that best value at checkpoint budget `b`, and
let `C*` be the exact MaxCut optimum from the versioned exact solver.

### Regret

```text
regret_b = C* - B_b
```

Lower is better. An observed value exceeding the exact optimum by more than
`1e-9` is treated as a data-integrity error rather than silently clipped.

### Normalized gap

```text
normalized_gap_b = regret_b / C*
```

Lower is better. For an edge-free graph where `C* = 0`, the normalized gap is
defined as zero because the only valid objective and regret are also zero.

### Target, success, and evaluations-to-target

The default target is `0.95 * C*`. A seed succeeds at checkpoint `b` if any
evaluation in records `1..b` reaches the target within absolute tolerance
`1e-9`. Evaluations-to-target is the one-based index of the first such record,
or `None` when the seed has not reached the target. For `C* = 0`, the target is
zero and the first valid evaluation succeeds.

### Seed sensitivity and success probability

At each graph and budget, seed sensitivity is reported using the population
standard deviation and range of best-so-far objectives. Success probability is
the fraction of optimizer seeds reaching the target. Mean evaluations-to-target
is calculated only over successful seeds and is reported together with the
success count and probability so failures are never hidden.

Every metric row records the exact optimum and its solver/version source. Metric
calculation is analysis-only and never invokes an evaluator or consumes the
objective-evaluation budget.

## 11. Pilot manifest

Every experiment must load a validated, content-addressed manifest before graph
generation or optimization begins. The manifest freezes graph-family/size
cells, every graph-generation seed, generator parameters, optimizer seeds,
depths, nested budgets, evaluator/version, optimizer, target ratio, and protocol
version.

The initial mandatory pilot is `qaoa-reliability-pilot-v0.1`, identified by:

```text
sha256:84a992b08c73e3988cf4773c2b919e930e5ac2e6bd361970bad411f6698d80f3
```

It contains 40 graphs, 10 optimizer seeds, `p=1`, and a maximum budget of 100,
for 400 runs and at most 40,000 objective evaluations. Budgets 25 and 50 are
prefixes of the same maximum-budget trajectory. Editing any manifest-controlled
choice creates a new experiment identity; completed data from different
manifest identities must not be merged as one protocol run.
