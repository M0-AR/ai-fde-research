from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config

plt.rcParams.update({"figure.dpi": 160, "savefig.bbox": "tight", "font.size": 9})


def _load(name: str, sub: str = "results") -> dict[str, Any]:
    path = config.as_path(sub, name)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def market_figures() -> list[Path]:
    out = []
    summary = _load("market_analysis.json")
    skills_path = config.RESULTS_DIR / "market_skills.csv"
    if summary and skills_path.exists():
        fig, ax = plt.subplots(figsize=(5.2, 3.0))
        counts = {
            "FDE-titled": summary["n_fde"],
            "Adjacent": summary["n_adjacent"],
            "Other": summary["n_other"],
        }
        ax.bar(counts.keys(), counts.values(), color=["#1f5f8b", "#6aa3c8", "#c9d6df"])
        ax.set_ylabel("Postings")
        ax.set_title(f"Live ATS snapshot, n={summary['n_postings']:,}")
        for index, value in enumerate(counts.values()):
            ax.text(index, value, f"{value:,}", ha="center", va="bottom", fontsize=8)
        path = config.FIGURES_DIR / "fig_market_roles.png"
        fig.savefig(path)
        plt.close(fig)
        out.append(path)

        skills = pd.read_csv(skills_path).head(10).iloc[::-1]
        fig, ax = plt.subplots(figsize=(5.4, 3.2))
        y = np.arange(len(skills))
        ax.barh(y + 0.2, skills["fde_share"] * 100, height=0.38, label="FDE-titled", color="#1f5f8b")
        ax.barh(y - 0.2, skills["adjacent_share"] * 100, height=0.38, label="Adjacent", color="#c28b3a")
        ax.set_yticks(y, skills["label"])
        ax.set_xlabel("Share of postings mentioning skill (%)")
        ax.legend(frameon=False, fontsize=8)
        path = config.FIGURES_DIR / "fig_market_skills.png"
        fig.savefig(path)
        plt.close(fig)
        out.append(path)
    return out


def benchmark_figures() -> list[Path]:
    out = []
    stats = _load("statistics.json")
    if not stats.get("overall"):
        return out
    frame = pd.DataFrame(stats["overall"])
    policies = stats["policies"]
    models = stats["models"]
    fig, ax = plt.subplots(figsize=(5.6, 3.1))
    width = 0.8 / max(len(models), 1)
    for index, model in enumerate(models):
        subset = frame[frame["model"] == model].set_index("policy").reindex(policies)
        x = np.arange(len(policies)) + index * width
        values = subset["resolve_rate"].fillna(0).to_numpy() * 100
        lower = values - subset["resolve_ci95"].apply(lambda pair: pair[0] if isinstance(pair, list) else 0).fillna(0).to_numpy() * 100
        upper = subset["resolve_ci95"].apply(lambda pair: pair[1] if isinstance(pair, list) else 0).fillna(0).to_numpy() * 100 - values
        ax.bar(x, values, width=width, label=model, yerr=[np.maximum(lower, 0), np.maximum(upper, 0)], capsize=2)
    ax.set_xticks(np.arange(len(policies)) + width * (len(models) - 1) / 2, policies, rotation=15)
    ax.set_ylabel("Fully resolved tasks (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8)
    path = config.FIGURES_DIR / "fig_benchmark_resolve.png"
    fig.savefig(path)
    plt.close(fig)
    out.append(path)

    phase = pd.DataFrame(stats["phase"])
    if not phase.empty:
        for model in models:
            subset = phase[phase["model"] == model]
            if subset.empty:
                continue
            pivot = subset.pivot(index="phase", columns="policy", values="resolve_rate").reindex(columns=policies) * 100
            fig, ax = plt.subplots(figsize=(5.6, 2.8))
            image = ax.imshow(pivot.fillna(0).to_numpy(), cmap="Blues", vmin=0, vmax=100, aspect="auto")
            ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=15)
            ax.set_yticks(range(len(pivot.index)), pivot.index)
            for row in range(pivot.shape[0]):
                for col in range(pivot.shape[1]):
                    value = pivot.iloc[row, col]
                    ax.text(col, row, f"{value:.0f}", ha="center", va="center", fontsize=7, color="black" if value < 60 else "white")
            fig.colorbar(image, ax=ax, label="Resolved (%)")
            ax.set_title(model)
            path = config.FIGURES_DIR / f"fig_phase_heatmap_{model.replace(':', '_').replace('.', '_')}.png"
            fig.savefig(path)
            plt.close(fig)
            out.append(path)
    return out


def cost_figure() -> list[Path]:
    payload = _load("cost_model.json")
    rows = payload.get("by_model_policy") or []
    if not rows:
        return []
    per_resolved = any(row.get("cost_per_resolved_usd") for row in rows)
    if not per_resolved:
        for row in rows:
            row["cost_per_resolved_usd"] = row["cost_per_episode_usd"]
    frame = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    for model, subset in frame.groupby("model"):
        ax.scatter(subset["resolve_rate"] * 100, subset["cost_per_resolved_usd"], label=model, s=40)
        for _, row in subset.iterrows():
            ax.annotate(row["policy"], (row["resolve_rate"] * 100, row["cost_per_resolved_usd"]), fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("Fully resolved tasks (%)")
    ax.set_ylabel("Cost per resolved task (USD)" if per_resolved else "Cost per episode (USD)")
    ax.legend(frameon=False, fontsize=8)
    path = config.FIGURES_DIR / "fig_cost_effectiveness.png"
    fig.savefig(path)
    plt.close(fig)
    return [path]


def guardrail_figure() -> list[Path]:
    payload = _load("guardrail_eval.json")
    if not payload:
        return []
    classifier = payload["classifier"]
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    labels = ["rules", "classifier @0.5", "classifier @target"]
    metrics = [
        payload["rules"]["test"],
        classifier["test_at_0_5"],
        classifier["test_at_selected_threshold"],
    ]
    x = np.arange(len(labels))
    width = 0.26
    for offset, metric in [(-width, "precision"), (0, "recall"), (width, "f1")]:
        values = [item[metric] for item in metrics]
        ax.bar(x + offset, values, width=width, label=metric)
    ax.set_xticks(x, labels, rotation=10)
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=7, ncol=3)
    path = config.FIGURES_DIR / "fig_guardrail.png"
    fig.savefig(path)
    plt.close(fig)
    return [path]


def deployment_figure() -> list[Path]:
    payload = _load("deployment_eval.json")
    rows = payload.get("canonical") or []
    if not rows:
        return []
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    labels = [row["task_id"] for row in rows]
    values = [row.get("startup_seconds", 0) for row in rows]
    colors = ["#2e7d4f" if row.get("healthy") else "#b23a3a" for row in rows]
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("Startup to healthy (s)")
    for index, row in enumerate(rows):
        ax.text(index, values[index], "healthy" if row.get("healthy") else "failed", ha="center", va="bottom", fontsize=7)
    path = config.FIGURES_DIR / "fig_deployment.png"
    fig.savefig(path)
    plt.close(fig)
    return [path]


def main() -> None:
    config.ensure_dirs()
    paths = market_figures() + benchmark_figures() + cost_figure() + guardrail_figure() + deployment_figure()
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
