# Project Scope

**Working title:** QAOA Reliability Benchmark
**Scope version:** 0.1  
**Date:** 9 October 2026  
**Status:** Frozen  
**Proposal deadline:** 20 October 2026  

## 1. Project purpose

This project will develop an open-source benchmark for evaluating the
reliability of QAOA parameter optimization under fixed computational
budgets. The benchmark will provide a reproducible way to compare
optimization runs across graph instances, parameter initializations,
QAOA depths, and evaluator implementations.

The accompanying pilot study will use unweighted MaxCut to investigate
whether graph properties predict budget-limited QAOA performance and
reliability, particularly when evaluation is performed on graph families
that were not represented during model fitting.

The software package is the primary deliverable. The pilot study will
validate the benchmark and provide an initial scientific use case.

## 2. Primary research question

> Under a fixed number of exact QAOA objective evaluations, which graph
> properties predict optimization performance and reliability on
> previously unseen graph families?

The study will focus on practical optimization behavior rather than only
the best result obtainable with a large or unrestricted optimization
budget.

The principal outcomes will include:

- optimization regret at fixed evaluation budgets;
- variation across parameter-initialization seeds;
- probability of reaching a specified performance target;
- number of evaluations required to reach that target;
- predictive performance on held-out graph families.

## 3. Primary software contribution

The project will produce a framework-agnostic benchmark protocol and an
open-source Python reference implementation for measuring QAOA
optimization reliability under standardized objective-evaluation
budgets.

The initial implementation will contain:

- a common evaluator interface;
- a lightweight NumPy statevector evaluator;
- a Qiskit 2.x evaluator adapter;
- deterministic graph generation and serialization;
- exact MaxCut solutions for the studied instances;
- fixed-budget optimizer execution;
- repeated parameter-initialization runs;
- complete optimization-trajectory recording;
- graph-feature extraction;
- reliability metrics and analysis utilities;
- versioned experiment manifests and reproducibility metadata.

In the ideal-simulation pilot, one objective evaluation is defined as one
calculation of the exact expected MaxCut objective for one complete QAOA
parameter vector. Optimizer bookkeeping, logging, and analysis do not
count as objective evaluations.

## 4. Pilot validation study

### Problem

The pilot will study unweighted MaxCut.

### QAOA configuration

- `p=1` is the mandatory benchmark depth.
- `p=2` will be included only if the implementation and computational
  budget permit it without reducing the quality of the `p=1` study.
- The initial classical optimizer will be COBYLA.
- Every graph instance will be tested using multiple independently seeded
  parameter initializations.
- Objective values will be calculated using exact statevector simulation.

### Graph instances

The initial pilot will use graphs with:

- `n=8` vertices;
- `n=10` vertices.

Candidate graph families are:

1. Erdős–Rényi random graphs;
2. random regular graphs;
3. Watts–Strogatz small-world graphs;
4. stochastic block-model graphs.

The generation parameters will be chosen to avoid trivial or
systematically disconnected instances. All generation seeds and graph
parameters will be recorded.

### Experimental budget

The initial objective-evaluation checkpoints will be:

- 25 evaluations;
- 50 evaluations;
- 100 evaluations.

Results at smaller checkpoints will be extracted from a single
optimization trajectory run to the maximum budget. The exact pilot size
may be reduced following a documented smoke test, but its multi-family
and repeated-seed design will be preserved.

## 5. Out of scope

The pilot will not include:

- execution on quantum hardware;
- claims about performance under realistic device noise;
- finite-shot benchmarking;
- weighted MaxCut;
- comparison of many classical optimizers;
- claims of quantum advantage;
- a second combinatorial optimization problem;
- commitments concerning large graph sizes;
- an interactive visualization dashboard before proposal submission;
- a dependency on OpenQAOA.

These subjects may be considered as future extensions but are not
requirements for the pilot or the initial funded project.

## 6. Success criteria

The pilot will be considered successful if it demonstrates that:

1. the same benchmark experiment can be run reproducibly through both
   the NumPy and Qiskit evaluator implementations;
2. objective evaluations are counted consistently and unambiguously;
3. complete optimization trajectories can be recorded and reproduced;
4. variation in at least one reliability metric can be measured across
   graph instances, graph families, or initialization seeds;
5. a held-out-family prediction analysis can be executed without data
   leakage;
6. the software, protocol, instances, exact solutions, and pilot results
   can be reused by another researcher.

Strong predictive performance is not required for project success. If
the selected graph features do not generalize to unseen graph families,
the benchmark, dataset, analysis pipeline, and scientifically useful
negative result will remain project contributions.

## 7. Scope-control rule

The scientific scope will be frozen before the full pilot is executed.

If implementation or computational constraints arise, work will be
reduced in the following order:

1. remove the optional `p=2` experiments;
2. reduce the number of instances or initialization seeds while
   preserving every graph family;
3. simplify the predictive models;
4. defer nonessential packaging or visualization features.

The tested `p=1` evaluators, objective-evaluation accounting, repeated
initializations, complete trajectories, reproducible pilot, and proposal
materials will not be removed.

## 8. Frozen decisions

Before this document is marked **Frozen**, confirm the following:

- [ ] The research question is final.
- [ ] The software package is the primary deliverable.
- [ ] Unweighted MaxCut is the only pilot problem.
- [ ] The four graph families are accepted.
- [ ] `n=8` and `n=10` are the pilot sizes.
- [ ] `p=1` is mandatory and `p=2` is optional.
- [ ] Exact expectation evaluation is the pilot execution model.
- [ ] NumPy and Qiskit are the two reference implementations.
- [ ] COBYLA is the initial optimizer.
- [ ] Evaluation checkpoints are 25, 50, and 100.
- [ ] The non-goals and scope-reduction order are accepted.
- [ ] No unresolved decision prevents implementation from starting