from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any

import pandas as pd

from . import config
from .util import http_get, utc_now, write_json

OPENALEX = "https://api.openalex.org/works"
ARXIV = "https://export.arxiv.org/api/query"
HN = "https://hn.algolia.com/api/v1/search"
GITHUB = "https://api.github.com/search/repositories"

QUERIES = {
    "forward_deployed": {
        "openalex": 'title_and_abstract.search:"forward deployed"',
        "arxiv": 'all:"forward deployed"',
        "hn": "forward deployed engineer",
        "github": '"forward deployed engineer"',
    },
    "agent_evaluation": {
        "openalex": 'title_and_abstract.search:"agentic" AND title_and_abstract.search:"evaluation"',
        "arxiv": 'all:"agentic" AND all:"evaluation"',
        "hn": "agent evaluation",
        "github": '"agent evaluation"',
    },
    "prompt_injection": {
        "openalex": 'title_and_abstract.search:"prompt injection"',
        "arxiv": 'all:"prompt injection"',
        "hn": "prompt injection",
        "github": '"prompt injection" benchmark',
    },
}

YEARS = list(range(2019, 2027))


def openalex_counts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, works = [], []
    for name, query in QUERIES.items():
        response = http_get(
            OPENALEX,
            params={"filter": query["openalex"], "group_by": "publication_year", "per-page": 200},
            timeout=45,
        ).json()
        groups = {int(g["key"]): g["count"] for g in response.get("group_by", []) if g["key"].isdigit()}
        for year in YEARS:
            rows.append({"source": "openalex", "query": name, "year": year, "count": groups.get(year, 0)})
        top = http_get(
            OPENALEX,
            params={"filter": query["openalex"], "per-page": 25, "sort": "cited_by_count:desc"},
            timeout=45,
        ).json()
        for work in top.get("results", []):
            works.append(
                {
                    "source": "openalex",
                    "query": name,
                    "id": work.get("id"),
                    "title": work.get("title"),
                    "year": work.get("publication_year"),
                    "doi": work.get("doi"),
                    "cited_by_count": work.get("cited_by_count"),
                    "url": (work.get("primary_location") or {}).get("landing_page_url"),
                }
            )
        time.sleep(0.5)
    return rows, works


def arxiv_counts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, works = [], []
    ns = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
    for name, query in QUERIES.items():
        response = http_get(
            ARXIV,
            params={"search_query": query["arxiv"], "start": 0, "max_results": 2000, "sortBy": "submittedDate"},
            timeout=60,
        )
        root = ET.fromstring(response.content)
        total = int(root.findtext("o:totalResults", default="0", namespaces=ns))
        per_year: dict[int, int] = {}
        for entry in root.findall("a:entry", ns):
            published = entry.findtext("a:published", default="", namespaces=ns)
            year = int(published[:4]) if published[:4].isdigit() else 0
            per_year[year] = per_year.get(year, 0) + 1
            if len(works) < 30:
                works.append(
                    {
                        "source": "arxiv",
                        "query": name,
                        "id": entry.findtext("a:id", default="", namespaces=ns),
                        "title": " ".join(entry.findtext("a:title", default="", namespaces=ns).split()),
                        "year": year,
                        "url": entry.findtext("a:id", default="", namespaces=ns),
                    }
                )
        for year in YEARS:
            rows.append(
                {
                    "source": "arxiv",
                    "query": name,
                    "year": year,
                    "count": per_year.get(year, 0),
                    "total_reported": total,
                    "truncated": total > 2000,
                }
            )
        time.sleep(3.1)
    return rows, works


def hn_counts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, works = [], []
    for name, query in QUERIES.items():
        response = http_get(
            HN,
            params={"query": query["hn"], "tags": "story", "hitsPerPage": 1000},
            timeout=30,
        ).json()
        per_year: dict[int, int] = {}
        for hit in response.get("hits", []):
            year = int(str(hit.get("created_at", ""))[:4] or 0)
            per_year[year] = per_year.get(year, 0) + 1
            if len(works) < 20:
                works.append(
                    {
                        "source": "hackernews",
                        "query": name,
                        "id": hit.get("objectID"),
                        "title": hit.get("title"),
                        "year": year,
                        "points": hit.get("points"),
                        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    }
                )
        for year in YEARS:
            rows.append({"source": "hackernews", "query": name, "year": year, "count": per_year.get(year, 0)})
        time.sleep(0.5)
    return rows, works


def github_counts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, works = [], []
    for name, query in QUERIES.items():
        response = http_get(
            GITHUB,
            params={"q": query["github"], "sort": "stars", "order": "desc", "per_page": 20},
            timeout=30,
        ).json()
        rows.append({"source": "github", "query": name, "year": 2026, "count": response.get("total_count", 0)})
        for repo in response.get("items", [])[:10]:
            works.append(
                {
                    "source": "github",
                    "query": name,
                    "id": repo.get("full_name"),
                    "title": repo.get("description") or repo.get("full_name"),
                    "year": int((repo.get("created_at") or "2026")[:4]),
                    "stars": repo.get("stargazers_count"),
                    "url": repo.get("html_url"),
                }
            )
        time.sleep(2.0)
    return rows, works


def main() -> None:
    config.ensure_dirs()
    all_rows, all_works = [], []
    errors = []
    for label, fn in [
        ("openalex", openalex_counts),
        ("arxiv", arxiv_counts),
        ("hackernews", hn_counts),
        ("github", github_counts),
    ]:
        try:
            rows, works = fn()
            all_rows.extend(rows)
            all_works.extend(works)
            print(label, len(rows), len(works))
        except Exception as exc:  # noqa: BLE001 - source isolation
            errors.append({"source": label, "error": str(exc)})
            print(label, "ERROR", exc)

    frame = pd.DataFrame(all_rows)
    frame.to_csv(config.PROCESSED_DIR / "scholarly_counts.csv", index=False)
    pd.DataFrame(all_works).to_csv(config.PROCESSED_DIR / "scholarly_works.csv", index=False)
    write_json(
        config.RESULTS_DIR / "scholarly_collection.json",
        {"retrieved_at": utc_now(), "rows": all_rows, "errors": errors},
    )
    print(frame.groupby(["source", "query"])["count"].sum().to_string())


if __name__ == "__main__":
    main()
