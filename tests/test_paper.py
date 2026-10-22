import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1] / "paper"


def test_latex_environments_are_balanced():
    text = (PAPER / "main.tex").read_text(encoding="utf-8")
    stack = []
    for match in re.finditer(r"\\(begin|end)\{([^}]+)\}", text):
        kind, name = match.groups()
        if kind == "begin":
            stack.append(name)
        else:
            assert stack and stack[-1] == name, f"unbalanced environment: {match.group(0)}"
            stack.pop()
    assert not stack, f"unclosed environments: {stack}"


def test_citations_exist_in_bib():
    text = (PAPER / "main.tex").read_text(encoding="utf-8")
    keys = set()
    for match in re.finditer(r"\\citep?\{([^}]+)\}", text):
        keys.update(key.strip() for key in match.group(1).split(","))
    bib = (PAPER / "references.bib").read_text(encoding="utf-8")
    defined = set(re.findall(r"@\w+\{([^,]+),", bib))
    assert keys <= defined, f"missing bibliography keys: {sorted(keys - defined)}"


def test_main_does_not_nest_a_table_input():
    text = (PAPER / "main.tex").read_text(encoding="utf-8")
    assert "\\input{generated/tables.tex}" in text
    start = text.index("\\input{generated/tables.tex}")
    assert "\\begin{table}" not in text[max(0, start - 300) : start], (
        "generated/tables.tex already contains table floats; do not wrap it in another table"
    )
