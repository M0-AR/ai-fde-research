"""Run the full study pipeline in dependency order.

The benchmark is opt-in because a full run takes hours on CPU-only local
models. All other stages are fast and deterministic once their inputs exist.

Examples:
    python -m fde_research.run_all --with-benchmark
    python -m fde_research.run_all --skip-market --skip-deployment
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass

from .config import RESULTS_DIR, ROOT
from .util import utc_now


@dataclass(frozen=True)
class Stage:
    name: str
    module: str
    args: tuple[str, ...] = ()
    optional: bool = False


STAGES: tuple[Stage, ...] = (
    Stage("tasks", "fde_research.tasks"),
    Stage("market", "fde_research.collect_jobs"),
    Stage("market-analysis", "fde_research.analyze_market"),
    Stage("guardrail", "fde_research.guardrail_eval"),
    Stage("benchmark", "fde_research.benchmark", ("--models", "qwen2.5-1.5b")),
    Stage("deployment", "fde_research.deployment_eval", ("--source", "both")),
    Stage("cost", "fde_research.cost_model"),
    Stage("statistics", "fde_research.stats"),
    Stage("figures", "fde_research.figures"),
    Stage("report", "fde_research.report"),
    Stage("verify", "fde_research.verify_results"),
)


def run_stage(stage: Stage, extra: tuple[str, ...] = ()) -> None:
    command = [sys.executable, "-m", stage.module, *stage.args, *extra]
    print(f"\n=== {stage.name} :: {' '.join(command)}", flush=True)
    started = time.time()
    completed = subprocess.run(command, cwd=ROOT)
    elapsed = time.time() - started
    if completed.returncode != 0:
        print(f"--- {stage.name} failed after {elapsed:.1f}s", flush=True)
        if not stage.optional:
            raise SystemExit(completed.returncode)
    else:
        print(f"--- {stage.name} ok in {elapsed:.1f}s", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-benchmark", action="store_true", help="include the long benchmark stage")
    parser.add_argument("--models", nargs="*", default=None, help="model ids for the benchmark stage")
    parser.add_argument("--skip", nargs="*", default=[], help="stage names to skip")
    parser.add_argument("--only", nargs="*", default=None, help="run only these stage names")
    parser.add_argument("--no-resume", action="store_true", help="restart the benchmark from scratch")
    args = parser.parse_args()

    selected: list[Stage] = []
    for stage in STAGES:
        if args.only and stage.name not in args.only:
            continue
        if stage.name in args.skip:
            continue
        if stage.name == "benchmark" and not args.with_benchmark and not args.only:
            print("skipping benchmark (use --with-benchmark)")
            continue
        selected.append(stage)

    print(f"pipeline start {utc_now()} :: {len(selected)} stages")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for stage in selected:
        extra: tuple[str, ...] = ()
        if stage.name == "benchmark":
            if args.models:
                extra += ("--models", *args.models)
            if args.no_resume:
                extra += ("--no-resume",)
        run_stage(stage, extra)
    print(f"\npipeline complete {utc_now()}")


if __name__ == "__main__":
    main()
