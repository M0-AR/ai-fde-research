from __future__ import annotations

import json
from typing import Any

from . import config

PHASES = ["discovery", "architecture", "security", "context", "deployment", "handover"]


def _task(
    *,
    tid: str,
    phase: str,
    title: str,
    difficulty: int,
    risk: str,
    brief: str,
    evidence: dict[str, str],
    instruction: str,
    checks: list[dict[str, Any]],
    reference: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": tid,
        "phase": phase,
        "title": title,
        "difficulty": difficulty,
        "risk": risk,
        "brief": brief,
        "evidence": evidence,
        "instruction": instruction,
        "checks": checks,
        "reference": reference,
    }


def discovery_tasks() -> list[dict[str, Any]]:
    rows = [
        ("D01", "Meridian Mutual", "claims triage", "CIO", 450000, 14, "reduce claims cycle time by 30%", ["HIPAA", "no customer PII to external model"], "high"),
        ("D02", "Northstar Logistics", "invoice reconciliation", "CFO", 220000, 8, "raise touchless invoice rate to 60%", ["SOX", "ERP read-only access"], "medium"),
        ("D03", "Cedar Valley Health", "patient intake", "CMO", 600000, 20, "cut intake time by 40%", ["HIPAA", "patient consent"], "high"),
        ("D04", "Arcadia Bank", "KYC review", "Head of Compliance", 750000, 16, "reduce false positives by 25%", ["GDPR", "full audit trail"], "high"),
        ("D05", "Helios Utility", "field service dispatch", "COO", 300000, 12, "improve SLA attainment by 15 percentage points", ["union scheduling rules", "worker safety"], "medium"),
        ("D06", "Pemberton Legal", "contract review", "General Counsel", 180000, 6, "cut review hours by 50%", ["attorney-client privilege", "no training on client data"], "high"),
        ("D07", "Orbit Telco", "churn save", "CMO", 500000, 10, "lift save rate by 8 percentage points", ["TCPA consent", "opt-out honored"], "medium"),
        ("D08", "Aster Pharma", "drug safety intake", "Head of Pharmacovigilance", 900000, 24, "reduce case intake time by 35%", ["GxP", "21 CFR Part 11"], "high"),
    ]
    out = []
    for tid, company, domain, dm, budget, weeks, metric, constraints, risk in rows:
        brief = (
            f"{company} wants an AI agent for {domain}. The executive sponsor is the {dm}. "
            f"The approved budget is ${budget:,} and the target launch is {weeks} weeks from kickoff. "
            f"Success means to {metric}. Hard constraints: {constraints[0]} and {constraints[1]}. "
            "The current process is manual and the client has not agreed to any model training."
        )
        evidence = {
            "E1": f"Sponsor: {dm}; budget ${budget:,}; target {weeks} weeks.",
            "E2": f"Success metric from the business case: {metric}.",
            "E3": f"Non-negotiable constraints: {constraints[0]}; {constraints[1]}.",
            "E4": "Current process is manual; client has not approved model training or data resale.",
        }
        reference = {
            "decision_maker": dm,
            "budget_usd": budget,
            "timeline_weeks": weeks,
            "success_metric": metric,
            "constraints": constraints,
            "risks": [
                "data access approval may slip",
                "workflow owners may resist changes",
                "evaluation data may not represent production",
            ],
            "out_of_scope": ["model training", "data resale"],
            "next_step": "validate data access with security and run a two-week discovery slice",
        }
        checks = [
            {"type": "equals", "path": "decision_maker", "value": dm},
            {"type": "numeric_equals", "path": "budget_usd", "value": budget},
            {"type": "numeric_equals", "path": "timeline_weeks", "value": weeks},
            {"type": "contains_any", "path": "success_metric", "terms": [metric, metric.replace("reduce", "reduction"), metric.replace("cut", "reduction")]},
            {"type": "contains_all", "path": "constraints", "terms": constraints},
            {"type": "min_items", "path": "risks", "n": 3},
            {"type": "contains_any", "path": "out_of_scope", "terms": ["model training", "training"]},
        ]
        instruction = (
            "Act as the forward deployed engineer on the discovery call. Return JSON only:\n"
            '{"artifact": {"decision_maker": str, "budget_usd": number, "timeline_weeks": number, '
            '"success_metric": str, "constraints": [str], "risks": [str], "out_of_scope": [str], '
            '"next_step": str}, "citations": [str], "confidence": number}\n'
            "Use the exact figures and constraint names from the evidence. List at least three concrete risks. "
            "Keep the next step small enough to finish inside two weeks."
        )
        out.append(_task(tid=tid, phase="discovery", title=f"{company}: {domain} discovery", difficulty=1 if weeks <= 10 else 2, risk=risk, brief=brief, evidence=evidence, instruction=instruction, checks=checks, reference=reference))
    return out


def architecture_tasks() -> list[dict[str, Any]]:
    rows = [
        ("A01", "claims decision support", "human-in-the-loop", ["intake", "policy engine", "retrieval", "human review", "audit log"], 8000, 0.40, "high"),
        ("A02", "employee FAQ assistant", "rag", ["retriever", "generator", "cache", "evaluation suite"], 3000, 0.05, "low"),
        ("A03", "procurement orchestration", "orchestrator-worker", ["planner", "tool gateway", "validator", "approval gate"], 20000, 1.20, "high"),
        ("A04", "batch document extraction", "batch", ["queue", "OCR", "extractor", "validator"], 3600000, 0.02, "medium"),
        ("A05", "real-time fraud scoring", "event-driven", ["stream", "feature store", "scorer", "case manager"], 500, 0.01, "high"),
        ("A06", "support copilot", "rag+human-in-the-loop", ["retriever", "drafter", "guardrail", "agent desktop"], 5000, 0.15, "medium"),
        ("A07", "data migration agent", "orchestrator-worker", ["profiler", "mapper", "validator", "rollback"], 7200000, 2.00, "high"),
        ("A08", "executive briefing agent", "rag", ["retriever", "summarizer", "citation checker", "scheduler"], 10000, 0.25, "low"),
    ]
    out = []
    for tid, domain, pattern, components, latency, cost, risk in rows:
        brief = (
            f"Design the production architecture for a {domain} agent. The business requires a {pattern} pattern. "
            f"The service must meet a p95 latency of {latency} ms and a unit cost at or below ${cost:.2f}. "
            "Name the required components, the human checkpoint, the main failure modes, and the evaluation plan."
        )
        evidence = {
            "E1": f"Required pattern: {pattern}.",
            "E2": f"p95 latency budget: {latency} ms.",
            "E3": f"Unit cost ceiling: ${cost:.2f}.",
            "E4": "The architecture review rejects designs without an explicit human checkpoint and evaluation plan.",
        }
        reference = {
            "pattern": pattern,
            "components": components,
            "slo": {"p95_latency_ms": latency, "cost_per_unit_usd": cost},
            "human_checkpoint": "human review before any irreversible action",
            "failure_modes": ["retrieval misses", "tool timeout", "policy violation"],
            "evaluation_plan": ["offline golden set", "shadow traffic", "canary with rollback"],
        }
        checks = [
            {"type": "equals", "path": "pattern", "value": pattern},
            {"type": "contains_all", "path": "components", "terms": components},
            {"type": "numeric_lte", "path": "slo.p95_latency_ms", "value": latency},
            {"type": "numeric_lte", "path": "slo.cost_per_unit_usd", "value": cost},
            {"type": "min_items", "path": "failure_modes", "n": 3},
            {"type": "min_items", "path": "evaluation_plan", "n": 2},
            {"type": "not_empty", "path": "human_checkpoint"},
        ]
        instruction = (
            "Return JSON only:\n"
            '{"artifact": {"pattern": str, "components": [str], "slo": {"p95_latency_ms": number, '
            '"cost_per_unit_usd": number}, "human_checkpoint": str, "failure_modes": [str], '
            '"evaluation_plan": [str]}, "citations": [str], "confidence": number}\n'
            "Use exactly the required pattern name and include every required component. Do not weaken the latency or cost ceilings."
        )
        out.append(_task(tid=tid, phase="architecture", title=f"Architecture: {domain}", difficulty=2 if risk == "high" else 1, risk=risk, brief=brief, evidence=evidence, instruction=instruction, checks=checks, reference=reference))
    return out


def security_tasks() -> list[dict[str, Any]]:
    rows = [
        ("S01", "indirect prompt injection in retrieved email", ["input isolation", "tool allowlist", "output filter", "human approval", "audit log"]),
        ("S02", "excessive agency through a write-capable tool", ["least privilege", "scoped tokens", "approval gate", "rate limit", "audit log"]),
        ("S03", "data exfiltration through a rendered link", ["egress allowlist", "sanitize output", "DLP check", "human approval", "audit log"]),
        ("S04", "memory poisoning across sessions", ["provenance", "write approval", "TTL", "integrity check", "audit log"]),
        ("S05", "malicious MCP server in the supply chain", ["signed registry", "version pinning", "sandbox", "security review", "audit log"]),
        ("S06", "identity spoofing between agents", ["SSO", "mutual TLS", "per-user authorization", "no shared secrets", "audit log"]),
        ("S07", "insecure output handling in the UI", ["output encoding", "schema validation", "content security policy", "sandboxed render", "audit log"]),
        ("S08", "denial of wallet through runaway loops", ["token budget", "rate limit", "circuit breaker", "anomaly alert", "audit log"]),
    ]
    out = []
    for tid, threat, controls in rows:
        brief = (
            f"A production agent has the following threat: {threat}. Produce a threat model and a deny-by-default control plan. "
            "The plan must include five controls, at least three concrete test cases, a residual-risk rating, and an explicit human approval point."
        )
        evidence = {
            "E1": f"Threat: {threat}.",
            "E2": "Security policy requires deny-by-default, least privilege, and an audit trail for every external action.",
            "E3": "A control is not accepted unless it has a test case that would fail without it.",
        }
        reference = {
            "threat": threat,
            "controls": controls,
            "residual_risk": "medium",
            "test_cases": [
                f"adversarial input exercising {threat}",
                "benign control input that must not be blocked",
                "tool invocation outside the allowlist must be denied",
            ],
            "approval_point": "human approval before any write, send, or delete action",
            "policy": "deny by default; allow only explicit tools and data scopes",
        }
        checks = [
            {"type": "contains_any", "path": "threat", "terms": [threat, threat.split()[0]]},
            {"type": "contains_all", "path": "controls", "terms": controls},
            {"type": "min_items", "path": "test_cases", "n": 3},
            {"type": "in_set", "path": "residual_risk", "values": ["low", "medium", "high"]},
            {"type": "not_empty", "path": "approval_point"},
            {"type": "contains_any", "path": "policy", "terms": ["deny by default", "least privilege"]},
        ]
        instruction = (
            "Return JSON only:\n"
            '{"artifact": {"threat": str, "controls": [str], "residual_risk": "low|medium|high", '
            '"test_cases": [str], "approval_point": str, "policy": str}, "citations": [str], "confidence": number}\n'
            "Include every control named in the evidence, at least three test cases, and a deny-by-default policy statement."
        )
        out.append(_task(tid=tid, phase="security", title=f"Threat model: {threat}", difficulty=2, risk="high" if tid in {"S01", "S02", "S03", "S04"} else "medium", brief=brief, evidence=evidence, instruction=instruction, checks=checks, reference=reference))
    return out


def context_tasks() -> list[dict[str, Any]]:
    rows = [
        ("C01", "customer preference", "E1", 90, False, "newest-verified-wins"),
        ("C02", "production incident", "E2", 365, True, "human-override"),
        ("C03", "product FAQ", "E3", 30, False, "source-authority"),
        ("C04", "contract clause", "E4", 2555, True, "legal-review"),
        ("C05", "user correction", "E5", 180, False, "user-confirmed"),
        ("C06", "operational runbook", "E6", 730, False, "version-priority"),
        ("C07", "vendor risk finding", "E7", 365, True, "compliance-hold"),
        ("C08", "conversation summary", "E8", 14, True, "recency"),
    ]
    out = []
    for tid, kind, source, retention, pii, rule in rows:
        brief = (
            f"Write a durable memory record for a {kind}. The only authoritative source is {source}. "
            f"Retention is {retention} days. The record {'contains' if pii else 'does not contain'} personal data. "
            f"When sources conflict, apply the {rule} rule. Every claim must cite its source."
        )
        evidence = {
            source: f"Authoritative {kind} content for this task; source id {source}.",
            "E9": "A conflicting but older secondary note exists; it must not override the authoritative source.",
        }
        reference = {
            "memory": {
                "kind": kind,
                "source_ids": [source],
                "retention_days": retention,
                "pii": pii,
                "conflict_rule": rule,
                "claims": [{"text": f"Authoritative {kind} fact", "source_id": source}],
            },
            "deletion_path": "delete by record id through the memory API",
            "confidence": 0.9,
        }
        checks = [
            {"type": "equals", "path": "memory.kind", "value": kind},
            {"type": "contains_any", "path": "memory.source_ids", "terms": [source]},
            {"type": "numeric_equals", "path": "memory.retention_days", "value": retention},
            {"type": "boolean_equals", "path": "memory.pii", "value": pii},
            {"type": "equals", "path": "memory.conflict_rule", "value": rule},
            {"type": "min_items", "path": "memory.claims", "n": 1},
            {"type": "not_empty", "path": "deletion_path"},
        ]
        instruction = (
            "Return JSON only:\n"
            '{"artifact": {"memory": {"kind": str, "source_ids": [str], "retention_days": number, '
            '"pii": boolean, "conflict_rule": str, "claims": [{"text": str, "source_id": str}]}, '
            '"deletion_path": str}, "citations": [str], "confidence": number}\n'
            "Cite only the authoritative source. Preserve the retention, PII, and conflict-rule values exactly."
        )
        out.append(_task(tid=tid, phase="context", title=f"Memory record: {kind}", difficulty=1 if not pii else 2, risk="medium" if pii else "low", brief=brief, evidence=evidence, instruction=instruction, checks=checks, reference=reference))
    return out


def deployment_tasks() -> list[dict[str, Any]]:
    rows = [
        ("P01", "static web tier", ["web"], "8080:80", ["healthcheck", "read_only"], "nginx:1.27-alpine"),
        ("P02", "api with cache", ["api", "cache"], "8000:8000", ["healthcheck", "depends_on", "read_only"], "python:3.12-slim"),
        ("P03", "worker with queue", ["worker", "queue"], "", ["healthcheck", "depends_on", "restart"], "python:3.12-slim"),
        ("P04", "api with database", ["api", "db"], "8000:8000", ["healthcheck", "depends_on", "volume"], "python:3.12-slim"),
        ("P05", "reverse proxy", ["proxy", "api"], "80:80", ["healthcheck", "depends_on", "read_only"], "nginx:1.27-alpine"),
        ("P06", "three-tier stack", ["web", "api", "cache"], "8080:80", ["healthcheck", "depends_on", "network"], "nginx:1.27-alpine"),
        ("P07", "repair broken api stack", ["api", "cache"], "8000:8000", ["healthcheck", "depends_on", "restart"], "python:3.12-slim"),
        ("P08", "repair insecure stack", ["api", "db"], "8000:8000", ["healthcheck", "non_root", "secret"], "python:3.12-slim"),
    ]
    out = []
    for tid, name, services, ports, requirements, image in rows:
        brief = (
            f"Author a production Docker Compose file for a {name}. Required services: {', '.join(services)}. "
            f"Expose {ports or 'no host ports'}. The stack must include: {', '.join(requirements)}. "
            "Do not use the latest tag, do not bake plaintext secrets into the file, and do not run as root."
        )
        evidence = {
            "E1": f"Required services: {', '.join(services)}.",
            "E2": f"Host port mapping: {ports or 'none'}.",
            "E3": f"Required controls: {', '.join(requirements)}.",
            "E4": "Base image family: " + image + ".",
            "E5": "Never use the latest tag or plaintext credentials in the compose file.",
        }
        service_blocks = []
        for index, svc in enumerate(services):
            block = (
                f"  {svc}:\n    image: {image}\n    restart: unless-stopped\n"
                "    healthcheck:\n      test: [\"CMD-SHELL\", \"true\"]\n"
                "      interval: 10s\n      timeout: 3s\n      retries: 3\n"
                "    read_only: true\n"
            )
            if index > 0:
                block += f"    depends_on:\n      - {services[0]}\n"
            if index == 0 and ports:
                block += f"    ports: [\"{ports}\"]\n"
            service_blocks.append(block)
        reference = {"compose_yaml": "services:\n" + "".join(service_blocks)}
        checks = [
            {"type": "yaml_services", "path": "compose_yaml", "services": services},
            {"type": "yaml_contains", "path": "compose_yaml", "terms": ["healthcheck:", "restart:"]},
            {"type": "yaml_not_contains", "path": "compose_yaml", "terms": [":latest", "password: admin", "POSTGRES_PASSWORD: postgres"]},
            {"type": "yaml_contains_any", "path": "compose_yaml", "terms": ["read_only: true", "user:"]},
            {"type": "yaml_port", "path": "compose_yaml", "port": ports},
        ]
        if "depends_on" in requirements:
            checks.append({"type": "yaml_contains", "path": "compose_yaml", "terms": ["depends_on:"]})
        instruction = (
            "Return JSON only:\n"
            '{"artifact": {"compose_yaml": "string containing a complete docker-compose.yml"}, '
            '"citations": [str], "confidence": number}\n'
            "The YAML must be syntactically valid, define every required service, include healthchecks, use a pinned image tag, "
            "and avoid plaintext secrets. Do not wrap the YAML in markdown."
        )
        out.append(_task(tid=tid, phase="deployment", title=f"Compose: {name}", difficulty=2 if tid not in {"P07", "P08"} else 3, risk="high" if tid in {"P04", "P08"} else "medium", brief=brief, evidence=evidence, instruction=instruction, checks=checks, reference=reference))
    return out


def handover_tasks() -> list[dict[str, Any]]:
    rows = [
        ("H01", "claims agent production handover", ["owner", "on_call", "slo", "rollback", "escalation", "known_limitations", "next_steps"]),
        ("H02", "model upgrade handover", ["version", "eval_delta", "rollback", "canary", "monitoring"]),
        ("H03", "incident postmortem handover", ["timeline", "root_cause", "corrective_actions", "owner", "due_dates"]),
        ("H04", "customer training handover", ["audience", "curriculum", "exercises", "certification", "support"]),
        ("H05", "vendor transition handover", ["assets", "credentials", "contracts", "exit_plan", "knowledge_transfer"]),
        ("H06", "prompt injection alert runbook", ["trigger", "triage", "containment", "eradication", "recovery", "communication"]),
        ("H07", "cost overrun handover", ["budget", "burn_rate", "levers", "approval", "forecast"]),
        ("H08", "end-of-engagement handover", ["acceptance_criteria", "residual_risks", "backlog", "ownership_matrix", "warranty"]),
    ]
    out = []
    for tid, name, keys in rows:
        brief = (
            f"Produce the {name} for the client. The receiving team must be able to operate, monitor, and roll back the system without the FDE. "
            f"Include these sections: {', '.join(keys)}. Give at least three rollback steps and one named accountable owner."
        )
        evidence = {
            "E1": "The client will own the system after the engagement; the FDE is not retained for run operations.",
            "E2": "Acceptance requires a tested rollback, a named owner, and a monitoring dashboard.",
            "E3": "Known limitations must be written down rather than transferred verbally.",
        }
        reference = {}
        for key in keys:
            if key == "rollback":
                reference[key] = [
                    "freeze deployments and announce the maintenance window",
                    "restore the previous model and configuration from the signed release bundle",
                    "replay the smoke suite and confirm the health dashboard before reopening traffic",
                ]
            elif key in {"known_limitations", "residual_risks", "corrective_actions", "levers", "assets", "exercises", "backlog"}:
                reference[key] = [
                    f"{key.replace('_', ' ')} item one with an accountable owner and due date",
                    f"{key.replace('_', ' ')} item two with a verification step and evidence link",
                ]
            else:
                reference[key] = (
                    f"{key.replace('_', ' ').title()}: the client platform lead owns this section; "
                    "the runbook names the dashboard, the approval path, and the evidence required to close it. "
                    "The receiving team has been trained and has rehearsed the procedure once."
                )
        reference["owner"] = "client platform lead"
        checks = [{"type": "json_has_keys", "path": "", "keys": keys}]
        if "rollback" in keys:
            checks.append({"type": "min_items", "path": "rollback", "n": 3})
        if "owner" in keys:
            checks.append({"type": "not_empty", "path": "owner"})
        if "known_limitations" in keys:
            checks.append({"type": "min_items", "path": "known_limitations", "n": 2})
        checks.append({"type": "min_total_words", "path": "", "n": 60})
        instruction = (
            "Return JSON only:\n"
            '{"artifact": {' + ", ".join(f'"{key}": ' + ('[str]' if key in {"rollback", "corrective_actions", "levers", "assets", "exercises"} else "str") for key in keys) + '}, '
            '"citations": [str], "confidence": number}\n'
            "Fill every section with concrete operational content, not placeholders. Include at least three rollback steps where rollback is requested."
        )
        out.append(_task(tid=tid, phase="handover", title=f"Handover: {name}", difficulty=1 if len(keys) <= 5 else 2, risk="medium", brief=brief, evidence=evidence, instruction=instruction, checks=checks, reference=reference))
    return out


def all_tasks() -> list[dict[str, Any]]:
    tasks = discovery_tasks() + architecture_tasks() + security_tasks() + context_tasks() + deployment_tasks() + handover_tasks()
    seen = set()
    for task in tasks:
        if task["id"] in seen:
            raise ValueError(f"duplicate task id {task['id']}")
        seen.add(task["id"])
    return tasks


def write_tasks() -> list[dict[str, Any]]:
    config.ensure_dirs()
    tasks = all_tasks()
    path = config.BENCHMARK_DIR / "tasks.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(tasks, handle, indent=2)
        handle.write("\n")
    return tasks


if __name__ == "__main__":
    written = write_tasks()
    print(f"wrote {len(written)} tasks to {config.BENCHMARK_DIR / 'tasks.json'}")
