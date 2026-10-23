from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from . import config
from .util import utc_now, write_json

CANONICAL = {
    "P01": """services:
  web:
    image: nginx:1.27-alpine
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /var/cache/nginx
      - /var/run
    ports:
      - "18081:80"
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/ || exit 1"]
      interval: 5s
      timeout: 3s
      retries: 10
""",
    "P02": """services:
  api:
    image: nginx:1.27-alpine
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /var/cache/nginx
      - /var/run
    ports:
      - "18082:80"
    depends_on:
      cache:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/ || exit 1"]
      interval: 5s
      timeout: 3s
      retries: 10
  cache:
    image: redis:7-alpine
    restart: unless-stopped
    read_only: true
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
""",
    "P03": """services:
  worker:
    image: alpine:3.20
    restart: unless-stopped
    read_only: true
    command: ["sh", "-c", "while true; do sleep 30; done"]
    depends_on:
      queue:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "true"]
      interval: 5s
      timeout: 3s
      retries: 10
  queue:
    image: redis:7-alpine
    restart: unless-stopped
    read_only: true
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
""",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(config.ROOT))
    except ValueError:
        return path.name


def _public(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(str(config.ROOT) + "/", "./").replace(str(config.ROOT), ".")
    if isinstance(value, list):
        return [_public(item) for item in value]
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items()}
    return value


def _run(args: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _project(task_id: str) -> str:
    return f"{config.study()['deployment']['project_prefix']}_{task_id.lower()}_{uuid.uuid4().hex[:6]}"


def compose_up(task_id: str, yaml_text: str, *, timeout: int | None = None) -> dict[str, Any]:
    timeout = timeout or int(config.study()["deployment"]["timeout_seconds"])
    config.ensure_dirs()
    workdir = Path(tempfile.mkdtemp(prefix=f"fde_{task_id.lower()}_", dir=config.RESULTS_DIR / "deployments" if (config.RESULTS_DIR / "deployments").exists() else None))
    project = _project(task_id)
    (workdir / "docker-compose.yml").write_text(yaml_text)
    third = int(uuid.uuid4().hex[:2], 16)
    (workdir / "docker-compose.override.yml").write_text(
        "networks:\n  default:\n    ipam:\n      config:\n        - subnet: 10.20%d.%d.0/24\n" % (third % 8, third)
    )
    result: dict[str, Any] = {"task_id": task_id, "workdir": _display_path(workdir), "project": project, "healthy": False, "http_status": None}
    start = time.perf_counter()
    try:
        parsed = yaml.safe_load(yaml_text)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("services"), dict):
            raise ValueError("compose yaml has no services mapping")
        up = _run(
            ["docker", "compose", "-p", project, "up", "-d", "--wait", "--wait-timeout", str(timeout), "--pull", "never"],
            workdir,
            timeout + 30,
        )
        result["up_returncode"] = up.returncode
        result["up_stdout"] = up.stdout[-4000:]
        result["up_stderr"] = up.stderr[-4000:]
        result["startup_seconds"] = time.perf_counter() - start
        if up.returncode == 0:
            result["healthy"] = True
            ps = _run(["docker", "compose", "-p", project, "ps", "--format", "json"], workdir, 30)
            result["containers"] = ps.stdout[-4000:]
            port = re_port(yaml_text)
            if port:
                import urllib.request

                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
                        result["http_status"] = response.status
                except Exception as exc:  # noqa: BLE001
                    result["http_error"] = str(exc)
            restart = _run(["docker", "compose", "-p", project, "restart"], workdir, 60)
            result["restart_returncode"] = restart.returncode
            time.sleep(1)
            ps2 = _run(["docker", "compose", "-p", project, "ps", "--format", "json"], workdir, 30)
            result["containers_after_restart"] = ps2.stdout[-4000:]
    except subprocess.TimeoutExpired as exc:
        result["error"] = f"timeout after {timeout}s: {exc}"
        result["startup_seconds"] = time.perf_counter() - start
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        result["startup_seconds"] = time.perf_counter() - start
    finally:
        down = _run(["docker", "compose", "-p", project, "down", "-v", "--remove-orphans"], workdir, 90)
        result["down_returncode"] = down.returncode
        shutil.rmtree(workdir, ignore_errors=True)
    return _public(result)


def re_port(yaml_text: str) -> str | None:
    import re

    match = re.search(r'["\'](\d{4,5}):\d+["\']', yaml_text)
    return match.group(1) if match else None


def canonical_eval() -> list[dict[str, Any]]:
    return [compose_up(task_id, yaml_text) for task_id, yaml_text in CANONICAL.items()]


def benchmark_eval() -> list[dict[str, Any]]:
    path = config.episodes_path()
    if not path.exists():
        return []
    episodes = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    selected = []
    seen = set()
    for episode in episodes:
        if episode["task_id"] not in CANONICAL:
            continue
        key = (episode["task_id"], episode["policy"], episode.get("model_id", episode["model"]))
        if key in seen:
            continue
        seen.add(key)
        artifact = episode.get("artifact") or {}
        yaml_text = artifact.get("compose_yaml") if isinstance(artifact, dict) else None
        if not yaml_text:
            selected.append(
                {
                    "task_id": episode["task_id"],
                    "policy": episode["policy"],
                    "model": episode["model"],
                    "model_id": episode.get("model_id", episode["model"]),
                    "healthy": False,
                    "error": "no compose_yaml in artifact",
                }
            )
            continue
        result = compose_up(episode["task_id"], yaml_text)
        result.update({k: episode[k] for k in ("task_id", "policy", "model")})
        result["model_id"] = episode.get("model_id", episode["model"])
        selected.append(result)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["canonical", "benchmark", "both"], default="both")
    args = parser.parse_args()
    config.ensure_dirs()
    (config.RESULTS_DIR / "deployments").mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "generated_at": utc_now(),
        "scope": "canonical_smoke_test" if args.source == "canonical" else "canonical_plus_generated",
        "limitations": [
            "P01 is an HTTP liveness check.",
            "P02 is an HTTP service plus cache dependency; it does not exercise application logic.",
            "P03 is a worker/queue liveness check; the worker does not process jobs.",
            "Generated benchmark artifacts are only executed with --source benchmark or both.",
        ],
    }
    if args.source in {"canonical", "both"}:
        payload["canonical"] = canonical_eval()
    if args.source in {"benchmark", "both"}:
        payload["benchmark_artifacts"] = benchmark_eval()
    write_json(config.RESULTS_DIR / "deployment_eval.json", payload)
    print(json.dumps(payload, indent=2)[:5000])


if __name__ == "__main__":
    main()
