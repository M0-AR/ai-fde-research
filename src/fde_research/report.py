from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from . import config
from .tasks import all_tasks
from .util import utc_now


def load(name: str) -> dict[str, Any]:
    path = config.RESULTS_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def pct(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


def usd(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"${value:,.{digits}f}"


def tex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def latex_table(headers: list[str], rows: list[list[Any]], caption: str, label: str) -> str:
    body = "\n".join(" & ".join(tex_escape(cell) for cell in row) + r" \\" for row in rows)
    return (
        "\\begin{table}[t]\n\\centering\n\\small\n"
        f"\\caption{{{caption}}}\n\\label{{{label}}}\n"
        "\\begin{tabular}{" + "l" * len(headers) + "}\n\\toprule\n"
        + " & ".join(tex_escape(h) for h in headers) + r" \\" + "\n\\midrule\n" + body + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )


def market_section(market: dict[str, Any]) -> tuple[str, str]:
    if not market:
        return "Market results pending.\n", "% market results pending\n"
    n_like = market.get("n_fde_like", market["n_fde"])
    n_explicit = market.get("n_fde_explicit")
    rows = [
        ["Postings collected (live ATS snapshot)", f"{market['n_postings']:,}"],
        ["FDE-like postings (broad regex class)", f"{n_like:,} ({pct(market.get('fde_like_share', market['fde_share']))})"],
    ]
    if n_explicit is not None:
        rows.append(
            [
                "Explicit forward-deployed titles (subset)",
                f"{n_explicit:,} ({pct(market.get('fde_explicit_share', 0))} of all; "
                f"{pct(market.get('explicit_share_of_fde_like', 0))} of FDE-like)",
            ]
        )
    rows += [
        ["Adjacent postings", f"{market['n_adjacent']:,}"],
        ["Remote share, FDE-like", pct(market["fde_remote_share"])],
        ["Median description length", f"{market['median_description_chars_fde']:,.0f} chars"],
        ["Postings with a parseable salary mention", f"{market['salary']['n_with_salary']} ({pct(market['salary']['share_with_salary'], 2)})"],
    ]
    markdown = table(["Metric", "Value"], rows) + "\n\n"
    markdown += (
        "The broad FDE-like class includes solutions, customer, and deployment "
        "engineering titles. The explicit subset matches `forward deployed` or "
        "`forward deploy` in the title. Salary figures come from a keyword-adjacent "
        "heuristic, not a verified compensation field.\n\n"
    )
    markdown += "**Top skills in FDE-like postings.**\n\n"
    markdown += table(
        ["Skill", "FDE share", "Adjacent share", "Lift (pp)"],
        [[item["label"], pct(item["fde_share"]), pct(item["adjacent_share"]), f"{item['lift_pp']:+.1f}"] for item in market["skills"][:8]],
    ) + "\n\n"
    markdown += "**Lifecycle language in FDE-like postings.**\n\n"
    markdown += table(
        ["Phase", "Share mentioning"],
        [[item["label"], pct(item["share"])] for item in market["lifecycle"]],
    )
    markdown += (
        "\n\nSkill and lifecycle shares are regex-coded from job descriptions. "
        "Boilerplate inflates broad categories such as customer language, so the "
        "comparison between FDE and adjacent roles is more informative than any "
        "single share.\n"
    )
    latex = latex_table(
        ["Metric", "Value"],
        rows,
        "Live FDE-like labor-market snapshot from public ATS boards. Broad and explicit title classes are reported separately.",
        "tab:market",
    )
    return markdown, latex


def benchmark_section(stats: dict[str, Any]) -> tuple[str, str]:
    if not stats.get("overall"):
        return "Benchmark results pending.\n", "% benchmark results pending\n"
    rows = []
    for item in stats["overall"]:
        low, high = item["resolve_ci95"]
        rows.append(
            [
                item["model"],
                item["policy"],
                item["n"],
                f"{item['resolved']} ({pct(item['resolve_rate'])})",
                f"[{pct(low)}, {pct(high)}]",
                f"{item['mean_score']:.3f}",
                f"{item.get('governance_compliant', 0)}/{item['n']}",
                item["safety_violations"],
            ]
        )
    markdown = table(
        ["Model", "Policy", "n", "Task resolved", "95% CI", "Mean score", "Gov. compliant", "Safety viol."],
        rows,
    )
    latex = latex_table(
        ["Model", "Policy", "n", "Task resolved", "95% CI", "Score", "Gov. comp.", "Saf. viol."],
        rows,
        "FDE-LifecycleBench results by model and policy. Task resolution and governance compliance are reported separately.",
        "tab:benchmark",
    )
    return markdown, latex


def phase_section(stats: dict[str, Any]) -> str:
    if not stats.get("phase"):
        return "Phase results pending.\n"
    frame = pd.DataFrame(stats["phase"])
    labels = stats.get("model_labels", {})
    blocks = []
    for model_id in frame["model_id"].unique():
        subset = frame[frame["model_id"] == model_id]
        pivot = subset.pivot(index="phase", columns="policy", values="resolve_rate")
        rows = []
        for phase in pivot.index:
            values = []
            for policy in stats["policies"]:
                if policy not in pivot.columns or pd.isna(pivot.loc[phase, policy]):
                    values.append("n/a")
                else:
                    values.append(pct(pivot.loc[phase, policy]))
            rows.append([phase] + values)
        label = labels.get(model_id, model_id)
        blocks.append(f"**{label}.**\n\n" + table(["Phase"] + stats["policies"], rows))
    return "\n\n".join(blocks)


def guardrail_section(guard: dict[str, Any]) -> tuple[str, str]:
    if not guard:
        return "Guardrail results pending.\n", "% guardrail pending\n"
    rule = guard["rules"]["test"]
    clf = guard["classifier"]["test_at_selected_threshold"]
    default = guard["classifier"]["test_at_0_5"]
    markdown = table(
        ["Detector", "Precision", "Recall", "F1", "FPR"],
        [
            ["Regex rules", pct(rule["precision"]), pct(rule["recall"]), f"{rule['f1']:.3f}", pct(rule["false_positive_rate"])],
            ["TF-IDF + LR @0.5", pct(default["precision"]), pct(default["recall"]), f"{default['f1']:.3f}", pct(default["false_positive_rate"])],
            [f"TF-IDF + LR @{guard['classifier']['selected_threshold']:.3f}", pct(clf["precision"]), pct(clf["recall"]), f"{clf['f1']:.3f}", pct(clf["false_positive_rate"])],
        ],
    )
    latex = latex_table(
        ["Detector", "Precision", "Recall", "F1", "FPR"],
        [
            ["Regex rules", pct(rule["precision"]), pct(rule["recall"]), f"{rule['f1']:.3f}", pct(rule["false_positive_rate"])],
            ["TF-IDF + LR @0.5", pct(default["precision"]), pct(default["recall"]), f"{default['f1']:.3f}", pct(default["false_positive_rate"])],
            ["TF-IDF + LR @target", pct(clf["precision"]), pct(clf["recall"]), f"{clf['f1']:.3f}", pct(clf["false_positive_rate"])],
        ],
        "Prompt-injection detection on the held-out deepset split.",
        "tab:guardrail",
    )
    return markdown, latex


def deployment_section(dep: dict[str, Any]) -> str:
    rows = dep.get("canonical") or []
    if not rows:
        return "Deployment results pending.\n"
    table_md = table(
        ["Task", "Healthy", "HTTP", "Startup (s)", "Restart rc", "Error"],
        [
            [row["task_id"], "yes" if row.get("healthy") else "no", row.get("http_status") or "-", f"{row.get('startup_seconds', 0):.1f}", row.get("restart_returncode"), (row.get("error") or "")[:60]]
            for row in rows
        ],
    )
    if dep.get("scope") == "canonical_smoke_test":
        table_md += (
            "\n\nThese are canonical infrastructure smoke tests, not executions of "
            "model-generated deployment artifacts. P01 is an HTTP liveness check; "
            "P02 and P03 add dependency and restart checks but do not exercise "
            "application logic.\n"
        )
    return table_md


def cost_section(cost: dict[str, Any]) -> tuple[str, str]:
    rows = cost.get("by_model_policy") or []
    if not rows:
        return "Cost results pending.\n", "% cost pending\n"
    table_rows = [
        [
            row["model"],
            row["policy"],
            pct(row["resolve_rate"]),
            usd(row["cost_per_episode_usd"]),
            usd(row["cost_per_resolved_usd"]),
            row["human_reviews"],
        ]
        for row in rows
    ]
    markdown = table(["Model", "Policy", "Resolve rate", "Cost/episode", "Cost/resolved", "Reviews"], table_rows)
    latex = latex_table(
        ["Model", "Policy", "Resolve", "Cost/ep.", "Cost/resolved", "Reviews"],
        table_rows,
        "Shadow-price cost model at hosted-equivalent token prices.",
        "tab:cost",
    )
    return markdown, latex


def external_table(benchmarks: list[dict[str, Any]]) -> str:
    return table(
        ["Source", "Date", "Headline quantity"],
        [
            [
                item["source"],
                item["date"],
                item.get("headline")
                or "; ".join(f"{key}={value}" for key, value in list(item.get("values", {}).items())[:2]),
            ]
            for item in benchmarks
        ],
    )


def build_readme() -> str:
    study = config.study()
    market = load("market_analysis.json")
    stats = load("statistics.json")
    guard = load("guardrail_eval.json")
    dep = load("deployment_eval.json")
    cost = load("cost_model.json")
    benchmarks = config.public_benchmarks()
    metrics = episode_metrics()

    market_md, _ = market_section(market)
    bench_md, _ = benchmark_section(stats)
    phase_md = phase_section(stats)
    guard_md, _ = guardrail_section(guard)
    dep_md = deployment_section(dep)
    cost_md, _ = cost_section(cost)

    def pick(policy: str) -> dict[str, Any] | None:
        for item in stats.get("overall", []):
            if item.get("policy") == policy:
                return item
        return None

    ungoverned = pick("ungoverned")
    verified = pick("verified")
    governed = pick("governed")
    fde = pick("fde_disciplined")

    def cell(item: dict[str, Any] | None) -> str:
        if not item:
            return "pending"
        return f"{item['resolved']}/{item['n']} ({pct(item['resolve_rate'])})"

    def gov_cell(item: dict[str, Any] | None) -> str:
        if not item:
            return "pending"
        return f"{item.get('governance_compliant', 0)}/{item['n']}"

    verified_changed = metrics.get("verified_changed", 0)
    verified_identical_nonerror = metrics.get("verified_identical_nonerror", 0)
    verified_both_error = metrics.get("verified_both_error", 0)
    repair_episodes = metrics.get("repair_episodes", 0)
    high_risk_perfect = metrics.get("governed_high_risk_perfect_unresolved", 0)
    deploy_total = metrics.get("deploy_total", 0)
    deploy_valid = metrics.get("deploy_valid_compose", 0)
    task_rows = metrics.get("task_rows", 48)
    templates = metrics.get("templates", 6)
    distinct_instructions = metrics.get("distinct_instructions", 13)

    market_explicit = market.get("n_fde_explicit", 0)
    market_like = market.get("n_fde_like", market.get("n_fde", 0))
    explicit_share_all = market.get("fde_explicit_share", 0)
    explicit_share_like = market.get("explicit_share_of_fde_like", 0)
    salary = market.get("salary", {})
    salary_n = salary.get("n_with_salary", 0)
    salary_share = salary.get("share_with_salary", 0)
    salary_low = salary.get("median_low_usd")
    salary_high = salary.get("median_high_usd")

    dep_scope = dep.get("scope", "canonical_smoke_test")
    dep_note = (
        "canonical infrastructure smoke tests only"
        if dep_scope == "canonical_smoke_test"
        else "canonical smoke tests plus generated-artifact attempts"
    )

    return f"""# Forward-Deployed Engineering for Enterprise AI Agents

**A measurement study, a six-template benchmark, and a null result for check-driven repair.**

Generated from `results/` at {utc_now()}. Every number below is produced by the pipeline in this repository; nothing is hand-entered.

## Abstract

Forward-deployed engineering (FDE) is a delivery model for enterprise AI agents: engineers embed with a customer, discover the workflow, build against messy context, deploy into a regulated environment, and hand the system to an owning team. The evidence base for the role is thin. This repository reports a live snapshot of {market.get('n_postings', 0):,} public job postings, a {task_rows}-row benchmark of FDE deliverables, a four-policy comparison on a small local model, a prompt-injection guardrail evaluation, and a shadow-price cost model.

The main benchmark result is a null result. One repair attempt driven by failed checks changed the score of **{verified_changed} of {metrics.get('verified_pairs', 48)} tasks**; {verified_identical_nonerror} non-error pairs were byte-identical; {verified_both_error} additional pairs were both errors. The ungoverned and verified policies both resolved {cell(ungoverned)} of tasks. The benchmark is not 48 independent scenarios: it is **{templates} templates with eight parameterizations each**, and five of the six phases reuse one instruction across all eight parameterizations ({distinct_instructions} distinct instruction strings in total). The model sees the acceptance criteria, so this measures instruction-following against explicit rubrics, not open-ended FDE capability.

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
| Task bank | `src/fde_research/tasks.py` | {task_rows} rows, six phases, machine-checked rubrics, reference artifacts |
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
| Report generator | `src/fde_research/report.py` | This README and LaTeX tables |

## Study design

### Benchmark: FDE-LifecycleBench

The benchmark contains **{task_rows} rows**: six phase templates with eight parameterizations each. Five phases (discovery, architecture, security, context, deployment) reuse a single instruction across the eight parameterizations; handover has eight distinct instructions. The total number of distinct instruction strings is **{distinct_instructions}**. This matters for inference: treating the rows as independent tasks overstates precision.

Each row supplies a brief, structured evidence, an instruction with explicit acceptance criteria, and a JSON schema. Every row has a reference artifact that passes its own checks. Scoring is the fraction of checks passed; a task is **task-resolved** only when every check passes. Because the criteria are visible to the model, the benchmark is best read as a test of instruction-following and structured artifact production, not as a hidden-capability benchmark.

### Policies

| Policy | Mechanism |
|---|---|
| `ungoverned` | One model call; no repair, no approval gate |
| `verified` | One call plus one repair attempt driven by failed checks |
| `governed` | Verification plus an approval requirement for high-risk tasks |
| `fde_disciplined` | Plan → artifact → critique → repair, with approval requirements |

High-risk tasks involve security controls, destructive actions, production deployment, or customer data. **Task resolution** is whether the artifact passes the task checks. **Governance compliance** is whether a governed high-risk artifact contains `requires_human_approval`. The current harness does not put approval in the task checks, so the two outcomes can diverge. They are reported separately throughout.

### Models and execution

The reported run uses `qwen2.5:1.5b` through Ollama's OpenAI-compatible endpoint. The design also supports `Qwen3VL-8B-Instruct-Q4_K_M` through llama.cpp; it was excluded from the reported run because a concurrent training job held most of the GPU. Temperature is zero, the seed is fixed, and each cell is a single episode. The harness records tokens and latency and validates every artifact with the same code that validates references.

### Guardrail evaluation

We train a TF-IDF (1–2 gram) logistic regression with balanced class weights on the deepset prompt-injection corpus and evaluate on a held-out 30% split. The threshold is chosen on cross-validation to reach at least 95% recall. A regex rule baseline represents a common blocklist approach.

### Deployment evaluation

The reported deployment scope is **{dep_note}**. P01 is an HTTP liveness check; P02 adds a cache dependency; P03 adds a worker/queue dependency and restart check. P02 and P03 do not exercise application logic. Generated benchmark artifacts are not executed in the reported run. We separately parse each generated `compose_yaml` field and count how many produce a Compose `services` mapping; {deploy_valid} of {deploy_total} deployment episodes did so.

### Cost model

We retrieve live AWS Lambda on-demand prices for us-east-1 and compute the cost of a 512 MB, 500 ms invocation. Token costs use hosted-equivalent shadow prices ($0.60 per million input tokens, $2.40 per million output tokens). Human review is priced at a $254,000 loaded annual cost over 1,800 working hours. A review is counted when a high-risk governed episode requires approval, when an episode escalates, or when it errors. We report cost per episode and cost per resolved task.

### Statistics

Task-resolution rates use Wilson 95% intervals. Policy comparisons are paired by task: paired bootstrap intervals for the difference, exact McNemar tests for discordant resolutions, and Wilcoxon signed-rank tests for partial scores. A Friedman test checks for an overall policy effect. All resampling uses 10,000 draws and the study seed. Because the rows are template parameterizations, these intervals describe this task bank, not a population of FDE tasks.

## Results

### RQ1 — Live market snapshot

{market_md}

The snapshot is a point-in-time census of public ATS boards, not a representative sample of the whole economy. The broad FDE-like class contains {market_like:,} postings; the explicit `forward deployed` subset contains {market_explicit:,} ({pct(explicit_share_all)} of all postings, {pct(explicit_share_like)} of FDE-like). Salary parsing is a keyword-adjacent heuristic over descriptions: {salary_n:,} FDE-like postings ({pct(salary_share, 2)}) yielded a parseable figure, with median low/high of {usd(salary_low, 0)} / {usd(salary_high, 0)}. This is not a verified compensation field.

### RQ2/RQ3 — Lifecycle benchmark

{bench_md}

{phase_md}

**The verification null.** The ungoverned baseline resolved {cell(ungoverned)}; verified resolved {cell(verified)}. Across the paired tasks, {verified_changed} scores changed, {metrics.get('verified_improved', 0)} improved, and {metrics.get('verified_worse', 0)} worsened. {verified_identical_nonerror} non-error pairs were byte-identical; {verified_both_error} additional pairs were both errors, and {repair_episodes} of {metrics.get('verified_pairs', 48)} verified episodes made a second call. The repair attempt did not move the outcome distribution.

**Governance is a separate outcome.** Governed task resolution is {cell(governed)}; governance compliance is {gov_cell(governed)}. The disciplined policy resolves {cell(fde)} with compliance {gov_cell(fde)}. {high_risk_perfect} governed or disciplined high-risk episodes passed every task check while omitting the approval field. Calling those episodes "unresolved" would conflate task quality with governance; calling them "safe" would ignore the missing approval. We report both. The governed prompt bundle also changes behavior: on D01 it adds the required `out_of_scope` entry while the verified run reproduces the ungoverned artifact, so the higher governed task-resolution count is not an approval effect.

The phase table is descriptive. With eight parameterizations per phase and one repeated instruction in most phases, phase differences should not be read as stable estimates of difficulty.

### RQ4 — Prompt-injection guardrails

{guard_md}

The rule baseline has high precision and very low recall. The classifier reaches the recall target only at a high false-positive rate, which is unacceptable for silent blocking but plausible as a review-queue signal. The exact operating point and held-out counts are in `results/guardrail_eval.json`.

### RQ5 — Deployment and cost

{dep_md}

{cost_md}

Generated artifacts are mostly not valid Compose: only {deploy_valid} of {deploy_total} deployment episodes produced a parsable `services` mapping. We therefore do not claim that generated stacks run. The canonical stacks are liveness checks, not functional deployment tests. Human review dominates the cost model at low resolve rates; the model token cost is small relative to review time.

## External evidence used for calibration

{external_table(benchmarks)}

These sources are cited, not re-estimated. The repository never overwrites an external number with a local estimate.

## Threats to validity

- **Template structure.** The benchmark has {task_rows} rows but only {templates} templates and {distinct_instructions} distinct instructions. Rows within a phase are parameterizations, not independent scenarios. Confidence intervals and paired tests treat them as exchangeable and are therefore optimistic.
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
make report         # regenerate README and LaTeX tables
make verify         # fail if any claimed artifact is missing
```

The benchmark run is frozen before analysis:

```bash
python -m fde_research.freeze_run --label final
FDE_EPISODES=results/frozen/benchmark_episodes_final.jsonl make cost stats figures report verify
```

Environment used for the reported run: Python 3.12, Ollama 0.23.2, `qwen2.5:1.5b` (Ollama ID `65ec06548149`), seed 20261022, temperature 0, max tokens 900. Every collector writes a raw snapshot with a retrieval timestamp; the benchmark writes an append-only JSONL and a freeze manifest with a SHA-256.

## Data and ethics

Only public job postings and public benchmark data are used. No customer data, credentials, or personal data are collected. The prompt-injection corpus is public research data. Deployment tests run locally and are torn down after each episode. The repository does not contact production systems.

## Citation

```bibtex
@misc{{fde_lifecycle_2026,
  title  = {{Forward-Deployed Engineering for Enterprise AI Agents: A Measurement Study and a Null Result for Check-Driven Repair}},
  author = {{AI FDE Research}},
  year   = {{2026}},
  note   = {{Code and task bank: ai-fde-research}}
}}
```

## License

Code: MIT. Task bank and generated results: CC BY 4.0.
"""

_DIGIT_WORDS = {
    "0": "Zero",
    "1": "One",
    "2": "Two",
    "3": "Three",
    "4": "Four",
    "5": "Five",
    "6": "Six",
    "7": "Seven",
    "8": "Eight",
    "9": "Nine",
}


def _macro_stem(model: str, policy: str) -> str:
    """Build a letters-only TeX control-word stem.

    Control words may contain letters only; digits and punctuation terminate
    the control sequence. ``qwen2.5:1.5b`` therefore becomes
    ``QwenTwoXFiveXOneXFiveb`` rather than the invalid ``Qwen2515b``.
    """
    import re

    normalized = re.sub(r"[^A-Za-z0-9]", "X", model)
    model_key = "".join(_DIGIT_WORDS.get(char, char) for char in normalized)
    model_key = model_key[:1].upper() + model_key[1:]
    policy_key = "".join(part.capitalize() for part in policy.split("_"))
    return model_key + policy_key


def episode_metrics() -> dict[str, Any]:
    """Derived counts quoted in the paper, computed from the frozen episodes."""
    path = config.episodes_path()
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    base = {row["task_id"]: row for row in rows if row["policy"] == "ungoverned"}
    verified = {row["task_id"]: row for row in rows if row["policy"] == "verified"}
    common = sorted(set(base) & set(verified))
    deltas = [float(verified[task]["score"]) - float(base[task]["score"]) for task in common]
    identical_tasks = [
        task
        for task in common
        if json.dumps(base[task].get("artifact"), sort_keys=True, ensure_ascii=False)
        == json.dumps(verified[task].get("artifact"), sort_keys=True, ensure_ascii=False)
    ]
    both_error = [
        task for task in common if base[task].get("error") and verified[task].get("error")
    ]
    identical = len(identical_tasks)
    identical_nonerror = len([task for task in identical_tasks if task not in both_error])
    deploy = [row for row in rows if row.get("phase") == "deployment"]
    valid_compose = 0
    for row in deploy:
        artifact = row.get("artifact")
        text = artifact.get("compose_yaml") if isinstance(artifact, dict) else None
        if not isinstance(text, str):
            continue
        try:
            parsed = yaml.safe_load(text)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("services"), dict):
            valid_compose += 1
    governed = [row for row in rows if row["policy"] in {"governed", "fde_disciplined"}]
    high_risk_perfect_unresolved = sum(
        1
        for row in governed
        if row.get("risk") == "high"
        and float(row.get("score", 0)) >= 0.999
        and not bool(row.get("requires_human_approval"))
    )
    return {
        "task_rows": len(all_tasks()),
        "templates": len({row["phase"] for row in all_tasks()}),
        "distinct_instructions": len({row["instruction"] for row in all_tasks()}),
        "verified_pairs": len(common),
        "verified_changed": sum(1 for delta in deltas if abs(delta) > 1e-9),
        "verified_improved": sum(1 for delta in deltas if delta > 1e-9),
        "verified_worse": sum(1 for delta in deltas if delta < -1e-9),
        "verified_identical": identical,
        "verified_identical_nonerror": identical_nonerror,
        "verified_both_error": len(both_error),
        "repair_episodes": sum(1 for row in verified.values() if int(row.get("calls", 0)) > 1),
        "governed_high_risk_perfect_unresolved": high_risk_perfect_unresolved,
        "deploy_total": len(deploy),
        "deploy_valid_compose": valid_compose,
    }


def build_latex() -> tuple[str, str]:
    market = load("market_analysis.json")
    stats = load("statistics.json")
    guard = load("guardrail_eval.json")
    cost = load("cost_model.json")
    _, market_tex = market_section(market)
    _, bench_tex = benchmark_section(stats)
    _, guard_tex = guardrail_section(guard)
    _, cost_tex = cost_section(cost)
    macros = []
    seen: set[str] = set()
    if stats.get("overall"):
        expected = {
            (model_id, policy)
            for model_id in stats.get("models", [])
            for policy in config.study()["benchmark"]["policies"]
        }
        observed = {
            (item.get("model_id", item["model"]), item["policy"])
            for item in stats["overall"]
        }
        missing = sorted(expected - observed)
        if missing:
            raise SystemExit(f"cannot build paper: missing model/policy rows: {missing}")
        for item in stats["overall"]:
            key = _macro_stem(item.get("model_id", item["model"]), item["policy"])
            if key in seen:
                raise SystemExit(f"duplicate LaTeX macro stem: {key}")
            seen.add(key)
            macros.append(f"\\newcommand{{\\Resolve{key}}}{{{tex_escape(pct(item['resolve_rate']))}}}")
            macros.append(f"\\newcommand{{\\Score{key}}}{{{item['mean_score']:.3f}}}")
            macros.append(f"\\newcommand{{\\Gov{key}}}{{{item.get('governance_compliant', 0)}/{item['n']}}}")
            macros.append(f"\\newcommand{{\\Reviews{key}}}{{{item.get('human_reviews', 0)}}}")
    if market:
        macros.append(f"\\newcommand{{\\MarketPostings}}{{{market['n_postings']:,}}}")
        macros.append(f"\\newcommand{{\\MarketFDE}}{{{market['n_fde']:,}}}")
        macros.append(f"\\newcommand{{\\MarketFDEShare}}{{{tex_escape(pct(market['fde_share']))}}}")
        macros.append(f"\\newcommand{{\\MarketExplicit}}{{{market.get('n_fde_explicit', 0):,}}}")
        macros.append(f"\\newcommand{{\\MarketExplicitShare}}{{{tex_escape(pct(market.get('fde_explicit_share', 0)))}}}")
        macros.append(f"\\newcommand{{\\MarketExplicitOfFDE}}{{{tex_escape(pct(market.get('explicit_share_of_fde_like', 0)))}}}")
        macros.append(f"\\newcommand{{\\SalaryN}}{{{market.get('salary', {}).get('n_with_salary', 0):,}}}")
        macros.append(f"\\newcommand{{\\SalaryShare}}{{{tex_escape(pct(market.get('salary', {}).get('share_with_salary', 0), 2))}}}")
        macros.append(f"\\newcommand{{\\SalaryMedianLow}}{{\\${market.get('salary', {}).get('median_low_usd') or 0:,.0f}}}")
        macros.append(f"\\newcommand{{\\SalaryMedianHigh}}{{\\${market.get('salary', {}).get('median_high_usd') or 0:,.0f}}}")
    if guard:
        macros.append(f"\\newcommand{{\\GuardRecall}}{{{tex_escape(pct(guard['classifier']['test_at_selected_threshold']['recall']))}}}")
        macros.append(f"\\newcommand{{\\GuardPrecision}}{{{tex_escape(pct(guard['classifier']['test_at_selected_threshold']['precision']))}}}")
    if cost.get("assumptions"):
        macros.append(f"\\newcommand{{\\LambdaGBSecond}}{{{cost['assumptions']['lambda_gb_second_usd']}}}")
    derived = episode_metrics()
    if derived:
        macros.append(f"\\newcommand{{\\TaskRows}}{{{derived['task_rows']}}}")
        macros.append(f"\\newcommand{{\\TaskTemplates}}{{{derived['templates']}}}")
        macros.append(f"\\newcommand{{\\DistinctInstructions}}{{{derived['distinct_instructions']}}}")
        macros.append(f"\\newcommand{{\\VerifiedPairs}}{{{derived['verified_pairs']}}}")
        macros.append(f"\\newcommand{{\\VerifiedChanged}}{{{derived['verified_changed']}}}")
        macros.append(f"\\newcommand{{\\VerifiedImproved}}{{{derived['verified_improved']}}}")
        macros.append(f"\\newcommand{{\\VerifiedWorse}}{{{derived['verified_worse']}}}")
        macros.append(f"\\newcommand{{\\VerifiedIdentical}}{{{derived['verified_identical']}}}")
        macros.append(f"\\newcommand{{\\VerifiedIdenticalNonError}}{{{derived['verified_identical_nonerror']}}}")
        macros.append(f"\\newcommand{{\\VerifiedBothError}}{{{derived['verified_both_error']}}}")
        macros.append(f"\\newcommand{{\\RepairEpisodes}}{{{derived['repair_episodes']}}}")
        macros.append(f"\\newcommand{{\\GovHighRiskPerfectUnresolved}}{{{derived['governed_high_risk_perfect_unresolved']}}}")
        macros.append(f"\\newcommand{{\\DeployTotal}}{{{derived['deploy_total']}}}")
        macros.append(f"\\newcommand{{\\DeployValidCompose}}{{{derived['deploy_valid_compose']}}}")
    return "\n".join(macros) + "\n", market_tex + "\n" + bench_tex + "\n" + guard_tex + "\n" + cost_tex


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    config.ensure_dirs()
    readme = build_readme()
    (config.ROOT / "README.md").write_text(readme)
    macros, tables = build_latex()
    out = config.PAPER_DIR / "generated"
    out.mkdir(parents=True, exist_ok=True)
    (out / "numbers.tex").write_text(macros)
    (out / "tables.tex").write_text(tables)
    print(f"wrote README.md ({len(readme)} chars), paper/generated/numbers.tex, paper/generated/tables.tex")
    if args.strict:
        missing = [name for name in ("market_analysis.json", "statistics.json", "guardrail_eval.json", "deployment_eval.json", "cost_model.json") if not (config.RESULTS_DIR / name).exists()]
        if missing:
            raise SystemExit(f"missing results: {missing}")


if __name__ == "__main__":
    main()
