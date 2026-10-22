from collections import Counter

from fde_research.tasks import all_tasks
from fde_research.validators import validate_reference


def test_task_bank_shape():
    tasks = all_tasks()
    assert len(tasks) == 48
    assert len({task["id"] for task in tasks}) == 48
    phases = Counter(task["phase"] for task in tasks)
    assert set(phases.values()) == {8}
    assert len(phases) == 6


def test_all_reference_artifacts_pass():
    for task in all_tasks():
        result = validate_reference(task)
        passed = result["resolved"]
        failures = [c for c in result["checks"] if not c["passed"]]
        assert passed, (task["id"], failures)
