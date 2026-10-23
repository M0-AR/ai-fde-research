from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
BENCHMARK_DIR = DATA_DIR / "benchmark"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
PAPER_DIR = ROOT / "paper"


def load_yaml(name: str) -> dict[str, Any]:
    with (CONFIG_DIR / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def study() -> dict[str, Any]:
    return load_yaml("study.yaml")


def taxonomy() -> dict[str, Any]:
    return load_yaml("taxonomy.yaml")


def public_benchmarks() -> list[dict[str, Any]]:
    return load_yaml("public_benchmarks.yaml")


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def episodes_path() -> Path:
    """Path to the episode JSONL used by analysis and verification.

    ``FDE_EPISODES`` lets the frozen archive be analyzed without overwriting
    the live ``results/benchmark_episodes.jsonl``.
    """
    override = os.environ.get("FDE_EPISODES")
    return Path(override) if override else RESULTS_DIR / "benchmark_episodes.jsonl"


def ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, BENCHMARK_DIR, RESULTS_DIR, FIGURES_DIR, PAPER_DIR / "generated"):
        path.mkdir(parents=True, exist_ok=True)


def as_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)
