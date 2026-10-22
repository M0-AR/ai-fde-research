from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from .util import parse_json_loose


@dataclass
class LLMResponse:
    text: str
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    raw: dict[str, Any]

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: int = 180,
        max_tokens: int = 900,
        temperature: float = 0.0,
        seed: int = 20261022,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int | None = None) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "seed": self.seed,
            "stream": False,
        }
        start = time.perf_counter()
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.timeout,
        )
        elapsed = time.perf_counter() - start
        if response.status_code >= 400:
            raise RuntimeError(f"LLM HTTP {response.status_code}: {response.text[:400]}")
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            latency_seconds=elapsed,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            raw=data,
        )

    def ask_json(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        retries: int = 2,
    ) -> tuple[Any, LLMResponse, int]:
        """Return (parsed, last response, attempts). Retries only on unparseable output."""
        attempt = 0
        last: LLMResponse | None = None
        current = list(messages)
        while attempt <= retries:
            attempt += 1
            last = self.chat(current, max_tokens=max_tokens)
            try:
                return parse_json_loose(last.text), last, attempt
            except ValueError as exc:
                if attempt > retries:
                    raise
                current = list(messages) + [
                    {"role": "assistant", "content": last.text[:2000]},
                    {
                        "role": "user",
                        "content": f"That response was not valid JSON ({exc}). Return only one JSON object, with no markdown fences or prose.",
                    },
                ]
        raise RuntimeError("unreachable")


def client_from_config(model_cfg: dict[str, Any]) -> LLMClient:
    from . import config

    bench = config.study()["benchmark"]
    return LLMClient(
        base_url=model_cfg["base_url"],
        model=model_cfg["model"],
        timeout=int(bench["request_timeout_seconds"]),
        max_tokens=int(bench["max_tokens"]),
        temperature=float(bench["temperature"]),
        seed=int(config.study()["study"]["seed"]),
    )
