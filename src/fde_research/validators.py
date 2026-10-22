from __future__ import annotations

import json
import re
from typing import Any

import yaml

from .util import safe_float


def _get_path(obj: Any, path: str) -> Any:
    if not path:
        return obj
    current = obj
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else None
        else:
            return None
    return current


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " | ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " | ".join(f"{key}: {_text(val)}" for key, val in value.items())
    return "" if value is None else str(value)


def _words(value: Any) -> int:
    return len(re.findall(r"\b[\w'-]+\b", _text(value)))


def _term_present(haystack: Any, term: str) -> bool:
    return term.lower() in _text(haystack).lower()


def run_check(check: dict[str, Any], artifact: Any) -> dict[str, Any]:
    kind = check["type"]
    path = check.get("path", "")
    value = _get_path(artifact, path)
    passed = False
    detail = ""

    if kind == "equals":
        expected = check["value"]
        if isinstance(expected, bool):
            passed = bool(value) is expected
        elif isinstance(expected, (int, float)):
            passed = safe_float(value) == float(expected)
        else:
            passed = _text(value).strip().lower() == str(expected).strip().lower()
        detail = f"expected={expected!r} actual={value!r}"

    elif kind == "numeric_equals":
        actual = safe_float(value)
        expected = float(check["value"])
        passed = actual is not None and abs(actual - expected) < 1e-6
        detail = f"expected={expected} actual={actual}"

    elif kind == "numeric_lte":
        actual = safe_float(value)
        passed = actual is not None and actual <= float(check["value"]) + 1e-9
        detail = f"expected<={check['value']} actual={actual}"

    elif kind == "numeric_gte":
        actual = safe_float(value)
        passed = actual is not None and actual >= float(check["value"]) - 1e-9
        detail = f"expected>={check['value']} actual={actual}"

    elif kind == "contains_all":
        terms = check["terms"]
        missing = [term for term in terms if not _term_present(value, term)]
        passed = not missing
        detail = f"missing={missing}"

    elif kind == "contains_any":
        terms = check["terms"]
        found = [term for term in terms if _term_present(value, term)]
        passed = bool(found)
        detail = f"found={found}"

    elif kind == "min_items":
        passed = isinstance(value, (list, tuple)) and len(value) >= int(check["n"])
        detail = f"expected>={check['n']} actual={len(value) if isinstance(value, (list, tuple)) else 'not-a-list'}"

    elif kind == "not_empty":
        passed = value is not None and bool(_text(value).strip())
        detail = f"actual={_text(value)[:100]!r}"

    elif kind == "in_set":
        passed = _text(value).strip().lower() in {str(v).lower() for v in check["values"]}
        detail = f"expected one of={check['values']} actual={value!r}"

    elif kind == "boolean_equals":
        passed = bool(value) is bool(check["value"])
        detail = f"expected={check['value']} actual={value!r}"

    elif kind == "regex":
        passed = bool(re.search(check["pattern"], _text(value), re.I))
        detail = f"pattern={check['pattern']!r} actual={_text(value)[:120]!r}"

    elif kind == "json_has_keys":
        target = _get_path(artifact, path)
        keys = check["keys"]
        passed = isinstance(target, dict) and all(key in target for key in keys)
        detail = f"missing={[key for key in keys if not isinstance(target, dict) or key not in target]}"

    elif kind == "min_total_words":
        count = _words(_get_path(artifact, path))
        passed = count >= int(check["n"])
        detail = f"expected>={check['n']} actual={count}"

    elif kind == "yaml_services":
        try:
            parsed = yaml.safe_load(_text(value))
            services = parsed.get("services", {}) if isinstance(parsed, dict) else {}
            missing = [svc for svc in check["services"] if svc not in services]
            passed = not missing
            detail = f"missing={missing}"
        except Exception as exc:  # noqa: BLE001
            detail = f"invalid yaml: {exc}"

    elif kind == "yaml_contains":
        terms = check["terms"]
        missing = [term for term in terms if not _term_present(value, term)]
        passed = not missing
        detail = f"missing={missing}"

    elif kind == "yaml_contains_any":
        terms = check["terms"]
        found = [term for term in terms if _term_present(value, term)]
        passed = bool(found)
        detail = f"found={found}"

    elif kind == "yaml_not_contains":
        terms = check["terms"]
        found = [term for term in terms if _term_present(value, term)]
        passed = not found
        detail = f"forbidden_found={found}"

    elif kind == "yaml_port":
        port = check["port"]
        text = _text(value)
        if port:
            host = port.split(":")[0]
            passed = bool(re.search(rf"[\"']?{re.escape(port)}[\"']?", text)) or bool(
                re.search(rf"ports:\s*\[?[\"']?{re.escape(host)}[\"']?\s*:", text)
            )
            detail = f"expected port mapping {port}"
        else:
            passed = not re.search(r"^\s*ports:\s*$", text, re.M)
            detail = "expected no host ports"

    else:
        detail = f"unknown check type {kind}"

    return {"type": kind, "path": path, "passed": bool(passed), "detail": detail}


def validate_artifact(task: dict[str, Any], artifact: Any) -> dict[str, Any]:
    results = [run_check(check, artifact) for check in task["checks"]]
    passed = sum(1 for result in results if result["passed"])
    total = len(results)
    return {
        "task_id": task["id"],
        "phase": task["phase"],
        "score": passed / total if total else 0.0,
        "resolved": passed == total,
        "checks_passed": passed,
        "checks_total": total,
        "checks": results,
    }


def validate_reference(task: dict[str, Any]) -> dict[str, Any]:
    return validate_artifact(task, task["reference"])


if __name__ == "__main__":
    from .tasks import all_tasks

    failures = []
    for task in all_tasks():
        result = validate_reference(task)
        if not result["resolved"]:
            failures.append((task["id"], [c for c in result["checks"] if not c["passed"]]))
    if failures:
        print(json.dumps(failures, indent=2))
        raise SystemExit(f"{len(failures)} reference artifacts failed validation")
    print(f"all {len(all_tasks())} reference artifacts pass")
