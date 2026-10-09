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