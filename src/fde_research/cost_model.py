from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import requests

from . import config
from .schema import (
    effective_model_id,
    governance_compliant,
    human_review_required,
    task_resolved,
)
from .util import utc_now, write_json


def lambda_prices() -> dict[str, Any]:
    cfg = config.study()["cost"]
    response = requests.get(cfg["lambda_pricing_url"], timeout=90)
    response.raise_for_status()
    payload = response.json()
    wanted = {"Lambda-GB-Second": None, "Request": None}
    for product in payload.get("products", {}).values():
        usage = product.get("attributes", {}).get("usagetype", "")
        if usage not in wanted:
            continue
        sku = product.get("sku")
        for dimension in payload.get("terms", {}).get("OnDemand", {}).get(sku, {}).values():
            for price_dim in dimension.get("priceDimensions", {}).values():
                usd = float(price_dim["pricePerUnit"].get("USD", 0))
                if usd > 0:
                    wanted[usage] = {
                        "usd": usd,
                        "unit": price_dim.get("unit"),
                        "description": price_dim.get("description"),
                    }
    return {
        "source": cfg["lambda_pricing_url"],
        "retrieved_at": utc_now(),
        "gb_second": wanted["Lambda-GB-Second"],
        "request": wanted["Request"],
    }


def lambda_invocation_cost(
    gb_seconds_usd: float,
    request_usd: float,
    memory_mb: float = 512,
    duration_ms: float = 500,
) -> float:
    """Cost of one Lambda invocation from GB-second and request list prices."""
    gb_seconds = (memory_mb / 1024) * (duration_ms / 1000)
    return gb_seconds_usd * gb_seconds + request_usd


def _episodes() -> list[dict[str, Any]]:
    path = config.episodes_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_model(episodes: list[dict[str, Any]], prices: dict[str, Any]) -> dict[str, Any]:
    cfg = config.study()["cost"]
    input_price = float(cfg["model_input_usd_per_million"])
    output_price = float(cfg["model_output_usd_per_million"])
    review_minutes = float(cfg["human_review_minutes"])
    loaded_annual = float(cfg["human_loaded_annual_usd"])
    hours = float(cfg["working_hours_per_year"])
    minute_rate = loaded_annual / (hours * 60)

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, str] = {}
    for episode in episodes:
        model_id = effective_model_id(episode)
        labels.setdefault(model_id, str(episode.get("model") or model_id))
        groups[(model_id, episode["policy"])].append(episode)

    rows = []
    for (model_id, policy), items in sorted(groups.items()):
        prompt_tokens = sum(item["prompt_tokens"] for item in items)
        completion_tokens = sum(item["completion_tokens"] for item in items)
        model_cost = (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price
        reviews = sum(1 for item in items if human_review_required(item))
        human_cost = reviews * review_minutes * minute_rate
        resolved = sum(1 for item in items if task_resolved(item))
        total = model_cost + human_cost
        rows.append(
            {
                "model_id": model_id,
                "model": labels.get(model_id, model_id),
                "policy": policy,
                "n": len(items),
                "resolved": resolved,
                "resolve_rate": resolved / len(items) if items else 0.0,
                "governance_compliant": sum(1 for item in items if governance_compliant(item)),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "model_cost_usd": round(model_cost, 4),
                "human_reviews": reviews,
                "human_cost_usd": round(human_cost, 2),
                "total_cost_usd": round(total, 2),
                "cost_per_episode_usd": round(total / len(items), 4) if items else 0.0,
                "cost_per_resolved_usd": round(total / resolved, 2) if resolved else None,
                "human_minutes": round(reviews * review_minutes, 1),
            }
        )

    lambda_cost_per_request = None
    if prices.get("request") and prices.get("gb_second"):
        lambda_cost_per_request = lambda_invocation_cost(
            gb_seconds_usd=prices["gb_second"]["usd"],
            request_usd=prices["request"]["usd"],
        )
    return {
        "generated_at": utc_now(),
        "assumptions": {
            "model_input_usd_per_million": input_price,
            "model_output_usd_per_million": output_price,
            "human_review_minutes": review_minutes,
            "human_loaded_annual_usd": loaded_annual,
            "working_hours_per_year": hours,
            "human_minute_usd": round(minute_rate, 4),
            "lambda_price_source": prices.get("source"),
            "lambda_retrieved_at": prices.get("retrieved_at"),
            "lambda_gb_second_usd": (prices.get("gb_second") or {}).get("usd"),
            "lambda_request_usd": (prices.get("request") or {}).get("usd"),
            "lambda_cost_per_500ms_512mb_invocation_usd": round(lambda_cost_per_request, 10) if lambda_cost_per_request else None,
            "note": "Model prices are hosted-equivalent shadow prices; the local GGUF run has no per-token billing.",
        },
        "by_model_policy": rows,
    }


def main() -> None:
    config.ensure_dirs()
    prices = lambda_prices()
    payload = build_model(_episodes(), prices)
    write_json(config.RESULTS_DIR / "cost_model.json", payload)
    print(json.dumps(payload["assumptions"], indent=2))
    for row in payload["by_model_policy"]:
        print(row["model_id"], row["policy"], row["resolve_rate"], row["cost_per_resolved_usd"])


if __name__ == "__main__":
    main()
