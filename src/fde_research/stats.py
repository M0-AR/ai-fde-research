from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import numpy as np
from scipy import stats as st

from . import config
from .util import bootstrap_ci, utc_now, wilson_ci, write_json


def _episodes() -> list[dict[str, Any]]:
    path = config.RESULTS_DIR / "benchmark_episodes.jsonl"
    if not path.exists():
        raise SystemExit("no benchmark episodes")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _paired(rows: list[dict[str, Any]], base: str, treatment: str) -> dict[str, Any]:
    by_task: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_task[row["task_id"]][row["policy"]] = row
    pairs = [
        (task, values[base], values[treatment])
        for task, values in by_task.items()
        if base in values and treatment in values
    ]
    if not pairs:
        return {"n_pairs": 0}
    base_res = np.array([int(pair[1]["resolved"]) for pair in pairs])
    treat_res = np.array([int(pair[2]["resolved"]) for pair in pairs])
    deltas = treat_res - base_res
    discordant_b = int(((base_res == 1) & (treat_res == 0)).sum())
    discordant_c = int(((base_res == 0) & (treat_res == 1)).sum())
    mcnemar_p = float(st.binomtest(discordant_c, discordant_b + discordant_c, 0.5).pvalue) if discordant_b + discordant_c else 1.0
    base_scores = np.array([float(pair[1]["score"]) for pair in pairs])
    treat_scores = np.array([float(pair[2]["score"]) for pair in pairs])
    try:
        wilcoxon = float(st.wilcoxon(treat_scores, base_scores, zero_method="zsplit").pvalue)
    except ValueError:
        wilcoxon = 1.0
    low, high = bootstrap_ci(
        deltas,
        resamples=int(config.study()["statistics"]["bootstrap_resamples"]),
        seed=int(config.study()["study"]["seed"]),
    )
    return {
        "n_pairs": len(pairs),
        "base_resolved": int(base_res.sum()),
        "treatment_resolved": int(treat_res.sum()),
        "delta_pp": round(float(deltas.mean() * 100), 2),
        "delta_ci95_pp": [round(low * 100, 2), round(high * 100, 2)],
        "discordant_base_only": discordant_b,
        "discordant_treatment_only": discordant_c,
        "mcnemar_exact_p": mcnemar_p,
        "mean_score_delta": round(float((treat_scores - base_scores).mean()), 4),
        "wilcoxon_p": wilcoxon,
    }


def main() -> None:
    config.ensure_dirs()
    rows = _episodes()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["policy"])].append(row)

    models = sorted({row["model"] for row in rows})
    policies = list(config.study()["benchmark"]["policies"])
    payload: dict[str, Any] = {
        "generated_at": utc_now(),
        "n_episodes": len(rows),
        "models": models,
        "policies": policies,
        "overall": [],
        "phase": [],
        "paired_vs_ungoverned": {},
        "cochran_q": {},
    }

    for (model, policy), items in sorted(groups.items()):
        resolved = sum(1 for item in items if item["resolved"])
        low, high = wilson_ci(resolved, len(items))
        scores = [float(item["score"]) for item in items]
        slow, shigh = bootstrap_ci(
            scores,
            resamples=int(config.study()["statistics"]["bootstrap_resamples"]),
            seed=int(config.study()["study"]["seed"]),
        )
        payload["overall"].append(
            {
                "model": model,
                "policy": policy,
                "n": len(items),
                "resolved": resolved,
                "resolve_rate": round(resolved / len(items), 4),
                "resolve_ci95": [round(low, 4), round(high, 4)],
                "mean_score": round(float(np.mean(scores)), 4),
                "mean_score_ci95": [round(slow, 4), round(shigh, 4)],
                "safety_violations": sum(1 for item in items if item["safety_violation"]),
                "escalations": sum(1 for item in items if item["escalated"]),
                "errors": sum(1 for item in items if item["error"]),
            }
        )

    phase_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        phase_groups[(row["model"], row["policy"], row["phase"])].append(row)
    for (model, policy, phase), items in sorted(phase_groups.items()):
        payload["phase"].append(
            {
                "model": model,
                "policy": policy,
                "phase": phase,
                "n": len(items),
                "resolved": sum(1 for item in items if item["resolved"]),
                "resolve_rate": round(sum(1 for item in items if item["resolved"]) / len(items), 4),
                "mean_score": round(float(np.mean([item["score"] for item in items])), 4),
            }
        )

    for model in models:
        model_rows = [row for row in rows if row["model"] == model]
        if "ungoverned" not in {row["policy"] for row in model_rows}:
            continue
        payload["paired_vs_ungoverned"][model] = {
            policy: _paired(model_rows, "ungoverned", policy)
            for policy in policies
            if policy != "ungoverned"
        }
        matrix = []
        for policy in policies:
            by_task = {row["task_id"]: int(row["resolved"]) for row in model_rows if row["policy"] == policy}
            if len(by_task) < 2:
                continue
            matrix.append(by_task)
        common = sorted(set.intersection(*[set(item) for item in matrix])) if matrix else []
        if len(matrix) >= 3 and common:
            arrays = [[item[task] for task in common] for item in matrix]
            try:
                result = st.friedmanchisquare(*arrays)
                payload["cochran_q"][model] = {"statistic": float(result.statistic), "p": float(result.pvalue), "n_tasks": len(common), "k_policies": len(arrays)}
            except ValueError:
                pass

    write_json(config.RESULTS_DIR / "statistics.json", payload)
    print(json.dumps(payload["paired_vs_ungoverned"], indent=2))


if __name__ == "__main__":
    main()
