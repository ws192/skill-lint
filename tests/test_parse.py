from pathlib import Path

from tests.conftest import skill_markdown

from skill_lint.parse import parse_skill_markdown


def test_parses_frontmatter_and_body(tmp_path):
    path = tmp_path / "SKILL.md"
    raw = skill_markdown(name="demo", extra={"license": "MIT"})
    doc = parse_skill_markdown(raw, path, tmp_path)
    assert doc.frontmatter["name"] == "demo"
    assert doc.frontmatter["license"] == "MIT"
    assert "Carry out the documented steps" in doc.body
    assert doc.key_locations["name"].line >= 2
    assert doc.parse_findings == []


def test_missing_frontmatter():
    doc = parse_skill_markdown("# Just a heading\n", Path("SKILL.md"), Path("."))
    assert any(item.rule == "frontmatter-missing" for item in doc.parse_findings)
    assert doc.frontmatter is None


def test_unclosed_frontmatter():
    raw = "---\nname: demo\ndescription: hi\n# no closer\n"
    doc = parse_skill_markdown(raw, Path("SKILL.md"), Path("demo"))
    assert any(item.rule == "frontmatter-unclosed" for item in doc.parse_findings)


def test_invalid_yaml_reports_line():
    raw = "---\nname: [unterminated\ndescription: ok\n---\n\nBody text is here and long enough.\n"
    doc = parse_skill_markdown(raw, Path("SKILL.md"), Path("demo"))
    findings = [item for item in doc.parse_findings if item.rule == "frontmatter-invalid"]
    assert findings
    assert findings[0].line >= 2


def test_frontmatter_not_mapping():
    raw = "---\n- just\n- a list\n---\n\n# Title\n\nSome instruction text lives here.\n"
    doc = parse_skill_markdown(raw, Path("SKILL.md"), Path("demo"))
    assert any(item.rule == "frontmatter-not-mapping" for item in doc.parse_findings)


def _sample_with_prefix(prefix: str) -> str:
    return (
        prefix
        + "---\n"
        + "name: demo\n"
        + "description: A clear description. Use when testing the parser.\n"
        + "---\n\n"
        + "# Demo\n\n"
        + "1. Do the work in a few careful steps.\n"
    )


def test_leading_blank_line():
    doc = parse_skill_markdown(_sample_with_prefix("\n"), Path("SKILL.md"), Path("demo"))
    assert any(item.rule == "frontmatter-leading-content" for item in doc.parse_findings)
    assert doc.frontmatter["name"] == "demo"


def test_bom_is_reported_and_stripped():
    doc = parse_skill_markdown(_sample_with_prefix("\ufeff"), Path("SKILL.md"), Path("demo"))
    assert any(item.rule == "frontmatter-leading-content" for item in doc.parse_findings)
    assert doc.frontmatter["name"] == "demo"
