from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import config
from .llm_client import LLMClient
from .policies import run_episode
from .schema import (
    effective_model_id,
    governance_compliant,
    human_review_required,
    safety_violation,
    task_resolved,
)
from .util import utc_now, wilson_ci, write_json


def model_configs(selected: list[str] | None = None) -> list[dict[str, Any]]:
    models = config.study()["benchmark"]["models"]
    if selected:
        wanted = set(selected)
        models = [model for model in models if model["id"] in wanted]
    return models


def load_tasks(ids: list[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    path = config.as_path("data", "benchmark", "tasks.json")
    tasks = json.loads(path.read_text())
    if ids:
        wanted = set(ids)
        tasks = [task for task in tasks if task["id"] in wanted]
    if limit:
        tasks = tasks[:limit]
    return tasks


def _key(episode: dict[str, Any]) -> tuple[str, str, str]:
    return episode["task_id"], episode["policy"], episode.get("model_id", episode["model"])


def _load_done(path: Path) -> set[tuple[str, str, str]]:
    done: set[tuple[str, str, str]] = set()
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            done.add(_key(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return done


def summarize(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    phases: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        model_id = effective_model_id(episode)
        groups[(model_id, episode["policy"])].append(episode)
        phases[(model_id, episode["policy"], episode["phase"])].append(episode)

    def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
        resolved = sum(1 for row in rows if task_resolved(row))
        low, high = wilson_ci(resolved, len(rows)) if rows else (0.0, 0.0)
        return {
            "n": len(rows),
            "resolved": resolved,
            "resolve_rate": resolved / len(rows) if rows else 0.0,
            "ci95_low": low,
            "ci95_high": high,
            "mean_score": sum(row["score"] for row in rows) / len(rows) if rows else 0.0,
            "governance_compliant": sum(1 for row in rows if governance_compliant(row)),
            "governance_required": sum(1 for row in rows if row.get("governance_required")),
            "safety_violations": sum(1 for row in rows if safety_violation(row)),
            "human_reviews": sum(1 for row in rows if human_review_required(row)),
            "escalations": sum(1 for row in rows if row["escalated"]),
            "mean_latency_seconds": sum(row["latency_seconds"] for row in rows) / len(rows) if rows else 0.0,
            "total_prompt_tokens": sum(row["prompt_tokens"] for row in rows),
            "total_completion_tokens": sum(row["completion_tokens"] for row in rows),
            "errors": sum(1 for row in rows if row["error"]),
        }

    summary = {
        "generated_at": utc_now(),
        "episodes": len(episodes),
        "by_model_policy": {
            f"{model}|{policy}": stats(rows) for (model, policy), rows in sorted(groups.items())
        },
        "by_phase": {
            f"{model}|{policy}|{phase}": stats(rows)
            for (model, policy, phase), rows in sorted(phases.items())
        },
    }
    return summary


def run(
    *,
    ids: list[str] | None = None,
    policies: list[str] | None = None,
    models: list[str] | None = None,
    limit: int | None = None,
    resume: bool = True,
    repeats: int = 1,
) -> dict[str, Any]:
    config.ensure_dirs()
    bench = config.study()["benchmark"]
    policies = policies or list(bench["policies"])
    tasks = load_tasks(ids, limit)
    out_path = config.as_path("results", "benchmark_episodes.jsonl")
    done = _load_done(out_path) if resume else set()
    if not resume and out_path.exists():
        out_path.unlink()

    total = len(tasks) * len(policies) * len(model_configs(models)) * repeats
    completed = 0
    started = time.time()

    with out_path.open("a") as handle:
        for model_cfg in model_configs(models):
            client = LLMClient(
                base_url=model_cfg["base_url"],
                model=model_cfg["model"],
                timeout=int(bench["request_timeout_seconds"]),
                max_tokens=int(bench["max_tokens"]),
                temperature=float(bench["temperature"]),
                seed=int(config.study()["study"]["seed"]),
            )
            for policy in policies:
                for task in tasks:
                    for repeat in range(repeats):
                        key = (task["id"], policy, model_cfg["id"])
                        if repeat == 0 and key in done:
                            completed += 1
                            continue
                        episode_start = time.time()
                        try:
                            episode = run_episode(task, policy, client)
                        except Exception as exc:  # noqa: BLE001 - transport failure, keep going
                            episode = {
                                "task_id": task["id"],
                                "phase": task["phase"],
                                "risk": task["risk"],
                                "difficulty": task["difficulty"],
                                "policy": policy,
                                "model": model_cfg["model"],
                                "model_id": model_cfg["id"],
                                "resolved": False,
                                "task_resolved": False,
                                "score": 0.0,
                                "checks_passed": 0,
                                "checks_total": len(task["checks"]),
                                "safety_violation": False,
                                "requires_human_approval": None,
                                "governance_required": policy in {"governed", "fde_disciplined"} and task["risk"] == "high",
                                "governance_compliant": not (policy in {"governed", "fde_disciplined"} and task["risk"] == "high"),
                                "governance_noncompliance": "episode error" if policy in {"governed", "fde_disciplined"} and task["risk"] == "high" else "",
                                "human_review_required": True,
                                "escalated": False,
                                "attempts": 0,
                                "calls": 0,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "latency_seconds": time.time() - episode_start,
                                "error": str(exc),
                                "artifact": None,
                                "check_details": [],
                            }
                        episode["model_id"] = model_cfg["id"]
                        episode["model_family"] = model_cfg["family"]
                        episode["repeat"] = repeat
                        episode["timestamp"] = utc_now()
                        handle.write(json.dumps(episode, ensure_ascii=False) + "\n")
                        handle.flush()
                        completed += 1
                        elapsed = time.time() - started
                        eta = (elapsed / completed) * (total - completed) if completed else 0
                        print(
                            f"[{completed}/{total}] {model_cfg['id']} {policy} {task['id']} "
                            f"score={episode['score']:.2f} resolved={episode['resolved']} "
                            f"err={episode['error'][:60]!r} eta={eta / 60:.1f}m",
                            flush=True,
                        )

    episodes = [json.loads(line) for line in out_path.read_text().splitlines() if line.strip()]
    summary = summarize(episodes)
    write_json(config.as_path("results", "benchmark_summary.json"), summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*")
    parser.add_argument("--policies", nargs="*")
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    summary = run(
        ids=args.tasks,
        policies=args.policies,
        models=args.models,
        limit=args.limit,
        resume=not args.no_resume,
        repeats=args.repeats,
    )
    print(json.dumps(summary["by_model_policy"], indent=2))


if __name__ == "__main__":
    main()
