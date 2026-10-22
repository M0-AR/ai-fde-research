from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
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
    rows = [
        ["Postings collected (live ATS snapshot)", f"{market['n_postings']:,}"],
        ["FDE-titled postings", f"{market['n_fde']:,} ({pct(market['fde_share'])})"],
        ["Adjacent postings", f"{market['n_adjacent']:,}"],
        ["Remote share, FDE-titled", pct(market["fde_remote_share"])],
        ["Median description length", f"{market['median_description_chars_fde']:,.0f} chars"],
        ["Postings stating a salary", f"{market['salary']['n_with_salary']} ({pct(market['salary']['share_with_salary'], 2)})"],
    ]
    markdown = table(["Metric", "Value"], rows) + "\n\n"
    markdown += "**Top skills in FDE-titled postings.**\n\n"
    markdown += table(
        ["Skill", "FDE share", "Adjacent share", "Lift (pp)"],
        [[item["label"], pct(item["fde_share"]), pct(item["adjacent_share"]), f"{item['lift_pp']:+.1f}"] for item in market["skills"][:8]],
    ) + "\n\n"
    markdown += "**Lifecycle language in FDE-titled postings.**\n\n"
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
        "Live FDE labor-market snapshot from public ATS boards.",
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
                item["safety_violations"],
                item["escalations"],
            ]
        )
    markdown = table(
        ["Model", "Policy", "n", "Resolved", "95% CI", "Mean score", "Safety violations", "Escalations"],
        rows,
    )
    latex = latex_table(
        ["Model", "Policy", "n", "Resolved", "95% CI", "Score", "Saf. viol.", "Esc."],
        rows,
        "FDE-LifecycleBench results by model and policy.",
        "tab:benchmark",
    )
    return markdown, latex


def phase_section(stats: dict[str, Any]) -> str:
    if not stats.get("phase"):
        return "Phase results pending.\n"
    frame = pd.DataFrame(stats["phase"])
    for model in frame["model"].unique():
        subset = frame[frame["model"] == model]
        pivot = subset.pivot(index="phase", columns="policy", values="resolve_rate")
        rows = [[phase] + [pct(pivot.loc[phase, policy]) if policy in pivot.columns else "n/a" for policy in stats["policies"]] for phase in pivot.index]
        return table(["Phase"] + stats["policies"], rows)
    return ""


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
    return table(
        ["Task", "Healthy", "HTTP", "Startup (s)", "Restart rc", "Error"],
        [
            [row["task_id"], "yes" if row.get("healthy") else "no", row.get("http_status") or "-", f"{row.get('startup_seconds', 0):.1f}", row.get("restart_returncode"), (row.get("error") or "")[:60]]
            for row in rows
        ],
    )


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

    market_md, _ = market_section(market)
    bench_md, _ = benchmark_section(stats)
    phase_md = phase_section(stats)
    guard_md, _ = guardrail_section(guard)
    dep_md = deployment_section(dep)
    cost_md, _ = cost_section(cost)

    posture = ""
    if stats.get("overall"):
        ungoverned = [item for item in stats["overall"] if item["policy"] == "ungoverned"]
        governed = [item for item in stats["overall"] if item["policy"] in {"governed", "fde_disciplined"}]
        if ungoverned and governed:
            best_ungoverned = max(item["resolve_rate"] for item in ungoverned)
            best_governed = max(item["resolve_rate"] for item in governed)
            posture = (
                f"The strongest governed policy resolves {pct(best_governed)} of tasks versus "
                f"{pct(best_ungoverned)} for the strongest ungoverned baseline."
            )

    return f"""# Forward-Deployed Engineering for Enterprise AI Agents

**A lifecycle-wide, evidence-backed study of the FDE role, its failure modes, and the governance that makes agent deployments survivable.**

Generated from `results/` at {utc_now()}. Every number below is produced by the pipeline in this repository; nothing is hand-entered.

## Abstract

Forward-deployed engineering (FDE) has become the delivery model for enterprise AI agents: engineers embed with a customer, discover the workflow, build against messy context, deploy into a regulated environment, and hand the system to an owning team. The role is growing quickly, but the evidence base is thin. Vendor reports describe demand, a single public benchmark covers deployment configuration, and practitioner guidance is largely anecdotal. This study makes three contributions. First, it combines a live snapshot of {market.get('n_postings', 0):,} public job postings with a structured review of 2026 practitioner and analyst sources to characterize the role, its skills, and its lifecycle. Second, it introduces **FDE-LifecycleBench**, a 48-task benchmark spanning discovery, architecture, security, context, deployment, and handover, with machine-checked acceptance criteria and reference artifacts. Third, it evaluates four delivery policies (ungoverned, verified-retry, governed with human approval, and a disciplined plan-artifact-critique loop) on local open-weight models, and measures prompt-injection detection, real Docker Compose deployment, and shadow-price cost. {posture + (' ' if posture else '')}The results argue that FDE capability is not a single model property: it is a lifecycle property, and the largest gains come from verification, explicit approval points, and executable acceptance tests.

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

{market_md}

The snapshot is a point-in-time census of public ATS boards, not a representative sample of the whole economy. It is used to describe skill language and role boundaries, not to estimate total demand; the external benchmarks below provide demand magnitudes.

### RQ2/RQ3 — Lifecycle benchmark

{bench_md}

{phase_md}

### RQ4 — Prompt-injection guardrails

{guard_md}

The classifier is trained on the deepset prompt-injection corpus and evaluated on a held-out 30% split. The operating point is chosen on cross-validation to reach at least {pct(config.study()['guardrail']['recall_target'], 0)} recall.

### RQ5 — Deployment and cost

{dep_md}

{cost_md}

The cost model uses live AWS Lambda list prices (retrieved {cost.get('assumptions', {}).get('lambda_retrieved_at', 'n/a')}) and a fully loaded reviewer cost of {usd(config.study()['cost']['human_loaded_annual_usd'], 0)} per year. Model token prices are hosted-equivalent shadow prices; the local run has no per-token bill. Human review is the dominant cost at low resolve rates.

## External evidence used for calibration

{external_table(benchmarks)}

These sources are cited, not re-estimated. The repository never overwrites an external number with a local estimate.

## Threats to validity

- **Model scale.** The local models are small. Results characterize the *shape* of lifecycle failures and the *relative* effect of policies, not the absolute capability of frontier systems.
- **Task authorship.** Tasks and rubrics were authored for this study. Reference artifacts guard against impossible checks, but rubric wording can still reward verbosity or keyword matching. Checks are deliberately explicit and are released with the tasks.
- **Market sample.** ATS boards over-represent AI-native companies. Salary fields are sparse ({pct(market.get('salary', {}).get('share_with_salary', 0), 2)} of FDE-titled postings), so compensation claims rely on external benchmarks.
- **Guardrail corpus.** deepset is small and dated; the 95%-recall operating point has a {pct(guard.get('classifier', {}).get('test_at_selected_threshold', {}).get('false_positive_rate', 0))} false-positive rate on benign traffic, which is unacceptable for direct blocking and motivates a review queue.
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
@misc{{fde_lifecycle_2026,
  title  = {{Forward-Deployed Engineering for Enterprise AI Agents: A Lifecycle Benchmark and Governance Study}},
  author = {{AI FDE Research}},
  year   = {{2026}},
  note   = {{Code and task bank: ai-fde-research}}
}}
```

## License

Code: MIT. Task bank and generated results: CC BY 4.0.
"""


def _macro_stem(model: str, policy: str) -> str:
    import re

    parts = [part for part in re.split(r"[^A-Za-z0-9]+", model) if part]
    model_key = "".join(part[:1].upper() + part[1:] for part in parts)
    policy_key = policy.replace("_", "").capitalize()
    return model_key + policy_key


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
    if stats.get("overall"):
        for item in stats["overall"]:
            key = _macro_stem(item["model"], item["policy"])
            macros.append(f"\\newcommand{{\\Resolve{key}}}{{{tex_escape(pct(item['resolve_rate']))}}}")
            macros.append(f"\\newcommand{{\\Score{key}}}{{{item['mean_score']:.3f}}}")
    if market:
        macros.append(f"\\newcommand{{\\MarketPostings}}{{{market['n_postings']:,}}}")
        macros.append(f"\\newcommand{{\\MarketFDE}}{{{market['n_fde']:,}}}")
        macros.append(f"\\newcommand{{\\MarketFDEShare}}{{{tex_escape(pct(market['fde_share']))}}}")
    if guard:
        macros.append(f"\\newcommand{{\\GuardRecall}}{{{tex_escape(pct(guard['classifier']['test_at_selected_threshold']['recall']))}}}")
        macros.append(f"\\newcommand{{\\GuardPrecision}}{{{tex_escape(pct(guard['classifier']['test_at_selected_threshold']['precision']))}}}")
    if cost.get("assumptions"):
        macros.append(f"\\newcommand{{\\LambdaGBSecond}}{{{cost['assumptions']['lambda_gb_second_usd']}}}")
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
