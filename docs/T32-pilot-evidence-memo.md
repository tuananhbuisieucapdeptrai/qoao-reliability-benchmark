# QAOA Reliability Benchmark — pilot evidence memo

**Purpose.** We built and ran an open, reproducible benchmark for asking a
practical question: under a fixed number of objective evaluations, how reliable
is shallow-QAOA parameter optimization across graph families and random initial
seeds? The mandatory pilot covers 40 MaxCut graphs, four graph families, two
sizes, ten optimizer seeds, QAOA depth p=1, and nested budgets of 25, 50, and 100
evaluations. [E1, E2]

**What worked.** The complete experiment executed 400 optimization runs and
persisted 16,370 counted objective evaluations in 53.49 seconds on local CPU.
Every graph, exact optimum, feature row, trajectory, checkpoint metric, and
aggregate passed the independent T26 audit; 446 source files were checksummed,
with no duplicate IDs, broken joins, accounting failures, or exclusions.
[E1, E2] The staged open dataset contains canonical graphs, exact solutions,
features, trajectories, metrics, schemas, provenance, a data dictionary, and an
MIT license, allowing every analysis row to be traced through `run_id` and
`graph_id` to the frozen protocol. [E3]

**Observed effect.** Additional p=1 optimization after the first 25 evaluations
provided little average benefit: mean normalized gap moved from 0.22726 at
budget 25 to 0.22554 at budget 100. Family uncertainty intervals overlap, so
the pilot does not justify a simple family ranking. [E4] Initialization
sensitivity was strongly topology-dependent at budget 100: the mean normalized
best-objective range was effectively zero for random-regular graphs, 0.07848
for Watts–Strogatz, 0.09389 for Erdős–Rényi, and 0.12781 for stochastic-block
graphs. [E5] No p=1 run reached the frozen 95%-of-exact target; each family had
0/100 successes, with a run-level Wilson 95% upper bound of about 3.7%, so
evaluations-to-target is not estimable for this threshold. [E5]

**Predictive result.** A leakage-safe leave-one-family-out study found no
evidence that the current seven-feature Ridge model generalizes better than a
size/density baseline. Baseline pooled MAE was 0.03797 versus 0.04261 for the
expanded model; baseline-minus-expanded improvement was -0.00464 with a 95%
bootstrap interval of [-0.01395, 0.00450]. Both pooled R² values were negative.
[E6] This negative result narrows the proposal claim: the current artifact
measures reliability reproducibly, but it does not yet predict unseen-family
reliability from simple graph descriptors. [E6]

**Limitations.** The mandatory evidence is noiseless statevector simulation on
small n=8 and n=10 graphs, one optimizer, one p=1 circuit convention, and only
ten graphs per family. [E1, E2] Zero target successes prevent direct comparison
of evaluations-to-target, and correlated optimizer seeds within a graph limit
run-level population interpretations. [E5] The optional eight-graph p=2 subset
showed a smaller mean gap than matched p=1 runs at budget 100, but 38/40 runs
used the full budget; its selected size is exploratory and cannot establish p=2
superiority. [E7]

**Next four-month study.** Month 1 will freeze protocol v0.2 and add multiple
optimizers plus noisy/sampled evaluator validation. **[H1: hypothesis]**
Optimizer choice and sampling noise will materially change seed sensitivity.
Month 2 will expand graph sizes, graph counts, and a predeclared p=1/p=2 matrix
under compute-matched budgets. **[H2: hypothesis]** Deeper QAOA will improve
gap only when given a larger search budget. Month 3 will preregister reliability
targets and repeat held-out-family modeling with more training graphs and
uncertainty-aware evaluation. **[H3: hypothesis]** Expanded topology features
will become useful only after family and size coverage increases. Month 4 will
release dataset v0.2, documented analysis notebooks, contributor instructions,
and a backend-ready reproducibility report. **[H4: planned outcome]** These
artifacts will let researchers compare optimizers and backends without silently
changing graph instances, conventions, or evaluation accounting.

## Evidence key

- **E1:** `releases/pilot-v0.1/qa/T26-qa-report.json`
- **E2:** `releases/pilot-v0.1/execution.json`
- **E3:** `releases/pilot-v0.1/dataset-metadata.json` and packaged data dictionary
- **E4:** `results/T29-analysis/figure-2-regret-vs-budget.{png,svg}` and figure data
- **E5:** `results/T30-analysis/family-reliability.csv` and reliability report
- **E6:** `results/T31-analysis/predictive-report.json` and fold metrics
- **E7:** `results/exploratory-p2-v0.1/execution.json` and T27 report
