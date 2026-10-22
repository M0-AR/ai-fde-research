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
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .config import FIGURES_DIR, PAPER_DIR, RESULTS_DIR, ROOT
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
    path = RESULTS_DIR / "benchmark_episodes.jsonl"
    if not path.exists():
        errors.append(f"missing result file: {path}")
        return
    if not episodes:
        errors.append("benchmark has no episodes")
        return

    seen: set[tuple[str, str, str]] = set()
    for index, episode in enumerate(episodes, start=1):
        for key in ("model", "policy", "task_id", "score", "resolved"):
            if key not in episode:
                errors.append(f"episode {index} missing {key}")
                return
        key = (episode["model"], episode["policy"], episode["task_id"])
        if key in seen:
            errors.append(f"duplicate episode: {key}")
        seen.add(key)
        score = episode["score"]
        if not isinstance(score, (int, float)) or math.isnan(score) or not 0 <= score <= 1:
            errors.append(f"episode {key} has invalid score {score!r}")
        if episode["resolved"] and score < 0.999:
            errors.append(f"episode {key} claims resolved with score {score}")
        if episode.get("error"):
            warnings.append(f"episode {key} recorded an error: {episode['error']}")

    models = sorted({episode["model"] for episode in episodes})
    policies = sorted({episode["policy"] for episode in episodes})
    tasks = sorted({episode["task_id"] for episode in episodes})
    expected = len(models) * len(policies) * 48
    if len(episodes) != expected:
        errors.append(
            f"benchmark has {len(episodes)} episodes; expected {expected} "
            f"({len(models)} models x {len(policies)} policies x 48 tasks)"
        )
    if len(tasks) != 48:
        errors.append(f"benchmark covers {len(tasks)} tasks, expected 48")

    overall = summary.get("by_model_policy", {}) if summary else {}
    counts = Counter((e["model"], e["policy"]) for e in episodes)
    resolved = Counter(
        (e["model"], e["policy"]) for e in episodes if e.get("resolved")
    )
    if overall:
        for summary_key, row in overall.items():
            model, policy = summary_key.split("|", 1)
            key = (model, policy)
            if row.get("n") != counts[key]:
                errors.append(f"summary n for {key} is {row.get('n')}, episodes {counts[key]}")
            if row.get("resolved") != resolved[key]:
                errors.append(
                    f"summary resolved for {key} is {row.get('resolved')}, episodes {resolved[key]}"
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


def check_deployment(dep: dict[str, Any], errors: list[str]) -> None:
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
    if "benchmark_artifacts" in dep:
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
        if row.get("total_cost_usd", 0) <= 0:
            errors.append(f"cost row {row.get('model')}/{row.get('policy')} is non-positive")
        if row.get("n", 0) == 0:
            errors.append(f"cost row {row.get('model')}/{row.get('policy')} has no episodes")


def check_stats(stats: dict[str, Any], errors: list[str]) -> None:
    if not stats:
        return
    overall = stats.get("overall", [])
    if len(overall) < 4:
        errors.append("statistics has fewer than four policy rows")
    for row in overall:
        interval = row.get("resolve_ci95") or [row.get("ci_low"), row.get("ci_high")]
        low, high = interval
        rate = row.get("resolve_rate")
        if None in (low, high, rate) or not low <= rate <= high:
            errors.append(f"statistics interval invalid for {row.get('policy')}: {row}")


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
        for token in ("nan", "None", "TBD"):
            if token in text:
                errors.append(f"{path} contains placeholder token {token!r}")
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
    check_deployment(dep, errors)
    check_cost(cost, errors)
    check_stats(stats, errors)

    episodes: list[dict[str, Any]] = []
    ep_path = RESULTS_DIR / "benchmark_episodes.jsonl"
    if ep_path.exists():
        for line in ep_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid episode line: {exc}")
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
