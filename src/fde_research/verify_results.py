"""Verify that result files exist, are mutually consistent, and are complete.

This is not a unit test of the analysis code. It is a submission gate: it
checks that the numbers rendered into README.md and the paper were produced
from a full run, that episodes reconcile with the summary, and that no
placeholder or missing-value marker leaked into a deliverable.

Exit code 0 means all required checks passed. Warnings do not fail the gate.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

from . import config
from .config import FIGURES_DIR, PAPER_DIR, RESULTS_DIR, ROOT
from .schema import (
    effective_model_id,
    governance_compliant,
    governance_required,
    normalize_rows,
    task_resolved,
)
from .tasks import all_tasks
from .validators import validate_reference

REQUIRED_RESULTS = (
    "market_collection.json",
    "market_analysis.json",
    "market_summary.json",
    "benchmark_episodes.jsonl",
    "benchmark_summary.json",
    "guardrail_eval.json",
    "deployment_eval.json",
    "cost_model.json",
    "statistics.json",
)

REQUIRED_FIGURES = (
    "fig_market_roles.png",
    "fig_market_skills.png",
    "fig_benchmark_resolve.png",
    "fig_guardrail.png",
    "fig_deployment.png",
    "fig_cost_effectiveness.png",
)

PLACEHOLDERS = ("TODO", "TBD", "FIXME", "PLACEHOLDER")


def load_json(name: str, errors: list[str]) -> dict[str, Any]:
    path = RESULTS_DIR / name
    if not path.exists():
        errors.append(f"missing result file: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
        return {}


def check_tasks(errors: list[str]) -> None:
    tasks = all_tasks()
    if len(tasks) != 48:
        errors.append(f"task bank has {len(tasks)} tasks, expected 48")
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)):
        errors.append("task ids are not unique")
    for task in tasks:
        result = validate_reference(task)
        if not result["resolved"]:
            failures = [check for check in result["checks"] if not check["passed"]]
            errors.append(f"reference artifact for {task['id']} fails: {failures[:3]}")


def check_market(summary: dict[str, Any], errors: list[str]) -> None:
    if not summary:
        return
    n = summary.get("n_postings", 0)
    parts = summary.get("n_fde", 0) + summary.get("n_adjacent", 0) + summary.get("n_other", 0)
    if n <= 0:
        errors.append("market summary has no postings")
    if parts != n:
        errors.append(f"market role counts ({parts}) do not sum to n_postings ({n})")
    share = summary.get("fde_share", 0)
    if not 0 <= share <= 1:
        errors.append(f"fde_share out of range: {share}")
    if summary.get("n_fde", 0) < 100:
        errors.append("fewer than 100 FDE postings; market snapshot is too thin for the paper")


def check_benchmark(
    episodes: list[dict[str, Any]], summary: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    path = config.episodes_path()
    if not path.exists():
        errors.append(f"missing result file: {path}")
        return
    if not episodes:
        errors.append("benchmark has no episodes")
        return

    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, episode in enumerate(episodes, start=1):
        for key in ("model_id", "model", "policy", "task_id", "score", "resolved", "task_resolved"):
            if key not in episode:
                errors.append(f"episode {index} missing {key}")
                return
        model_id = effective_model_id(episode)
        key = (model_id, episode["policy"], episode["task_id"])
        if key in seen:
            errors.append(f"duplicate episode cell: {key}")
        seen[key] = episode
        score = episode["score"]
        if not isinstance(score, (int, float)) or math.isnan(score) or not 0 <= score <= 1:
            errors.append(f"episode {key} has invalid score {score!r}")
        if bool(episode["task_resolved"]) != bool(episode["resolved"]):
            errors.append(f"episode {key} task_resolved={episode['task_resolved']} but resolved={episode['resolved']}")
        if episode["task_resolved"] and score < 0.999:
            errors.append(f"episode {key} claims task_resolved with score {score}")
        if not episode["task_resolved"] and score >= 0.999 and not episode.get("error"):
            errors.append(f"episode {key} has score 1.0 but task_resolved=False")
        required = bool(episode.get("governance_required", governance_required(episode)))
        compliant = bool(episode.get("governance_compliant", governance_compliant(episode)))
        approval = bool(episode.get("requires_human_approval"))
        if required and compliant and not approval:
            errors.append(f"episode {key} claims governance compliance without approval")
        if required and approval and not compliant:
            errors.append(f"episode {key} has approval but is marked non-compliant")
        if not required and not compliant and not episode.get("error"):
            errors.append(f"episode {key} is non-compliant but has no governance requirement")
        if episode.get("error"):
            warnings.append(f"episode {key} recorded an error: {episode['error']}")

    model_ids = sorted({effective_model_id(episode) for episode in episodes})
    tasks = sorted({episode["task_id"] for episode in episodes})
    if len(tasks) != 48:
        errors.append(f"benchmark covers {len(tasks)} tasks, expected 48")

    configured_policies = list(config.study()["benchmark"]["policies"])
    expected_cells = {
        (model_id, policy, task["id"])
        for model_id in model_ids
        for policy in configured_policies
        for task in all_tasks()
    }
    missing = sorted(expected_cells - set(seen))
    extra = sorted(set(seen) - expected_cells)
    if missing:
        errors.append(f"benchmark is missing {len(missing)} cells, e.g. {missing[:5]}")
    if extra:
        errors.append(f"benchmark has {len(extra)} unexpected cells, e.g. {extra[:5]}")
    expected = len(model_ids) * len(configured_policies) * 48
    if len(episodes) != expected:
        errors.append(
            f"benchmark has {len(episodes)} episodes; expected {expected} "
            f"({len(model_ids)} models x {len(configured_policies)} policies x 48 tasks)"
        )

    overall = summary.get("by_model_policy", {}) if summary else {}
    counts = Counter((effective_model_id(e), e["policy"]) for e in episodes)
    resolved = Counter(
        (effective_model_id(e), e["policy"]) for e in episodes if task_resolved(e)
    )
    compliant = Counter(
        (effective_model_id(e), e["policy"]) for e in episodes if governance_compliant(e)
    )
    if overall:
        for summary_key, row in overall.items():
            model_id, policy = summary_key.split("|", 1)
            key = (model_id, policy)
            if row.get("n") != counts[key]:
                errors.append(f"summary n for {key} is {row.get('n')}, episodes {counts[key]}")
            if row.get("resolved") != resolved[key]:
                errors.append(
                    f"summary resolved for {key} is {row.get('resolved')}, episodes {resolved[key]}"
                )
            if row.get("governance_compliant") != compliant[key]:
                errors.append(
                    f"summary governance_compliant for {key} is {row.get('governance_compliant')}, episodes {compliant[key]}"
                )
    else:
        warnings.append("benchmark summary has no by_model_policy rows")


def check_guardrail(guard: dict[str, Any], errors: list[str]) -> None:
    if not guard:
        return
    if guard.get("n_test", 0) < 100:
        errors.append("guardrail test split is too small")
    for name in ("rules", "classifier"):
        block = guard.get(name, {})
        metrics = block.get("test") or block.get("test_at_selected_threshold") or {}
        for metric in ("precision", "recall", "f1", "false_positive_rate"):
            value = metrics.get(metric)
            if value is None or not 0 <= value <= 1:
                errors.append(f"guardrail {name}.{metric} invalid: {value!r}")
    classifier = guard.get("classifier", {})
    if classifier.get("dataset_sha256") is None and not guard.get("dataset_sha256"):
        errors.append("guardrail result has no dataset hash")


def check_deployment(dep: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if not dep:
        return
    canonical = dep.get("canonical", [])
    if len(canonical) < 3:
        errors.append(f"deployment has {len(canonical)} canonical runs, expected 3")
    for row in canonical:
        if not row.get("healthy"):
            errors.append(f"canonical stack {row.get('task_id')} did not become healthy")
        if not row.get("startup_seconds"):
            errors.append(f"canonical stack {row.get('task_id')} has no duration")
    if "benchmark_artifacts" not in dep:
        if dep.get("scope") != "canonical_smoke_test":
            warnings.append(
                "deployment has no generated-artifact section; declare scope='canonical_smoke_test' "
                "or execute the generated stacks"
            )
    else:
        runs = dep["benchmark_artifacts"]
        if not runs:
            errors.append("deployment benchmark section is empty")


def check_cost(cost: dict[str, Any], errors: list[str]) -> None:
    if not cost:
        return
    rows = cost.get("by_model_policy", [])
    if not rows:
        errors.append("cost model has no rows")
        return
    for row in rows:
        if row.get("total_cost_usd", 0) < 0:
            errors.append(f"cost row {row.get('model_id', row.get('model'))}/{row.get('policy')} is negative")
        if row.get("n", 0) == 0:
            errors.append(f"cost row {row.get('model_id', row.get('model'))}/{row.get('policy')} has no episodes")


def check_stats(stats: dict[str, Any], errors: list[str]) -> None:
    if not stats:
        return
    overall = stats.get("overall", [])
    models = stats.get("models", [])
    policies = stats.get("policies", [])
    expected = len(models) * len(policies)
    if len(overall) != expected:
        errors.append(
            f"statistics has {len(overall)} model/policy rows; expected {expected} "
            f"({len(models)} models x {len(policies)} policies)"
        )
    for row in overall:
        if "model_id" not in row:
            errors.append(f"statistics row has no model_id: {row.get('policy')}")
        interval = row.get("resolve_ci95") or [row.get("ci_low"), row.get("ci_high")]
        low, high = interval
        rate = row.get("resolve_rate")
        if None in (low, high, rate) or not low <= rate <= high:
            errors.append(f"statistics interval invalid for {row.get('policy')}: {row}")
        if "governance_compliant" not in row:
            errors.append(f"statistics row has no governance_compliant: {row.get('policy')}")
    if sum(row.get("n", 0) for row in overall) != stats.get("n_episodes"):
        errors.append("statistics row n does not sum to n_episodes")


def check_deliverables(errors: list[str], warnings: list[str]) -> None:
    for name in REQUIRED_FIGURES:
        if not (FIGURES_DIR / name).exists():
            errors.append(f"missing figure: {FIGURES_DIR / name}")
    for name in ("README.md",):
        if not (ROOT / name).exists():
            errors.append(f"missing deliverable: {name}")
    for name in ("numbers.tex", "tables.tex"):
        path = PAPER_DIR / "generated" / name
        if not path.exists():
            errors.append(f"missing LaTeX artifact: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r"\b(?:nan|NaN|None|TBD)\b", text)
        if match:
            errors.append(f"{path} contains placeholder token {match.group(0)!r}")
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        for token in PLACEHOLDERS:
            if token in text:
                warnings.append(f"README contains placeholder token {token!r}")
        if re.search(r"\b(?:nan|NaN|None)\b", text):
            warnings.append("README contains a missing-value marker")


def main() -> None:
    errors: list[str] = []
    warnings: list[str] = []

    check_tasks(errors)

    market = load_json("market_summary.json", errors)
    guard = load_json("guardrail_eval.json", errors)
    dep = load_json("deployment_eval.json", errors)
    cost = load_json("cost_model.json", errors)
    stats = load_json("statistics.json", errors)
    bsummary = load_json("benchmark_summary.json", errors)

    check_market(market, errors)
    check_guardrail(guard, errors)
    check_deployment(dep, errors, warnings)
    check_cost(cost, errors)
    check_stats(stats, errors)

    episodes: list[dict[str, Any]] = []
    ep_path = config.episodes_path()
    if ep_path.exists():
        for line in ep_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid episode line: {exc}")
    episodes = normalize_rows(episodes)
    check_benchmark(episodes, bsummary, errors, warnings)

    check_deliverables(errors, warnings)

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        print(f"\nverify_results: {len(errors)} failure(s), {len(warnings)} warning(s)")
        raise SystemExit(1)
    print(f"verify_results: ok ({len(warnings)} warning(s))")


if __name__ == "__main__":
    main()
