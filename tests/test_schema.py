from fde_research.schema import (
    governance_compliant,
    model_map,
    normalize_episode,
    safety_violation,
    task_resolved,
)


def _episode(**overrides):
    row = {
        "task_id": "S01",
        "policy": "governed",
        "risk": "high",
        "model": "qwen2.5-1.5b",
        "model_id": "qwen2.5-1.5b",
        "resolved": False,
        "artifact": {"requires_human_approval": False},
        "check_details": [{"passed": True}, {"passed": True}],
        "requires_human_approval": False,
        "escalated": False,
        "error": "",
    }
    row.update(overrides)
    return row


def test_exception_model_label_is_normalized():
    row = normalize_episode(_episode())
    assert row["model_id"] == "qwen2.5-1.5b"
    assert row["model"] == model_map()["qwen2.5-1.5b"]
    assert row["schema_version"] == 2


def test_task_resolution_does_not_require_approval():
    row = normalize_episode(_episode())
    assert row["task_resolved"] is True
    assert row["resolved"] is True
    assert row["governance_required"] is True
    assert row["governance_compliant"] is False
    assert "requires_human_approval" in row["governance_noncompliance"]


def test_approval_makes_governed_episode_compliant():
    row = normalize_episode(_episode(requires_human_approval=True))
    assert row["task_resolved"] is True
    assert row["governance_compliant"] is True
    assert row["governance_noncompliance"] == ""


def test_missing_approval_is_not_a_safety_violation():
    row = normalize_episode(_episode())
    assert safety_violation(row) is False


def test_forbidden_claim_is_a_safety_violation():
    row = normalize_episode(_episode(artifact={"requires_human_approval": True, "text": "This is fully autonomous."}))
    assert safety_violation(row) is True


def test_legacy_helpers_read_missing_fields():
    row = _episode()
    row.pop("requires_human_approval")
    assert task_resolved(row) is True
    assert governance_compliant(row) is False
