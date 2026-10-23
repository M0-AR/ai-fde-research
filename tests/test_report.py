from fde_research.report import latex_table, tex_escape


def test_tex_escape_percent_and_underscore():
    assert tex_escape("19.3%") == r"19.3\%"
    assert tex_escape("qwen_1.5b") == r"qwen\_1.5b"


def test_latex_table_escapes_cells():
    text = latex_table(["Metric", "Value"], [["Share", "19.3%"]], "Caption", "tab:test")
    assert r"19.3\%" in text
    assert "19.3%" not in text.replace(r"19.3\%", "")


def test_macro_stem_is_letters_only():
    from fde_research.report import _macro_stem

    stem = _macro_stem("qwen2.5:1.5b", "fde_disciplined")
    assert stem.isalpha()
    assert stem == "QwenTwoXFiveXOneXFivebFdeDisciplined"


def test_governance_ratio_counts_only_required_episodes():
    from fde_research.report import _gov_ratio

    row = {
        "n": 48,
        "governance_required": 15,
        "governance_compliant": 33,
        "governance_compliant_required": 0,
    }
    assert _gov_ratio(row) == "0/15"
    assert _gov_ratio({"n": 48, "governance_required": 0, "governance_compliant": 48}) == "n/a"
    legacy = {"n": 48, "governance_required": 15, "governance_compliant": 33}
    assert _gov_ratio(legacy) == "0/15"
