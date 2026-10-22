# Study protocol

This document records the design of the study before results were interpreted. It is written so that an independent reviewer can determine what was specified in advance, what was changed, and why. The repository is the artifact; this protocol is the contract. Sections 1--11 are the pre-result protocol. Section 12 records post-audit deviations; where they conflict, Section 12 governs the reported analysis.

## 1. Research questions

- **RQ1 (Market).** What does the 2026 labor market ask of forward-deployed engineers (FDEs), and how does the role differ from adjacent solutions and deployment roles?
- **RQ2 (Lifecycle difficulty).** Which phases of the FDE lifecycle are hardest for capable but small open-weight models, and what kinds of failures dominate?
- **RQ3 (Governance).** Do verification, approval gates, and a disciplined delivery loop improve resolve rates, partial scores, or safety relative to an ungoverned baseline?
- **RQ4 (Guardrails).** How well do simple rules and a lightweight classifier detect prompt injection in customer-supplied content?
- **RQ5 (Deployment and cost).** Do generated deployment artifacts actually run, and what does governance cost per resolved task?

The unit of analysis is the **engagement task**, not the model response in isolation. A task is resolved only when every machine-checked acceptance criterion passes.

## 2. Design summary

| Component | Design |
|---|---|
| Market | Cross-sectional census of selected public ATS boards, collected live |
| Benchmark | 48 tasks, 8 per phase, 6 phases, 4 policies, 1 model per full run |
| Guardrail | Public corpus, stratified 70/30 split, rules versus TF-IDF logistic regression |
| Deployment | 3 canonical Compose stacks plus unmodified generated stacks |
| Cost | Live AWS Lambda list price plus shadow token and reviewer prices |
| Statistics | Wilson intervals, paired bootstrap, McNemar, Wilcoxon, Friedman |

## 3. Market data

### 3.1 Sources

Public job postings are collected from:

- Greenhouse boards: Anthropic, Databricks, Scale AI
- Lever: Palantir
- Ashby: OpenAI, Cursor, Sierra
- Remotive search API
- Arbeitnow public API

These sources over-represent AI-native companies. The snapshot is a **census of selected boards**, not a probability sample of the labor market. Demand magnitudes are cited from Lightcast, CNBC, and the FDE Jobs 2026 report rather than estimated from this census.

### 3.2 Deduplication and coding

Records are normalized (HTML stripped, whitespace collapsed, case-folded for hashing) and deduplicated by a SHA-256 of source, company, normalized title, location, and URL, plus a near-duplicate key over the description prefix. Titles are classified by a pre-registered regex taxonomy in `config/taxonomy.yaml` into:

- `fde`: explicit FDE or forward-deployed titles
- `adjacent`: solutions architect, solutions engineer, deployment engineer, AI engineer, applied AI, customer engineer, technical account manager
- `other`: everything else

Descriptions are coded with regex patterns for 13 skills and six lifecycle phases. Regex coding is deliberately transparent and reproducible, but it has known noise: phrases such as "customer" appear in boilerplate. We report shares as descriptive, not causal.

### 3.3 Inclusion

A posting is included if it has a title and a non-empty description. No salary filter is applied. Salary presence is reported separately because it is too sparse for inference.

## 4. FDE-LifecycleBench

### 4.1 Phases and tasks

Six phases, eight tasks each:

1. **Discovery (D01–D08):** stakeholder mapping, success metrics, scoping, data-access negotiation.
2. **Architecture (A01–A08):** agent topology, tool contracts, evaluation harness, failure isolation.
3. **Security (S01–S08):** threat model, permission matrix, egress control, incident response.
4. **Context (C01–C08):** source inventory, chunking, retrieval evaluation, freshness and provenance.
5. **Deployment (P01–P08):** Compose stack, health checks, rollback, observability, secrets.
6. **Handover (H01–H08):** runbook, ownership, known limitations, exit criteria.

Each task contains: `id`, `phase`, `title`, `brief`, `evidence`, `instruction`, `output_schema`, `checks`, `reference`, and `risk`. Tasks are synthetic but grounded in public practitioner guidance and in the FDE-Bench task style. They are not copied from any customer or proprietary source.

### 4.2 Checks

Eighteen check types are implemented in `src/fde_research/validators.py`: equality, numeric comparisons, contains-all and contains-any, minimum item count, non-empty, set membership, boolean equality, regex, required JSON keys, minimum word count, YAML service presence, YAML term presence and absence, and YAML port mapping. A check failure returns a machine-readable reason.

Every task's reference artifact must pass every check. `python -m fde_research.tasks` aborts if any reference fails. This prevents impossible or contradictory rubrics.

### 4.3 Acceptance criteria in the prompt

**Deviation from the first design.** The first benchmark run exposed criteria that the model could not infer from the brief (for example, the exact control names "egress allowlist" and "sanitize output"). That design measured hidden-phrase guessing, not engineering. We changed the prompt builder to append an explicit "ACCEPTANCE CRITERIA (machine-checked, all must pass)" block derived from the same checks used for scoring. The first run was discarded and the benchmark restarted from scratch. This is a pre-result design change; no outcome data from the discarded run is reported.

### 4.4 Policies

- `ungoverned`: one model call, artifact extracted, scored.
- `verified`: up to one repair call seeded with failed check reasons.
- `governed`: the verified loop plus a requirement that high-risk tasks set `requires_human_approval: true`. Missing approval is a safety violation and the episode cannot resolve.
- `fde_disciplined`: plan, artifact, critique, repair; same approval requirement.

Policies are prompts and control flow, not fine-tuning. The same model, temperature, seed, and token budget are used within a model run.

### 4.5 Models and execution

The primary full run uses `qwen2.5:1.5b` through Ollama's OpenAI-compatible endpoint. The intended second model is `Qwen3VL-8B-Instruct-Q4_K_M` through llama.cpp. Temperature is 0.0, `max_tokens` is 900, and the request timeout is 180 seconds. Each cell is one episode; `repeats: 1`.

The 8B model was excluded from the primary run because a concurrent training job held approximately 12 GB of GPU memory and 100% GPU utilization, reducing prompt evaluation to 0.49 tokens/second. This is an environmental limitation, not a model-selection claim. A subset may be added if the GPU frees; otherwise the exclusion is reported under threats to validity.

### 4.6 Metrics

- **Resolved:** all checks pass (primary binary outcome).
- **Score:** fraction of checks passed (secondary, bounded 0–1).
- **Safety violation:** forbidden claim, or missing approval on a high-risk task.
- **Latency and tokens:** recorded per episode.
- **Escalation:** whether the policy requested human review.

## 5. Guardrail evaluation

Corpus: `deepset/prompt-injections` (public; 546 rows). Split: 70/30 stratified, seed 20261022. Baseline: regex rules. Model: TF-IDF (1–2 grams, sublinear term frequency) plus logistic regression with balanced class weights. Threshold: chosen on cross-validation to achieve at least 95% recall. Report held-out precision, recall, F1, and false-positive rate. No test example is used for threshold selection.

## 6. Deployment evaluation

Canonical stacks:

- **P01:** single nginx web tier with health check.
- **P02:** API plus Redis cache, health checks, no host port for Redis.
- **P03:** worker plus queue, no host ports, health check.

Images are locally cached and pinned. Each stack runs with a read-only root filesystem where feasible, a dropped capability set, and an explicit network. Time to healthy, HTTP status, and logs are recorded. Stacks are torn down after each run.

**Deviation.** The host had 32 custom Docker networks, exhausting the default address pools. The evaluator writes `docker-compose.override.yml` with an explicit per-run subnet (`10.20X.Y.0/24`). This changes only address allocation, not application behavior.

Generated stacks from the benchmark are executed unmodified. A generated stack that fails to parse, references an unavailable image, or never becomes healthy counts as a deployment failure. This is reported separately from benchmark resolve rate.

## 7. Cost model

- Lambda: live AWS Price List API, us-east-1, on-demand, x86. Cost per invocation computed for 512 MB and 500 ms from GB-second and request prices.
- Tokens: shadow prices of \$0.60 per million input tokens and \$2.40 per million output tokens.
- Human review: \$254,000 loaded annual cost / 1,800 hours = \$2.3519 per minute; 6 minutes per escalated episode.
- Cost per resolved task = total cost / number resolved.

The cost model is a planning tool, not an invoice. It excludes idle time, travel, procurement, and customer-side review.

## 8. Statistical analysis

- Wilson 95% intervals for proportions.
- Paired bootstrap (10,000 draws) for policy differences on the same tasks.
- Exact McNemar test for discordant resolved/not-resolved pairs.
- Wilcoxon signed-rank for paired partial scores.
- Friedman test for an overall policy effect across tasks.

Tests treat tasks as exchangeable. With 48 tasks and one deterministic episode per cell, intervals are wide; we emphasize effect direction and consistency across phases over significance stars.

## 9. Data provenance and reproducibility

- Every result file records the UTC timestamp, command context where applicable, and input hashes for downloaded datasets.
- Results are generated by code in `src/fde_research/`; no result value is hand-edited.
- `python -m fde_research.verify_results` checks completeness and internal consistency.
- The task bank is regenerated deterministically from `tasks.py`; reference artifacts are validated in tests.
- External numbers are cited in `config/public_benchmarks.yaml` and the paper bibliography; they are not re-estimated.

## 10. Ethics

Public job postings and public research datasets only. No customer data, credentials, or personal information. Prompt-injection examples are used for defense. Deployment tests are local and ephemeral. The benchmark is intended to improve the safety and reliability of enterprise AI delivery.

## 11. Known limitations

- Small local models and a shared GPU limit external validity.
- One deterministic episode per cell limits statistical power.
- Tasks and rubrics are authored by the study team; explicit criteria can reward keyword compliance.
- Market sources over-represent AI-native companies; salary data is too sparse to analyze.
- The guardrail corpus is small, English-heavy, and older than the 2026 threat landscape.
- Compose tests do not cover Kubernetes, registry policy, or multi-tenant isolation.
- The 8B model is excluded from the primary run because of GPU contention.


## 12. Post-audit deviations (2026-10-22)

The first full interpretation of the run exposed four construct-validity problems. They are recorded here rather than silently folded into the original protocol.

### 12.1 Task resolution versus governance compliance

The original metric `resolved` required both all task checks and, for governed high-risk rows, `requires_human_approval`. That conflated two constructs and produced rows with `score=1.0` and `resolved=False`. The reported analysis uses schema v2:

- `task_resolved`: every task check passes.
- `governance_required`: the policy is `governed` or `fde_disciplined` and the task risk is high.
- `governance_compliant`: approval is present when required (vacuously true otherwise).
- `resolved`: retained as an alias for `task_resolved` so older consumers do not silently change meaning.

`requires_human_approval` is not a task acceptance criterion in the current harness. We therefore do **not** interpret a governed high-risk perfect-score artifact as either "unresolved" or "safe"; we report both outcomes.

### 12.2 Model identity

An exception path recorded the model config id (`qwen2.5-1.5b`) in `model` while normal rows recorded the served name (`qwen2.5:1.5b`). This split one model into two groups and inflated the expected cell count. Analysis now groups by `model_id`; `model` is a display label. `freeze_run.py` normalizes legacy rows before analysis.

### 12.3 Deployment scope

The protocol specified executing generated stacks unmodified. The reported run does **not** execute them. The deployment section is a canonical smoke test only: P01 is an HTTP liveness check, P02 adds a cache dependency, and P03 adds a worker/queue dependency. Generated `compose_yaml` artifacts are parsed and counted, but not run. The paper and README state this scope explicitly. The earlier claim that generated stacks were executed is withdrawn.

### 12.4 Market title definition and salary parsing

The broad regex class is reported as **FDE-like**, not "FDE-titled." An explicit `forward deployed` subset is reported as a sensitivity count. The salary parser was broadened to handle comma ranges and single values and restricted to salary-keyword windows; it is a heuristic, not a verified compensation field. Substring regexes for `api`, `rag`, `risk`, `sla`, and related terms were replaced with word-boundary patterns before regenerating the market analysis.

### 12.5 Benchmark structure

The 48 rows are six phase templates with eight parameterizations each. Five phases reuse one instruction across all eight parameterizations; the bank has 13 distinct instruction strings. This was not clear in the original protocol. The paper now treats rows within a phase as parameterizations and warns that confidence intervals and paired tests are optimistic.

### 12.6 Analysis snapshot

The benchmark is allowed to reach 192 episodes (1 model x 4 policies x 48 rows). The run is then copied to `results/frozen/`, normalized to schema v2, hashed, and used for all reported statistics, figures, README, and paper numbers. No analysis is regenerated from a partial file. The live JSONL is never overwritten by the freeze tool.
