from fde_research.validators import run_check


def check(kind, artifact, **kwargs):
    return run_check({"type": kind, **kwargs}, artifact)["passed"]


def test_contains():
    assert check("contains_all", "we keep an audit log", terms=["audit"])
    assert check("yaml_not_contains", "image: nginx:1.27-alpine", terms=["latest"])


def test_regex():
    assert check("regex", "the GDPR applies", pattern=r"\bGDPR\b")
    assert not check("regex", "the CCPA applies", pattern=r"\bGDPR\b")


def test_numeric_bounds():
    assert check("numeric_gte", 12, value=10)
    assert not check("numeric_gte", 9, value=10)
    assert check("numeric_lte", 10, value=10)


def test_min_items():
    assert check("min_items", ["a", "b"], n=2)
    assert not check("min_items", ["a"], n=2)


def test_json_keys():
    assert check("json_has_keys", {"owner": "x", "risk": "high"}, keys=["owner", "risk"])
    assert not check("json_has_keys", {"owner": "x"}, keys=["owner", "risk"])


def test_words():
    assert check("min_total_words", "one two three four", n=3)
    assert not check("min_total_words", "one two", n=3)


def test_yaml_services_and_port():
    text = """services:
  web:
    image: nginx:1.27-alpine
    healthcheck:
      test: ["CMD", "true"]
    ports:
      - "8080:80"
"""
    assert check("yaml_services", text, services=["web"])
    assert check("yaml_port", text, port="8080:80")
    assert check("yaml_contains", text, terms=["healthcheck"])


def test_bad_yaml_fails_cleanly():
    result = run_check({"type": "yaml_services", "services": ["web"]}, "services: [")
    assert not result["passed"]
    assert result["detail"]
