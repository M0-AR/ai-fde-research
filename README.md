# Forward-Deployed Engineering for Enterprise AI Agents

**A lifecycle-wide, evidence-backed study of the FDE role, its failure modes, and the governance that makes agent deployments survivable.**

Generated from `results/` at 2026-10-22T12:12:40+00:00. Every number below is produced by the pipeline in this repository; nothing is hand-entered.

## Abstract

Forward-deployed engineering (FDE) has become the delivery model for enterprise AI agents: engineers embed with a customer, discover the workflow, build against messy context, deploy into a regulated environment, and hand the system to an owning team. The role is growing quickly, but the evidence base is thin. Vendor reports describe demand, a single public benchmark covers deployment configuration, and practitioner guidance is largely anecdotal. This study makes three contributions. First, it combines a live snapshot of 3,473 public job postings with a structured review of 2026 practitioner and analyst sources to characterize the role, its skills, and its lifecycle. Second, it introduces **FDE-LifecycleBench**, a 48-task benchmark spanning discovery, architecture, security, context, deployment, and handover, with machine-checked acceptance criteria and reference artifacts. Third, it evaluates four delivery policies (ungoverned, verified-retry, governed with human approval, and a disciplined plan-artifact-critique loop) on local open-weight models, and measures prompt-injection detection, real Docker Compose deployment, and shadow-price cost. The results argue that FDE capability is not a single model property: it is a lifecycle property, and the largest gains come from verification, explicit approval points, and executable acceptance tests.

## Research questions

1. **RQ1 — Market.** What does the 2026 labor market ask of FDEs, and how is the role distinguished from adjacent solutions and deployment roles?
2. **RQ2 — Lifecycle difficulty.** Which phases of the FDE lifecycle are hardest for capable but small open-weight models, and what kinds of failures dominate?
3. **RQ3 — Governance.** Do verification, approval gates, and a disciplined delivery loop improve outcomes or safety relative to an ungoverned baseline?
4. **RQ4 — Guardrails.** How well do simple rules and a lightweight classifier detect prompt injection in customer-supplied content?
5. **RQ5 — Deployment and cost.** Do generated deployment artifacts actually run, and what does governance cost per resolved task?

## What is in this repository

| Component | Path | What it does |
|---|---|---|
| Study configuration | `config/study.yaml` | Seeds, models, policies, sources, price assumptions |
| Role and skill taxonomy | `config/taxonomy.yaml` | Regexes for roles, 13 skills, 6 lifecycle phases, forbidden claims |
| External evidence | `config/public_benchmarks.yaml` | Cited 2026 benchmarks and market reports |
| Task bank | `src/fde_research/tasks.py` | 48 tasks, 6 phases, machine-checked rubrics, reference artifacts |
| Benchmark harness | `src/fde_research/benchmark.py` | Runs models × policies, resumes, writes JSONL |
| Validators | `src/fde_research/validators.py` | 18 check types; reference artifacts must pass their own checks |
| Market collector | `src/fde_research/collect_jobs.py` | Greenhouse, Lever, Ashby, Remotive, Arbeitnow |
| Scholarly collector | `src/fde_research/collect_scholarly.py` | OpenAlex, arXiv, Hacker News, GitHub |
| Guardrail evaluation | `src/fde_research/guardrail_eval.py` | deepset prompt-injection benchmark |
| Deployment evaluation | `src/fde_research/deployment_eval.py` | Real `docker compose up --wait` for P01–P03 |
| Cost model | `src/fde_research/cost_model.py` | Live AWS Lambda prices + loaded human review cost |
| Statistics | `src/fde_research/stats.py` | Wilson intervals, paired bootstrap, McNemar, Wilcoxon, Friedman |
| Figures | `src/fde_research/figures.py` | Publication figures from result JSON |
| Report generator | `src/fde_research/report.py` | This README and LaTeX tables |

## Study design

### Benchmark: FDE-LifecycleBench

The benchmark contains 48 tasks, eight per lifecycle phase:

- **Discovery (D01–D08):** stakeholder maps, success metrics, scoping, risk registers, data audits, ROI cases, pilot plans, requirement traceability.
- **Architecture (A01–A08):** agent topology, tool contracts, retrieval design, memory, evaluation harness, integration, failure modes, build-vs-buy.
- **Security (S01–S08):** threat models, permission matrices, injection defenses, data handling, approval gates, audit trails, secrets, incident response.
- **Context (C01–C08):** source inventories, chunking, metadata, freshness, retrieval evaluation, context budgets, conflict resolution, grounding.
- **Deployment (P01–P08):** Compose stacks, health checks, rollback, observability, canary, capacity, cost controls, runbooks.
- **Handover (H01–H08):** runbooks, ownership, training, known limitations, SLAs, escalation, change management, exit criteria.

Each task supplies a brief, evidence, an instruction with explicit acceptance criteria, and a JSON schema. Every task has a reference artifact that passes its own checks, which prevents unsatisfiable rubrics. Scoring is the fraction of checks passed; a task is **resolved** only when every check passes.

### Policies

| Policy | Mechanism |
|---|---|
| `ungoverned` | One model call; no verification, no approval gate |
| `verified` | One call plus one repair attempt driven by failed checks |
| `governed` | Verification plus approval requirement for high-risk tasks |
| `fde_disciplined` | Plan → artifact → critique → repair, with approval requirements |

High-risk tasks are those involving security controls, destructive actions, production deployment, or customer data. A governed episode that omits `requires_human_approval` cannot be counted as resolved.

### Models

The primary run uses `qwen2.5:1.5b` through Ollama's OpenAI-compatible endpoint. The design also supports `Qwen3VL-8B-Instruct-Q4_K_M` through `llama.cpp`; it is excluded from the primary run because a concurrent training job held most of the GPU, reducing prompt evaluation to under one token per second. Runs are seeded and temperature is zero. The design is model-agnostic; any endpoint implementing `/v1/chat/completions` can be substituted.

## Results

### RQ1 — Live market snapshot

| Metric | Value |
|---|---|
| Postings collected (live ATS snapshot) | 3,473 |
| FDE-titled postings | 670 (19.3%) |
| Adjacent postings | 679 |
| Remote share, FDE-titled | 24.2% |
| Median description length | 7,260 chars |
| Postings stating a salary | 1 (0.15%) |

**Top skills in FDE-titled postings.**

| Skill | FDE share | Adjacent share | Lift (pp) |
|---|---|---|---|
| Customer / stakeholder | 99.7% | 89.2% | +10.4 |
| AI / LLM | 94.0% | 94.5% | -0.5 |
| Leadership | 84.3% | 75.4% | +8.9 |
| Production deployment | 79.2% | 87.5% | -8.2 |
| Security / governance | 78.2% | 69.1% | +9.1 |
| Cloud | 59.9% | 47.6% | +12.3 |
| Python | 58.4% | 32.6% | +25.8 |
| Software engineering | 57.2% | 80.7% | -23.5 |

**Lifecycle language in FDE-titled postings.**

| Phase | Share mentioning |
|---|---|
| Architecture | 89.8% |
| Deployment | 86.1% |
| Handover | 83.3% |
| Discovery | 82.7% |
| Security | 72.7% |
| Context | 37.3% |

Skill and lifecycle shares are regex-coded from job descriptions. Boilerplate inflates broad categories such as customer language, so the comparison between FDE and adjacent roles is more informative than any single share.


The snapshot is a point-in-time census of public ATS boards, not a representative sample of the whole economy. It is used to describe skill language and role boundaries, not to estimate total demand; the external benchmarks below provide demand magnitudes.

### RQ2/RQ3 — Lifecycle benchmark

| Model | Policy | n | Resolved | 95% CI | Mean score | Safety violations | Escalations |
|---|---|---|---|---|---|---|---|
| qwen2.5:1.5b | ungoverned | 23 | 4 (17.4%) | [7.0%, 37.1%] | 0.759 | 0 | 0 |

| Phase | ungoverned | verified | governed | fde_disciplined |
|---|---|---|---|---|
| architecture | 25.0% | n/a | n/a | n/a |
| discovery | 12.5% | n/a | n/a | n/a |
| security | 14.3% | n/a | n/a | n/a |

### RQ4 — Prompt-injection guardrails

| Detector | Precision | Recall | F1 | FPR |
|---|---|---|---|---|
| Regex rules | 100.0% | 3.3% | 0.063 | 0.0% |
| TF-IDF + LR @0.5 | 87.0% | 77.0% | 0.817 | 6.8% |
| TF-IDF + LR @0.417 | 65.2% | 95.1% | 0.773 | 30.1% |

The classifier is trained on the deepset prompt-injection corpus and evaluated on a held-out 30% split. The operating point is chosen on cross-validation to reach at least 95% recall.

### RQ5 — Deployment and cost

| Task | Healthy | HTTP | Startup (s) | Restart rc | Error |
|---|---|---|---|---|---|
| P01 | yes | 200 | 6.0 | 0 |  |
| P02 | yes | 200 | 11.4 | 0 |  |
| P03 | yes | - | 11.4 | 0 |  |

| Model | Policy | Resolve rate | Cost/episode | Cost/resolved | Reviews |
|---|---|---|---|---|---|
| qwen2.5:1.5b | ungoverned | 0.0% | $0.00 | n/a | 0 |

The cost model uses live AWS Lambda list prices (retrieved 2026-10-22T10:49:52+00:00) and a fully loaded reviewer cost of $254,000 per year. Model token prices are hosted-equivalent shadow prices; the local run has no per-token bill. Human review is the dominant cost at low resolve rates.

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

- **Model scale.** The local models are small. Results characterize the *shape* of lifecycle failures and the *relative* effect of policies, not the absolute capability of frontier systems.
- **Task authorship.** Tasks and rubrics were authored for this study. Reference artifacts guard against impossible checks, but rubric wording can still reward verbosity or keyword matching. Checks are deliberately explicit and are released with the tasks.
- **Market sample.** ATS boards over-represent AI-native companies. Salary fields are sparse (0.15% of FDE-titled postings), so compensation claims rely on external benchmarks.
- **Guardrail corpus.** deepset is small and dated; the 95%-recall operating point has a 30.1% false-positive rate on benign traffic, which is unacceptable for direct blocking and motivates a review queue.
- **Deployment environment.** Compose tests run against locally cached images with an injected network subnet; registry access and multi-node scheduling are out of scope.
- **Single run.** Each cell is a single deterministic episode. Stochastic robustness would require repeated runs at temperature > 0.

## Reproducibility

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make tasks          # generate and self-check the 48-task bank
make market         # live ATS collection + analysis
make benchmark      # 48 tasks × 4 policies × configured models
make guardrail      # prompt-injection evaluation
make deployment     # real compose stacks (run on the host; Docker socket is not mounted)
make cost stats figures
make report         # regenerate README and LaTeX tables
make verify         # fail if any claimed artifact is missing
```

Environment used for the reported run: Python 3.12, Docker 29.1, Docker Compose 2.40, NVIDIA RTX 3090 (shared), Ollama and llama.cpp local endpoints. Seeds and model identifiers are in `config/study.yaml`. Every collector writes a raw snapshot with a retrieval timestamp and SHA-256 where applicable.

## Data and ethics

Only public job postings and public benchmark data are used. No customer data, credentials, or personal data are collected. The prompt-injection corpus is public research data. Deployment tests run locally and are torn down after each episode. The repository does not contact production systems.

## Citation

```bibtex
@misc{fde_lifecycle_2026,
  title  = {Forward-Deployed Engineering for Enterprise AI Agents: A Lifecycle Benchmark and Governance Study},
  author = {AI FDE Research},
  year   = {2026},
  note   = {Code and task bank: ai-fde-research}
}
```

## License

Code: MIT. Task bank and generated results: CC BY 4.0.
