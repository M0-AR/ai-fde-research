from __future__ import annotations

import argparse
import re
import time
from datetime import date
from typing import Any

import pandas as pd

from . import config
from .util import clean_text, http_get, normalize_space, sha256_text, slugify, utc_now, write_json


def _role_patterns() -> list[re.Pattern[str]]:
    patterns = config.taxonomy()["roles"]["fde"]["patterns"]
    return [re.compile(pattern, re.I) for pattern in patterns]


def classify_role(title: str) -> str:
    for pattern in _role_patterns():
        if pattern.search(title):
            return "fde"
    adjacent = config.taxonomy()["roles"]["adjacent"]["patterns"]
    if any(re.search(pattern, title, re.I) for pattern in adjacent):
        return "adjacent"
    return "other"


def _record(
    *,
    source: str,
    company: str,
    title: str,
    location: str,
    description: str,
    url: str,
    posted_at: str,
    department: str = "",
    remote: bool | None = None,
    salary_text: str = "",
) -> dict[str, Any]:
    desc = clean_text(description)[: config.study()["market"]["max_description_chars"]]
    loc = normalize_space(location)
    remote_flag = remote
    if remote_flag is None:
        remote_flag = bool(re.search(r"\bremote\b|anywhere|distributed", loc, re.I))
    rec = {
        "source": source,
        "company": company,
        "title": normalize_space(title),
        "location": loc,
        "remote": remote_flag,
        "department": normalize_space(department),
        "posted_at": posted_at or "",
        "url": url,
        "description": desc,
        "salary_text": normalize_space(salary_text),
    }
    rec["id"] = sha256_text("|".join([source, company, rec["title"].lower(), loc.lower(), url]))[:20]
    rec["role_class"] = classify_role(rec["title"])
    rec["text_length"] = len(desc)
    return rec


def collect_greenhouse(board: str) -> list[dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    payload = http_get(url, timeout=60).json()
    out = []
    for job in payload.get("jobs", []):
        departments = ", ".join(d.get("name", "") for d in job.get("departments", []))
        out.append(
            _record(
                source="greenhouse",
                company=board,
                title=job.get("title", ""),
                location=(job.get("location") or {}).get("name", ""),
                description=job.get("content", ""),
                url=job.get("absolute_url", ""),
                posted_at=job.get("updated_at", ""),
                department=departments,
            )
        )
    return out


def collect_lever(board: str) -> list[dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{board}?mode=json"
    payload = http_get(url, timeout=60).json()
    out = []
    for job in payload:
        categories = job.get("categories") or {}
        out.append(
            _record(
                source="lever",
                company=board,
                title=job.get("text", ""),
                location=categories.get("location", ""),
                description=job.get("descriptionPlain") or job.get("description", ""),
                url=job.get("hostedUrl", ""),
                posted_at=str(job.get("createdAt", "")),
                department=categories.get("team", "") or categories.get("department", ""),
                remote=(job.get("workplaceType") == "remote"),
                salary_text=str(job.get("salaryRange", "") or ""),
            )
        )
    return out


def collect_ashby(board: str) -> list[dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
    payload = http_get(url, timeout=60).json()
    out = []
    for job in payload.get("jobs", []):
        comp = job.get("compensation") or {}
        salary = comp.get("compensationTierSummary", "") if isinstance(comp, dict) else ""
        out.append(
            _record(
                source="ashby",
                company=board,
                title=job.get("title", ""),
                location=job.get("location", ""),
                description=job.get("descriptionHtml", "") or job.get("descriptionPlain", ""),
                url=job.get("jobUrl", ""),
                posted_at=job.get("publishedAt", ""),
                department=job.get("department", "") or job.get("team", ""),
                remote=job.get("isRemote"),
                salary_text=salary,
            )
        )
    return out


def collect_remotive(query: str) -> list[dict[str, Any]]:
    url = "https://remotive.com/api/remote-jobs"
    payload = http_get(url, timeout=30, params={"search": query, "limit": 100}).json()
    out = []
    for job in payload.get("jobs", []):
        out.append(
            _record(
                source="remotive",
                company=job.get("company_name", ""),
                title=job.get("title", ""),
                location=job.get("candidate_required_location", ""),
                description=job.get("description", ""),
                url=job.get("url", ""),
                posted_at=job.get("publication_date", ""),
                department=job.get("category", ""),
                remote=True,
                salary_text=job.get("salary", ""),
            )
        )
    return out


def collect_arbeitnow() -> list[dict[str, Any]]:
    url = "https://www.arbeitnow.com/api/job-board-api"
    payload = http_get(url, timeout=30).json()
    out = []
    for job in payload.get("data", []):
        out.append(
            _record(
                source="arbeitnow",
                company=job.get("company_name", ""),
                title=job.get("title", ""),
                location=job.get("location", ""),
                description=job.get("description", ""),
                url=job.get("url", ""),
                posted_at=str(job.get("created_at", "")),
                department=", ".join(job.get("tags", []) or []),
                remote=job.get("remote"),
                salary_text=job.get("salary", "") or "",
            )
        )
    return out


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for record in records:
        key = record["id"]
        near = slugify(record["company"] + " " + record["title"] + " " + record["location"])
        if key in seen or near in seen:
            continue
        seen.add(key)
        seen.add(near)
        out.append(record)
    return out


def collect_all() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = config.study()["market"]
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for board in cfg["greenhouse_boards"]:
        try:
            batch = collect_greenhouse(board)
            records.extend(batch)
            print(f"greenhouse/{board}: {len(batch)}")
        except Exception as exc:  # noqa: BLE001 - source isolation
            errors.append({"source": "greenhouse", "board": board, "error": str(exc)})
        time.sleep(0.4)

    for board in cfg["lever_boards"]:
        try:
            batch = collect_lever(board)
            records.extend(batch)
            print(f"lever/{board}: {len(batch)}")
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "lever", "board": board, "error": str(exc)})
        time.sleep(0.4)

    for board in cfg["ashby_boards"]:
        try:
            batch = collect_ashby(board)
            records.extend(batch)
            print(f"ashby/{board}: {len(batch)}")
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "ashby", "board": board, "error": str(exc)})
        time.sleep(0.4)

    for query in cfg["remotive_queries"]:
        try:
            batch = collect_remotive(query)
            records.extend(batch)
            print(f"remotive/{query}: {len(batch)}")
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "remotive", "query": query, "error": str(exc)})
        time.sleep(0.4)

    if cfg.get("include_arbeitnow"):
        try:
            batch = collect_arbeitnow()
            records.extend(batch)
            print(f"arbeitnow: {len(batch)}")
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "arbeitnow", "error": str(exc)})

    records = deduplicate(records)
    return records, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="reuse the latest raw snapshot")
    args = parser.parse_args()
    config.ensure_dirs()

    if args.offline:
        snapshots = sorted(config.RAW_DIR.glob("jobs_*.json"))
        if not snapshots:
            raise SystemExit("no raw job snapshot available")
        payload = pd.read_json(snapshots[-1], typ="series").to_dict()
        records = payload["records"]
        errors = payload.get("errors", [])
    else:
        records, errors = collect_all()
        payload = {
            "retrieved_at": utc_now(),
            "date": date.today().isoformat(),
            "records": records,
            "errors": errors,
        }
        write_json(config.RAW_DIR / f"jobs_{date.today().isoformat()}.json", payload)

    frame = pd.DataFrame(records)
    frame = frame.sort_values(["role_class", "company", "title"]).reset_index(drop=True)
    frame.to_csv(config.PROCESSED_DIR / "jobs.csv", index=False)
    summary = {
        "retrieved_at": payload.get("retrieved_at", utc_now()),
        "n_raw": len(records),
        "n_fde": int((frame["role_class"] == "fde").sum()),
        "n_adjacent": int((frame["role_class"] == "adjacent").sum()),
        "n_other": int((frame["role_class"] == "other").sum()),
        "sources": frame["source"].value_counts().to_dict(),
        "errors": errors,
    }
    write_json(config.RESULTS_DIR / "market_collection.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
