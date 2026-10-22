from fde_research.report import latex_table, tex_escape


def test_tex_escape_percent_and_underscore():
    assert tex_escape("19.3%") == r"19.3\%"
    assert tex_escape("qwen_1.5b") == r"qwen\_1.5b"


def test_latex_table_escapes_cells():
    text = latex_table(["Metric", "Value"], [["Share", "19.3%"]], "Caption", "tab:test")
    assert r"19.3\%" in text
    assert "19.3%" not in text.replace(r"19.3\%", "")
