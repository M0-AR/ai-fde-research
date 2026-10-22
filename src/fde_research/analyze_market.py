from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .util import write_json


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def extract_salary(text: str) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    normalized = text.replace(",", "")
    range_match = re.search(r"\$\s*(\d{2,3}(?:\.\d+)?)\s*[kK]?\s*(?:-|–|to)\s*\$?\s*(\d{2,3}(?:\.\d+)?)\s*[kK]?", normalized)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        if low < 1000:
            low *= 1000
        if high < 1000:
            high *= 1000
        if 20000 <= low <= 1000000 and 20000 <= high <= 1000000 and low <= high:
            return low, high
    single = re.search(r"\$\s*(\d{2,3}(?:\.\d+)?)\s*[kK]\b", normalized)
    if single:
        value = float(single.group(1)) * 1000
        if 20000 <= value <= 1000000:
            return value, value
    return None, None


def seniority(title: str) -> str:
    rules = config.taxonomy()["seniority"]
    for level in ("junior", "mid", "senior"):
        if _matches(rules[level], title):
            return level
    return "unspecified"


def analyze(frame: pd.DataFrame) -> dict[str, Any]:
    taxonomy = config.taxonomy()
    fde = frame[frame["role_class"] == "fde"].copy()
    adjacent = frame[frame["role_class"] == "adjacent"].copy()
    fde["description"] = fde["description"].fillna("")
    adjacent["description"] = adjacent["description"].fillna("")
    combined = fde["title"].fillna("") + " " + fde["description"]

    skill_rows = []
    for key, spec in taxonomy["skills"].items():
        in_fde = combined.apply(lambda text, p=spec["patterns"]: _matches(p, text)).mean()
        adj_text = adjacent["title"].fillna("") + " " + adjacent["description"]
        in_adj = adj_text.apply(lambda text, p=spec["patterns"]: _matches(p, text)).mean() if len(adjacent) else 0.0
        skill_rows.append(
            {
                "skill": key,
                "label": spec["label"],
                "fde_share": round(float(in_fde), 4),
                "adjacent_share": round(float(in_adj), 4),
                "lift_pp": round(float(in_fde - in_adj) * 100, 2),
            }
        )
    skills = pd.DataFrame(skill_rows).sort_values("fde_share", ascending=False)

    lifecycle_rows = []
    for key, spec in taxonomy["lifecycle"].items():
        share = combined.apply(lambda text, p=spec["patterns"]: _matches(p, text)).mean()
        lifecycle_rows.append({"phase": key, "label": spec["label"], "share": round(float(share), 4)})
    lifecycle = pd.DataFrame(lifecycle_rows).sort_values("share", ascending=False)

    salary_low = []
    salary_high = []
    for text in (fde["description"].fillna("") + " " + fde["salary_text"].fillna("")):
        low, high = extract_salary(text)
        if low is not None:
            salary_low.append(low)
            salary_high.append(high)
    salary = {
        "n_with_salary": len(salary_low),
        "share_with_salary": round(len(salary_low) / len(fde), 4) if len(fde) else 0.0,
        "median_low_usd": float(pd.Series(salary_low).median()) if salary_low else None,
        "median_high_usd": float(pd.Series(salary_high).median()) if salary_high else None,
    }

    seniority_counts = Counter(seniority(title) for title in fde["title"])
    locations = Counter(fde["location"].fillna("").str.strip()).most_common(15)
    companies = Counter(fde["company"]).most_common(15)

    frame_out = frame.copy()
    frame_out["seniority"] = frame_out["title"].fillna("").apply(seniority)
    frame_out.to_csv(config.PROCESSED_DIR / "jobs_analyzed.csv", index=False)
    skills.to_csv(config.RESULTS_DIR / "market_skills.csv", index=False)
    lifecycle.to_csv(config.RESULTS_DIR / "market_lifecycle.csv", index=False)

    return {
        "n_postings": int(len(frame)),
        "n_fde": int(len(fde)),
        "n_adjacent": int(len(adjacent)),
        "n_other": int((frame["role_class"] == "other").sum()),
        "fde_share": round(len(fde) / len(frame), 4) if len(frame) else 0.0,
        "fde_remote_share": round(float(fde["remote"].mean()), 4) if len(fde) else 0.0,
        "adjacent_remote_share": round(float(adjacent["remote"].mean()), 4) if len(adjacent) else 0.0,
        "median_description_chars_fde": float(fde["text_length"].median()) if len(fde) else 0.0,
        "salary": salary,
        "seniority": dict(seniority_counts),
        "top_locations": [{"location": loc or "(unspecified)", "n": n} for loc, n in locations],
        "top_companies": [{"company": company, "n": n} for company, n in companies],
        "skills": skills.to_dict(orient="records"),
        "lifecycle": lifecycle.to_dict(orient="records"),
        "sources": frame["source"].value_counts().to_dict(),
    }


def main() -> None:
    config.ensure_dirs()
    path = config.PROCESSED_DIR / "jobs.csv"
    if not path.exists():
        raise SystemExit("run collect_jobs first")
    frame = pd.read_csv(path)
    summary = analyze(frame)
    write_json(config.RESULTS_DIR / "market_analysis.json", summary)
    write_json(config.RESULTS_DIR / "market_summary.json", {k: v for k, v in summary.items() if k not in {"skills", "lifecycle"}})
    print(json.dumps({k: v for k, v in summary.items() if k not in {"skills", "lifecycle", "top_locations", "top_companies"}}, indent=2))


if __name__ == "__main__":
    main()
