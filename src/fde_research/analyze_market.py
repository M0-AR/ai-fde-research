from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

import pandas as pd

from . import config
from .util import write_json


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


_NUMBER = r"(\d[\d,]*(?:\.\d+)?)(\s*[kK])?"
_RANGE = re.compile(
    rf"\$?\s*{_NUMBER}\s*(?:-|–|—|to)\s*\$?\s*{_NUMBER}", re.I
)
_SINGLE = re.compile(rf"\$\s*{_NUMBER}(?!\s*(?:-|–|—|to))", re.I)
_SALARY_CONTEXT = re.compile(
    r"salary|compensation|pay range|base pay|annual pay|hourly rate|\bote\b",
    re.I,
)


def _usd(number: str, suffix: str | None) -> float | None:
    value = float(number.replace(",", ""))
    if suffix:
        value *= 1000
    if 20000 <= value <= 1_000_000:
        return value
    return None


def extract_salary(text: str) -> tuple[float | None, float | None]:
    """Parse a salary range or single value.

    Handles ``$120k-$150k``, ``$120,000 - $150,000``, ``120k-150k`` and
    ``$145,000``. Hourly amounts (``$50-$75 /hour``) are rejected rather than
    silently multiplied into an annual figure.
    """
    if not text:
        return None, None
    range_match = _RANGE.search(text)
    if range_match:
        low = _usd(range_match.group(1), range_match.group(2))
        high = _usd(range_match.group(3), range_match.group(4))
        if low is not None and high is not None and low <= high:
            return low, high
    single = _SINGLE.search(text)
    if single:
        value = _usd(single.group(1), single.group(2))
        if value is not None:
            return value, value
    return None, None


def _salary_windows(text: str):
    for match in _SALARY_CONTEXT.finditer(text):
        yield text[max(0, match.start() - 120) : match.end() + 220]


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
    explicit = fde["title"].fillna("").str.contains(r"forward[\s-]*deploy", case=False, regex=True)
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
    for _, row in fde.iterrows():
        low, high = extract_salary(str(row.get("salary_text") or ""))
        if low is None:
            for window in _salary_windows(str(row.get("description") or "")):
                low, high = extract_salary(window)
                if low is not None:
                    break
        if low is not None:
            salary_low.append(low)
            salary_high.append(high)
    salary = {
        "n_with_salary": len(salary_low),
        "share_with_salary": round(len(salary_low) / len(fde), 4) if len(fde) else 0.0,
        "median_low_usd": float(pd.Series(salary_low).median()) if salary_low else None,
        "median_high_usd": float(pd.Series(salary_high).median()) if salary_high else None,
        "method": "salary_text, else keyword-adjacent window in description",
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
        "n_fde_like": int(len(fde)),
        "n_fde_explicit": int(explicit.sum()),
        "fde_like_share": round(len(fde) / len(frame), 4) if len(frame) else 0.0,
        "fde_explicit_share": round(int(explicit.sum()) / len(frame), 4) if len(frame) else 0.0,
        "explicit_share_of_fde_like": round(float(explicit.mean()), 4) if len(fde) else 0.0,
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
