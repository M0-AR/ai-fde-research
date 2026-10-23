# Forward-Deployed Engineering for Enterprise AI Agents

**A measurement study, a six-template benchmark, and a null result for check-driven repair.**

Generated from `results/` at 2026-10-23T14:22:10+00:00. Every number below is produced by the pipeline in this repository; nothing is hand-entered.

## Abstract

Forward-deployed engineering (FDE) is a delivery model for enterprise AI agents: engineers embed with a customer, discover the workflow, build against messy context, deploy into a regulated environment, and hand the system to an owning team. The evidence base for the role is thin. This repository reports a point-in-time snapshot of 3,473 public job postings, a 48-row benchmark of FDE deliverables, a four-policy comparison on a small local model, a prompt-injection guardrail evaluation, and a shadow-price cost model.

The main benchmark result is a null result. One repair attempt driven by failed checks changed the score of **0 of 48 tasks**; 40 non-error pairs were byte-identical; 2 additional pairs were both errors. The ungoverned and verified policies both resolved 9/48 (18.8%) of tasks. The benchmark is not 48 independent scenarios: it is **6 templates with eight parameterizations each**, and five of the six phases reuse one instruction across all eight parameterizations (13 distinct instruction strings in total). The model sees the acceptance criteria, so this measures instruction-following against explicit rubrics, not open-ended FDE capability.

The governed and disciplined policies are reported separately from task resolution. In the current implementation, `requires_human_approval` is not part of the task acceptance criteria, so a high-risk artifact can pass every check and still omit approval. We therefore report **task resolution** and **governance compliance** as distinct outcomes. We do not claim that governance improves task outcomes, and we do not claim four-policy superiority.

## Research questions

1. **RQ1 — Market.** What does the 2026 labor market ask of FDE-like roles, and how sensitive is the count to the title definition?
2. **RQ2 — Lifecycle difficulty.** Which phases of the FDE lifecycle are hardest for a small open-weight model under explicit acceptance criteria?
3. **RQ3 — Governance.** Do verification, approval gates, and a disciplined delivery loop change task outcomes or governance compliance?
4. **RQ4 — Guardrails.** How well do simple rules and a lightweight classifier detect prompt injection in customer-supplied content?
5. **RQ5 — Deployment and cost.** Do canonical and generated deployment artifacts run, and what does governance cost per resolved task?

## What is in this repository

| Component | Path | What it does |
|---|---|---|
| Study configuration | `config/study.yaml` | Seeds, models, policies, sources, price assumptions |
| Role and skill taxonomy | `config/taxonomy.yaml` | Regexes for roles, skills, lifecycle phases, forbidden claims |
| External evidence | `config/public_benchmarks.yaml` | Cited 2026 benchmarks and market reports |
| Task bank | `src/fde_research/tasks.py` | 48 rows, six phases, machine-checked rubrics, reference artifacts |
| Benchmark harness | `src/fde_research/benchmark.py` | Runs models × policies, resumes, writes JSONL |
| Schema helpers | `src/fde_research/schema.py` | Model identity, task resolution, governance compliance |
| Freeze tool | `src/fde_research/freeze_run.py` | Hash and normalize a run before analysis |
| Validators | `src/fde_research/validators.py` | Check types; reference artifacts must pass their own checks |
| Market collector | `src/fde_research/collect_jobs.py` | Greenhouse, Lever, Ashby, Remotive, Arbeitnow |
| Scholarly collector | `src/fde_research/collect_scholarly.py` | OpenAlex, arXiv, Hacker News, GitHub |
| Guardrail evaluation | `src/fde_research/guardrail_eval.py` | deepset prompt-injection benchmark |
| Deployment evaluation | `src/fde_research/deployment_eval.py` | Canonical Compose smoke tests; optional generated-artifact attempts |
| Cost model | `src/fde_research/cost_model.py` | Live AWS Lambda prices + loaded human review cost |
| Statistics | `src/fde_research/stats.py` | Wilson intervals, paired bootstrap, McNemar, Wilcoxon, Friedman |
| Figures | `src/fde_research/figures.py` | Publication figures from result JSON |
| Report generator | `src/fde_research/report.py` | This report and LaTeX tables |

## Study design

### Benchmark: FDE-LifecycleBench

The benchmark contains **48 rows**: six phase templates with eight parameterizations each. Five phases (discovery, architecture, security, context, deployment) reuse a single instruction across the eight parameterizations; handover has eight distinct instructions. The total number of distinct instruction strings is **13**. This matters for inference: treating the rows as independent tasks overstates precision.

Each row supplies a brief, structured evidence, an instruction with explicit acceptance criteria, and an output contract stated in the prompt. Every row has a reference artifact that passes its own checks. Scoring is the fraction of checks passed; a task is **task-resolved** only when every check passes. Because the criteria are visible to the model, the benchmark is best read as a test of instruction-following and structured artifact production, not as a hidden-capability benchmark.

### Policies

| Policy | Mechanism |
|---|---|
| `ungoverned` | One model call; no repair, no approval gate |
| `verified` | One call plus one repair attempt driven by failed checks |
| `governed` | Verification plus an approval requirement for high-risk tasks |
| `fde_disciplined` | Plan → artifact → critique → repair, with approval requirements |

High-risk tasks involve security controls, destructive actions, production deployment, or customer data. **Task resolution** is whether the artifact passes the task checks. **Governance compliance** is whether a governed or disciplined high-risk artifact contains `requires_human_approval`. The current harness does not put approval in the task checks, so the two outcomes can diverge. They are reported separately throughout.

### Models and execution

The reported run uses `qwen2.5:1.5b` through Ollama's OpenAI-compatible endpoint. The design also supports `Qwen3VL-8B-Instruct-Q4_K_M` through llama.cpp; it was excluded from the reported run because a concurrent training job held most of the GPU. Temperature is zero, the seed is fixed, and each cell is a single episode. The harness records tokens and latency and validates every artifact with the same code that validates references.

### Guardrail evaluation

We train a TF-IDF (1–2 gram) logistic regression with balanced class weights on the deepset prompt-injection corpus and evaluate on a held-out 30% split. The threshold is chosen on cross-validation to reach at least 95% recall. A regex rule baseline represents a common blocklist approach.

### Deployment evaluation

The reported deployment scope is **canonical infrastructure smoke tests only**. P01 is an HTTP liveness check; P02 adds a cache dependency; P03 adds a worker/queue dependency and restart check. P02 and P03 do not exercise application logic. Generated benchmark artifacts are not executed in the reported run. We separately parse each generated `compose_yaml` field and count how many produce a Compose `services` mapping; 1 of 32 deployment episodes did so.

### Cost model

We retrieve live AWS Lambda on-demand prices for us-east-1 and compute the cost of a 512 MB, 500 ms invocation. Token costs use hosted-equivalent shadow prices ($0.60 per million input tokens, $2.40 per million output tokens). Human review is priced at a $254,000 loaded annual cost over 1,800 working hours. A review is counted when a high-risk governed or disciplined episode requires approval, when an episode escalates, or when it errors. We report cost per episode and cost per resolved task.

### Statistics

Task-resolution rates use Wilson 95% intervals. Policy comparisons are paired by task: paired bootstrap intervals for the difference, exact McNemar tests for discordant resolutions, and Wilcoxon signed-rank tests for partial scores. A Friedman test checks for an overall policy effect. All resampling uses 10,000 draws and the study seed. Because the rows are template parameterizations, these intervals describe this task bank, not a population of FDE tasks.

## Results

### RQ1 — Live market snapshot

| Metric | Value |
|---|---|
| Postings collected (point-in-time ATS snapshot) | 3,473 |
| FDE-like postings (broad regex class) | 670 (19.3%) |
| Explicit forward-deployed titles (subset) | 229 (6.6% of all; 34.2% of FDE-like) |
| Adjacent postings | 679 |
| Remote share, FDE-like | 24.2% |
| Median description length | 7,260 chars |
| Postings with a parseable salary mention | 205 (30.60%) |

The broad FDE-like class includes solutions, customer, and deployment engineering titles. The explicit subset matches `forward deployed` or `forward deploy` in the title. Salary figures come from a keyword-adjacent heuristic, not a verified compensation field.

**Top skills in FDE-like postings.**

| Skill | FDE share | Adjacent share | Lift (pp) |
|---|---|---|---|
| Customer / stakeholder | 99.7% | 89.2% | +10.4 |
| Leadership | 96.6% | 81.3% | +15.3 |
| AI / LLM | 90.0% | 88.4% | +1.6 |
| Production deployment | 82.2% | 88.2% | -6.0 |
| Security / governance | 77.9% | 68.8% | +9.1 |
| Cloud | 59.9% | 47.6% | +12.3 |
| Python | 58.4% | 32.6% | +25.8 |
| Evaluation / testing | 46.3% | 49.9% | -3.7 |

**Lifecycle language in FDE-like postings.**

| Phase | Share mentioning |
|---|---|
| Handover | 83.3% |
| Discovery | 82.7% |
| Deployment | 82.4% |
| Architecture | 80.3% |
| Security | 72.7% |
| Context | 37.2% |

Skill and lifecycle shares are regex-coded from job descriptions. Boilerplate inflates broad categories such as customer language, so the comparison between FDE and adjacent roles is more informative than any single share.


The snapshot is a point-in-time census of public ATS boards, not a representative sample of the whole economy. The broad FDE-like class contains 670 postings; the explicit `forward deployed` subset contains 229 (6.6% of all postings, 34.2% of FDE-like). Salary parsing is a keyword-adjacent heuristic over descriptions: 205 FDE-like postings (30.60%) yielded a parseable figure, with median low/high of $182,000 / $182,000. This is not a verified compensation field.

### RQ2/RQ3 — Lifecycle benchmark

| Model | Policy | n | Task resolved | 95% CI | Mean score | Gov. compliant (required) | Safety viol. | Errors |
|---|---|---|---|---|---|---|---|---|
| qwen2.5:1.5b | ungoverned | 48 | 9 (18.8%) | [10.2%, 31.9%] | 0.592 | n/a | 0 | 2 |
| qwen2.5:1.5b | verified | 48 | 9 (18.8%) | [10.2%, 31.9%] | 0.592 | n/a | 0 | 2 |
| qwen2.5:1.5b | governed | 48 | 16 (33.3%) | [21.7%, 47.5%] | 0.663 | 0/15 | 0 | 1 |
| qwen2.5:1.5b | fde_disciplined | 48 | 11 (22.9%) | [13.3%, 36.5%] | 0.537 | 0/15 | 0 | 10 |

**qwen2.5:1.5b.**

| Phase | ungoverned | verified | governed | fde_disciplined |
|---|---|---|---|---|
| discovery | 12.5% | 12.5% | 37.5% | 0.0% |
| architecture | 25.0% | 25.0% | 25.0% | 37.5% |
| security | 12.5% | 12.5% | 75.0% | 37.5% |
| context | 0.0% | 0.0% | 0.0% | 0.0% |
| deployment | 0.0% | 0.0% | 0.0% | 0.0% |
| handover | 62.5% | 62.5% | 62.5% | 62.5% |

**The verification null.** The ungoverned baseline resolved 9/48 (18.8%); verified resolved 9/48 (18.8%). Across the paired tasks, 0 scores changed, 0 improved, and 0 worsened. 40 non-error pairs were byte-identical; 2 additional pairs were both errors, and 37 of 48 verified episodes made a second call. The repair attempt did not move the outcome distribution. The disciplined loop changed 23 of 48 paired scores (8 improved, 15 worsened); 0 non-error artifacts were byte-identical to the ungoverned baseline, and 0 pairs were both errors.

**Governance is a separate outcome.** Governed task resolution is 16/48 (33.3%); governance compliance among required high-risk episodes is 0/15 in the governed run and 0/15 in the disciplined run (0/30 combined). The disciplined policy resolves 11/48 (22.9%). 11 governed or disciplined high-risk episodes passed every task check while omitting the approval field. Calling those episodes "unresolved" would conflate task quality with governance; calling them "safe" would ignore the missing approval. We report both. The governed prompt bundle also changes behavior: on D01 it adds the required `out_of_scope` entry while the verified run reproduces the ungoverned artifact, so the higher governed task-resolution count is not an approval effect.

The phase table is descriptive. With eight parameterizations per phase and one repeated instruction in most phases, phase differences should not be read as stable estimates of difficulty.

### RQ4 — Prompt-injection guardrails

| Detector | Precision | Recall | F1 | FPR |
|---|---|---|---|---|
| Regex rules | 100.0% | 3.3% | 0.063 | 0.0% |
| TF-IDF + LR @0.5 | 87.0% | 77.0% | 0.817 | 6.8% |
| TF-IDF + LR @0.417 | 65.2% | 95.1% | 0.773 | 30.1% |

The rule baseline has high precision and very low recall. The classifier reaches the recall target only at a high false-positive rate, which is unacceptable for silent blocking but plausible as a review-queue signal. The exact operating point and held-out counts are in `results/guardrail_eval.json`.

### RQ5 — Deployment and cost

| Task | Healthy | HTTP | Startup (s) | Restart rc | Error |
|---|---|---|---|---|---|
| P01 | yes | 200 | 6.2 | 0 |  |
| P02 | yes | 200 | 11.4 | 0 |  |
| P03 | yes | - | 11.4 | 0 |  |

These are canonical infrastructure smoke tests, not executions of model-generated deployment artifacts. P01 is an HTTP liveness check; P02 and P03 add dependency and restart checks but do not exercise application logic.


| Model | Policy | Resolve rate | Cost/episode | Cost/resolved | Reviews |
|---|---|---|---|---|---|
| qwen2.5:1.5b | fde_disciplined | 22.9% | $6.47 | $28.23 | 22 |
| qwen2.5:1.5b | governed | 33.3% | $4.70 | $14.11 | 16 |
| qwen2.5:1.5b | ungoverned | 18.8% | $0.59 | $3.14 | 2 |
| qwen2.5:1.5b | verified | 18.8% | $0.59 | $3.14 | 2 |

Generated artifacts are a stricter test: 1 of 32 deployment episodes produced a parsable `services` mapping. We therefore do not claim that generated stacks run. The canonical stacks are liveness checks, not functional deployment tests. Human review dominates the cost model at low resolve rates; the model token cost is small relative to review time.

## External evidence used for calibration

| Source | Date | Headline quantity |
|---|---|---|
| Lightcast, 'What is a Forward Deployed Engineer? The fastest growing AI job.' | 2026-09-15 | us_postings_2024_approx=200; us_postings_2025_approx=1200 |
| CNBC, 'AWS, Anthropic race to deploy army of specialized engineers...' | 2026-10-15 | us_postings_2026_first_nine_months=7300; median_advertised_salary_usd=195456 |
| FDE Jobs in 2026 market report | 2026-06 | employer_boards_scanned=6486; raw_postings=239428 |
| FDE-Bench: Evaluating LLM Agents for Deployment Environment Configuration | 2026-09-23 | tasks=136; checks=2145 |
| Deloitte State of AI in the Enterprise 2026 | 2026 | moved_40pct_plus_experiments_to_production_pct=25; expect_revenue_growth_pct=74 |
| Gartner prediction on agentic AI project cancellation | 2025-06 | over 40% of agentic AI projects canceled by end-2027 |
| Gartner forecast reported by CXOtoday | 2026 | 70% of enterprises abandon vendor-built agentic AI by 2028 |
| CIO, 'Forward-deployed engineering in the age of agentic AI' | 2026-07-29 | governance_layers=5; lifecycle_phases=5 |

These sources are cited, not re-estimated. The repository never overwrites an external number with a local estimate.

## Threats to validity

- **Template structure.** The benchmark has 48 rows but only 6 templates and 13 distinct instructions. Rows within a phase are parameterizations, not independent scenarios. Confidence intervals and paired tests treat them as exchangeable and are therefore optimistic.
- **Rubric leakage.** The model sees the acceptance criteria. High scores measure instruction-following against visible checks, not hidden FDE capability.
- **Model scale.** The reported run uses a 1.5B model. Results characterize this model and task bank, not frontier systems.
- **Single deterministic run.** Each cell is one episode at temperature zero. There is no estimate of run-to-run variance.
- **Governance confound.** `requires_human_approval` is outside the task checks. Governed and disciplined policies are not clean estimates of the causal effect of approval.
- **Market sample.** ATS boards over-represent AI-native companies. The broad FDE-like class is a regex construct; the explicit subset is a sensitivity check, not a ground truth.
- **Salary parsing.** Salary figures come from a keyword-adjacent heuristic and may include OTE, equity-adjacent, or non-base figures.
- **Guardrail corpus.** deepset is small, English-heavy, and older than the 2026 threat landscape. The 95% recall point has a high false-positive rate.
- **Deployment environment.** Canonical smoke tests use cached images and a local Docker daemon. Generated artifacts were parsed but not executed. Registry policy, Kubernetes, and multi-tenant isolation are out of scope.
- **Cost model.** Token prices are shadow prices; the local run has no per-token bill. Human review time is an assumption, not a measurement.

## Reproducibility

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make tasks          # generate and self-check the task bank
make market         # live ATS collection + analysis
make benchmark      # tasks × policies × configured models
make guardrail      # prompt-injection evaluation
make deployment     # canonical Compose smoke tests
make cost stats figures
make report         # regenerate docs/RESEARCH.md and LaTeX tables
make verify         # fail if any claimed artifact is missing
```

The benchmark run is frozen before analysis:

```bash
PYTHONPATH=src python -m fde_research.freeze_run --label final
FDE_EPISODES=results/frozen/benchmark_episodes_final.jsonl make cost stats figures report verify
```

Environment used for the reported run: Python 3.12, Ollama 0.23.2, `qwen2.5:1.5b` (Ollama ID `65ec06548149`), seed 20261022, temperature 0, max tokens 900. Every collector writes a raw snapshot with a retrieval timestamp; the benchmark writes an append-only JSONL and a freeze manifest with a SHA-256.

## Data and ethics

Only public job postings and public benchmark data are used. No customer data, credentials, or personal data are collected. The prompt-injection corpus is public research data. Deployment tests run locally and are torn down after each episode. The repository does not contact production systems.

## Citation

```bibtex
@misc{fde_lifecycle_2026,
  title  = {Forward-Deployed Engineering for Enterprise AI Agents: A Measurement Study and a Null Result for Check-Driven Repair},
  author = {AI FDE Research},
  year   = {2026},
  note   = {Code and task bank: ai-fde-research}
}
```

## License

Code: MIT. Task bank and generated results: CC BY 4.0.
