"""Freeze a benchmark run into an immutable, schema-normalized archive.

Usage:
    python -m fde_research.freeze_run --label final
    python -m fde_research.freeze_run --input results/benchmark_episodes.jsonl --label 2026-10-22

The live ``results/benchmark_episodes.jsonl`` is never modified. The frozen
file and a manifest are written under ``results/frozen/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .benchmark import summarize
from .schema import normalize_rows
from .util import write_json


def _read(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(rows),
        "by_model": dict(Counter(str(row["model_id"]) for row in rows)),
        "by_policy": dict(Counter(str(row["policy"]) for row in rows)),
        "by_model_policy": {
            f"{model}|{policy}": n
            for (model, policy), n in sorted(
                Counter((str(row["model_id"]), str(row["policy"])) for row in rows).items()
            )
        },
        "task_resolved": sum(1 for row in rows if row["task_resolved"]),
        "governance_compliant": sum(1 for row in rows if row["governance_compliant"]),
        "safety_violations": sum(1 for row in rows if row["safety_violation"]),
        "errors": sum(1 for row in rows if row.get("error")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    source = args.input or config.episodes_path()
    if not source.exists():
        raise SystemExit(f"no episode file: {source}")
    out_dir = args.out or (config.RESULTS_DIR / "frozen")
    out_dir.mkdir(parents=True, exist_ok=True)
    label = args.label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raw = _read(source)
    rows = normalize_rows(raw)
    dest = out_dir / f"benchmark_episodes_{label}.jsonl"
    dest.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    manifest = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "frozen_file": str(dest),
        "sha256": digest,
        "schema_version": 2,
        **_counts(rows),
    }
    write_json(out_dir / f"manifest_{label}.json", manifest)
    summary = summarize(rows)
    write_json(out_dir / f"benchmark_summary_{label}.json", summary)
    write_json(config.RESULTS_DIR / "benchmark_summary.json", summary)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
