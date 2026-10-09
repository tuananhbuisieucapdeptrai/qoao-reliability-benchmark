# Novelty and Related-Work Matrix

**Document version:** 0.1  
**Evidence checked:** 9 October 2026  
**Status:** Initial evidence-backed review

## Rating key

- **Yes** — the inspected source clearly provides the capability.
- **No** — the inspected source clearly places the capability outside its method or reported output.
- **Partial** — relevant support exists, but not as the complete benchmark capability defined for this project.
- **Unknown—verify** — the inspected evidence is insufficient for a defensible conclusion.

The ratings describe the published or documented workflow, not what a skilled user could build by writing additional code around it.

## Main comparison

| Work or project | Graph-conditioned analysis | Diverse graph families | Standardized evaluation budgets | Complete trajectories | Repeated seeds | Seed sensitivity | Evaluations-to-target | Exact reference | Held-out graph families | Reusable benchmark software | Framework-agnostic protocol | Public trajectories/data |
| :-- | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: |
| [Herrman et al. (2021), *Impact of Graph Structures for QAOA on MaxCut*](https://arxiv.org/abs/2102.05997) | Yes | Partial | No | No | Yes | Partial | No | Yes | No | Partial | No | Partial |
| [Farhi, Goldstone and Gutmann (2014), *A Quantum Approximate Optimization Algorithm*](https://arxiv.org/abs/1411.4028) | Partial | No | No | No | No | No | No | Partial | No | No | No | No |
| [Qiskit Algorithms QAOA](https://qiskit-community.github.io/qiskit-algorithms/stubs/qiskit_algorithms.QAOA.html) | No | Partial | Partial | Partial | Partial | No | No | Partial | No | Partial | No | No |
| [OpenQAOA](https://github.com/entropicalabs/openqaoa) | No | Partial | Partial | Yes | Partial | No | No | Yes | No | Partial | No | No |
| [Metriq / metriq-gym](https://github.com/unitaryfoundation/metriq-gym) | No | No | No | No | Partial | No | No | Partial | No | Yes | Yes | Yes |
| [Qiskit Community QAOA Training Pipeline](https://github.com/qiskit-community/qaoa_training_pipeline) | Partial | Partial | Partial | Partial | Partial | No | No | Partial | No | Yes | No | Partial |
| [Koch et al. (2025), QOBLIB — *The Intractable Decathlon*](https://arxiv.org/abs/2504.03832) | No | Partial | No | Partial | Unknown—verify | No | No | Partial | No | Yes | Yes | Yes |
| [Falla et al. (2024), *Graph Representation Learning for Parameter Transferability in QAOA*](https://arxiv.org/abs/2401.06655) | Yes | Yes | Partial | No | Unknown—verify | No | No | Yes | Partial | Unknown—verify | No | Unknown—verify |
| [Nguyen and Safro (2026), *Graph-Conditioned Meta-Optimizer for QAOA Parameter Generation*](https://arxiv.org/abs/2604.25275) | Yes | Yes | Partial | Yes | Unknown—verify | Unknown—verify | No | Partial | Yes | Unknown—verify | No | Unknown—verify |
| **Proposed project** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |

## Interpretation notes

### Herrman et al. (2021)

Herrman et al. is the closest predecessor for the structural-analysis component. It evaluates all connected, non-isomorphic graphs with three to eight vertices and correlates graph properties with expected cost, optimal-solution probability, approximation ratio, and improvement with QAOA depth.

Important overlap that must be acknowledged:

- the study uses many random initializations: 50 at `p=1`, 100 at `p=2`, and 500 at `p=3`;
- it calculates exact MaxCut reference values for the small graphs;
- it publishes a graph/property/QAOA-result dataset and scripts for MySQL and pandas.

Important distinction:

- the random starts are used to obtain and verify best-case optimized angles;
- the paper does not standardize or analyze objective-function evaluation counts;
- it does not report complete per-evaluation optimization trajectories;
- it does not quantify the distribution of outcomes across seeds as the primary object of study;
- it does not use leave-one-graph-family-out prediction.

The **seed sensitivity** rating is **Partial**, rather than **No**, because independent random-start batches were rerun to check consistency. However, variability across individual seeds was not treated as the reported reliability outcome.

Evidence: [open-access paper copy](https://www.osti.gov/servlets/purl/1819598), especially the numerical-method description and Appendix B.

### Farhi, Goldstone and Gutmann (2014)

The original QAOA paper defines the algorithm and analyzes approximation behavior on selected problem settings. It is foundational rather than a reusable empirical reliability benchmark.

- **Graph-conditioned analysis: Partial** because graph structure and local neighborhoods are relevant to its MaxCut analysis, but it does not fit predictive relationships from a diverse graph-property dataset.
- **Exact reference: Partial** because optimal objective values and approximation ratios are part of the theoretical formulation, but it does not publish an exact-reference dataset for the benchmark proposed here.
- The paper does not provide repeated-seed reliability analysis, objective-evaluation checkpoints, held-out-family prediction, or public optimization trajectories.

Evidence: [arXiv:1411.4028](https://arxiv.org/abs/1411.4028).

### Qiskit Algorithms QAOA

Qiskit provides a reusable QAOA implementation rather than a graph-conditioned benchmark.

- Its callback exposes the evaluation count, current parameter vector, evaluated value, and metadata at each functional evaluation. This makes trajectory capture possible.
- Optimizers may be configured with limits, and users may provide initial points and control random state externally.
- Qiskit does not itself prescribe the proposed 25/50/100 evaluation protocol, repeated-seed orchestration, seed-sensitivity metrics, evaluations-to-target, or held-out-family analysis.

Therefore **standardized budgets**, **complete trajectories**, and **repeated seeds** are rated **Partial**: the mechanisms exist, but the benchmark behavior must be implemented by the user. **Reusable benchmark software** is also **Partial**, because Qiskit is reusable algorithm software but not this benchmark workflow.

Evidence: [Qiskit Algorithms QAOA API](https://qiskit-community.github.io/qiskit-algorithms/stubs/qiskit_algorithms.QAOA.html), especially the `callback` and `initial_point` documentation.

### OpenQAOA

OpenQAOA is a multi-backend QAOA SDK with multiple parameterizations, initialization methods, classical optimizers, simulators, and hardware-provider plugins.

Substantial overlap:

- `q.result.intermediate` records the angles and cost from intermediate objective evaluations;
- the optimized result records the selected evaluation number;
- a maximum optimizer iteration count can be configured;
- random initialization is supported;
- `ground_state_hamiltonian()` provides a brute-force exact reference for sufficiently small problems.

Missing benchmark layer:

- no documented graph-conditioned study protocol;
- no standardized repeated-seed comparison across graph families;
- no seed-sensitivity or evaluations-to-target analysis;
- no leave-one-family-out predictive test;
- no public corpus of the proposed graph-level optimization trajectories.

**Complete trajectories** is rated **Yes** for angles and costs because the result object records the intermediate optimization history. Intermediate measurement outcomes are disabled by default, but they are not required by our trajectory definition. **Reusable benchmark software** remains **Partial** because OpenQAOA supplies QAOA execution and results, not the complete proposed benchmarking protocol.

Evidence: [OpenQAOA result documentation](https://openqaoa.entropicalabs.com/making-sense-of-the-result/) and [OpenQAOA repository](https://github.com/entropicalabs/openqaoa).

### Metriq and metriq-gym

Metriq is a general quantum-device benchmarking platform rather than a graph-conditioned parameter-optimization benchmark. `metriq-gym` defines benchmark configurations in schemas and supports execution across multiple providers; `metriq-data` stores schema-enforced public benchmark records.

- **Reusable benchmark software: Yes** because implementing, dispatching, and recording standardized benchmarks is its central purpose.
- **Framework-agnostic protocol: Yes** at the provider-facing level: benchmark definitions are separated from supported provider integrations.
- **Public trajectories/data: Yes** because public versioned benchmark records are maintained in `metriq-data`.
- Its Linear Ramp QAOA benchmark does not establish the proposed iterative objective-evaluation-budget, repeated-initialization, graph-feature, or held-out-family protocol.

Evidence: [metriq-gym](https://github.com/unitaryfoundation/metriq-gym), [metriq-data](https://github.com/unitaryfoundation/metriq-data), and the [Metriq platform overview](https://github.com/unitaryfoundation/metriq).

### QAOA Training Pipeline

The Qiskit Community QAOA Training Pipeline is designed to produce good QAOA parameters using interchangeable trainers and evaluators, including exact light-cone evaluation, matrix-product states, Pauli propagation, and Qiskit/Aer support.

Relevant overlap:

- command-line runs accept input graphs and JSON method configurations;
- SciPy trainer configurations can set `maxiter` and initial parameters;
- saved result dictionaries include training history;
- the project includes an optional CPLEX-based exact MaxCut solver;
- data-based and graph-related parameter-training methods are present.

The inspected documentation does not define a repeated-seed graph-reliability benchmark, evaluation checkpoints, seed-sensitivity outcomes, evaluations-to-target, or leave-one-family-out validation. Training history is rated **Partial** because the repository documents saved history, but the top-level documentation does not establish that every trainer records every underlying objective call with one uniform schema.

The protocol is not framework-agnostic: its documented input objects and ansatz conventions use Qiskit types such as `SparsePauliOp` and `QAOAAnsatz`.

Evidence: [QAOA Training Pipeline repository](https://github.com/qiskit-community/qaoa_training_pipeline).

### QOBLIB — The Intractable Decathlon

QOBLIB provides ten difficult, application-relevant optimization problem classes, public instances, reference solver results, submission guidance, and a standardized presentation format for comparing classical and quantum solvers.

It is highly relevant as a benchmark-design precedent, but its scope differs from this project:

- it benchmarks optimization problem instances and solver results broadly;
- it does not define QAOA objective-evaluation checkpoints or QAOA parameter trajectories;
- it does not analyze graph properties as predictors of QAOA optimization reliability;
- exact optima are available for some instances, while others use best-known/reference solver track records.

**Complete trajectories** is **Partial** because QOBLIB maintains solution track records, not complete per-objective-call QAOA parameter trajectories. **Repeated seeds** remains **Unknown—verify** because this can depend on individual contributed solver records rather than the core library specification.

Evidence: [Koch et al., 2025](https://arxiv.org/abs/2504.03832).

### Falla et al. (2024)

This work uses five graph-embedding techniques to select donor graphs for QAOA parameter transfer, including transfer across different classes of MaxCut instances. It reports an order-of-magnitude reduction in optimization iterations and investigates ideal and noisy settings.

This is direct prior art for graph-conditioned prediction and cross-class generalization. The remaining distinction is that its primary target is donor-parameter transferability, not a reusable benchmark of repeated-seed optimizer reliability at fixed objective-evaluation checkpoints.

- **Held-out graph families: Partial** because it transfers between graph classes, but the inspected abstract does not establish our exact leave-one-family-out protocol.
- **Standardized evaluation budgets: Partial** because optimization effort/iterations are compared, but this is not yet verified as strict objective-call accounting at common checkpoints.
- Public code, data, and repeated-seed treatment remain **Unknown—verify** pending inspection of the full supplementary material or linked repository.

Evidence: [arXiv:2401.06655](https://arxiv.org/abs/2401.06655).

### Nguyen and Safro (2026)

This is the strongest recent novelty challenge. It trains a graph-conditioned meta-optimizer that generates QAOA parameter trajectories over a fixed horizon. It evaluates cross-problem transfer among MaxCut, maximum independent set, maximum clique, and minimum vertex cover, reporting 64 experimental settings.

Overlap with our project:

- graph-conditioned parameter optimization;
- explicit parameter trajectories;
- fixed-horizon optimization effort;
- transfer to graph/problem classes excluded during training.

Remaining distinction:

- its contribution is a learned meta-optimizer for parameter generation;
- our proposed contribution is an optimizer-neutral benchmarking protocol and dataset for measuring regret, initialization sensitivity, success probability, and evaluations-to-target under standardized objective-call checkpoints;
- our main generalization test is leave-one-graph-family-out within unweighted MaxCut, not primarily transfer of a trained optimizer between combinatorial problem types.

The paper clearly uses a fixed horizon, but this is rated **Partial** under standardized evaluation budgets because equivalence between a learned optimization step and one counted QAOA objective evaluation needs verification. Repeated random seeds, seed-sensitivity reporting, exact-reference coverage, released software, and public trajectory data remain **Unknown—verify** unless confirmed from the paper supplement or an author repository.

Evidence: [arXiv:2604.25275](https://arxiv.org/abs/2604.25275).

## Revised novelty statement

> Existing research already relates graph structure to QAOA outcomes, studies graph-aware parameter transfer, and—in recent work—uses graph-conditioned learned optimizers that generate fixed-horizon parameter trajectories. Existing SDKs can also expose intermediate optimization histories, while general benchmark platforms provide cross-provider execution and public result schemas. The missing contribution targeted here is narrower: an optimizer-neutral, framework-agnostic benchmark protocol that standardizes objective-call accounting and repeated initialization experiments, publishes complete graph-level trajectories, measures regret, seed sensitivity, success probability and evaluations-to-target at fixed checkpoints, and evaluates whether these reliability relationships generalize under leave-one-graph-family-out testing.

## Implication for the proposal

Avoid claiming that the project is the first to:

- study graph structure and QAOA;
- record QAOA optimization histories;
- use many random initializations;
- reduce QAOA optimization effort;
- study parameter transfer between graph classes;
- provide a general quantum benchmark framework.

The defensible contribution is the integrated **benchmark protocol and reusable dataset for optimizer reliability**, with strict objective-evaluation accounting and held-out-family validation. The pilot should demonstrate that this integration works; it does not need to prove that every component is individually novel.

## Remaining verification tasks

- [ ] Inspect the Herrman public repository/database schema to confirm precisely which optimizer fields and per-seed records are released.
- [ ] Inspect all QAOA Training Pipeline trainer result schemas to determine whether every objective evaluation is uniformly recorded.
- [ ] Inspect the full Falla et al. supplementary material and code availability.
- [ ] Inspect the full Nguyen–Safro experimental appendix for random seeds, exact references, objective-call accounting, data splits, and code/data release.
- [ ] Inspect QOBLIB submission records to determine how repeated stochastic solver runs are represented.
- [ ] Decide whether Metriq should remain in the main matrix or move to a separate “benchmark infrastructure precedents” section.
