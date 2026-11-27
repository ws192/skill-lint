from tests.conftest import lint_dir, rule_ids, rules_in, write_skill

from skill_lint.config import Config
from skill_lint.lint import lint_paths

GOOD_DESC = (
    "Extract text and tables from PDF files and fill forms. "
    "Use when the user mentions PDFs or form filling."
)


def test_valid_fixture_is_clean():
    report = lint_dir(__import__("pathlib").Path("tests/fixtures/valid/pdf-processing"))
    # Resolve via fixtures path to be cwd-independent
    from tests.conftest import FIXTURES

    report = lint_dir(FIXTURES / "valid" / "pdf-processing")
    assert report.findings == [], [item.rule + ": " + item.message for item in report.findings]
    assert report.skill_count == 1


def test_cursor_vendor_fields_are_accepted():
    from tests.conftest import FIXTURES

    report = lint_dir(FIXTURES / "valid" / "react-component-patterns")
    assert report.findings == [], [item.rule + ": " + item.message for item in report.findings]


def test_missing_name_and_description(tmp_path):
    write_skill(
        tmp_path,
        "sample-skill",
        raw_frontmatter="license: MIT",
        body="# Title\n\n1. Do a careful step.\n2. Do another careful step.\n3. Finish up.\n",
    )
    report = lint_dir(tmp_path)
    assert {"name-missing", "description-missing"} <= rule_ids(report)


def test_name_rules(tmp_path):
    cases = [
        ("PDF-Processing", {"name-case", "name-mismatch"}),
        ("-pdf", {"name-hyphen", "name-mismatch"}),
        ("pdf--tools", {"name-hyphen", "name-mismatch"}),
        ("pdf_tools", {"name-charset", "name-mismatch"}),
        ("claude-review", {"name-reserved", "name-mismatch"}),
        ("a" * 65, {"name-length", "name-mismatch"}),
    ]
    for name, expected in cases:
        skill_dir = tmp_path / "checked"
        if skill_dir.exists():
            for path in sorted(skill_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            skill_dir.rmdir()
        write_skill(tmp_path, "checked")
        text = skill_dir.joinpath("SKILL.md").read_text()
        text = text.replace("name: checked", f"name: {name}")
        skill_dir.joinpath("SKILL.md").write_text(text)
        report = lint_dir(skill_dir)
        assert expected <= rule_ids(report), (name, rule_ids(report))


def test_empty_name(tmp_path):
    write_skill(tmp_path, "checked", raw_frontmatter='name: ""\ndescription: "' + GOOD_DESC + '"')
    report = lint_dir(tmp_path / "checked")
    assert "name-empty" in rule_ids(report)


def test_name_type(tmp_path):
    write_skill(tmp_path, "checked", raw_frontmatter="name: 1\ndescription: |\n  " + GOOD_DESC)
    report = lint_dir(tmp_path / "checked")
    assert "name-type" in rule_ids(report)


def test_name_mismatch_fixture():
    from tests.conftest import FIXTURES

    report = lint_dir(FIXTURES / "invalid" / "name-mismatch")
    assert "name-mismatch" in rule_ids(report)


def test_description_length_and_xml(tmp_path):
    write_skill(tmp_path, "checked", description="A" * 1025 + " Use when testing limits.")
    report = lint_dir(tmp_path / "checked")
    assert "description-length" in rule_ids(report)

    write_skill(
        tmp_path,
        "xmlish",
        description="Use this when the user mentions <file> paths in a prompt.",
    )
    report = lint_dir(tmp_path / "xmlish")
    assert "description-xml" in rule_ids(report)


def test_description_vague_and_no_when(tmp_path):
    write_skill(tmp_path, "checked", description="Helps with PDFs.")
    report = lint_dir(tmp_path / "checked")
    ids = rule_ids(report)
    assert "description-vague" in ids
    assert "description-no-when" in ids


def test_when_to_use_field_suppresses_no_when(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        description="Extracts text and tables from PDF files and fills form fields.",
        extra={"when_to_use": "The user mentions a PDF or a form."},
    )
    report = lint_dir(tmp_path / "checked")
    assert "description-no-when" not in rule_ids(report)


def test_compatibility_and_metadata(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        extra={"compatibility": 123, "metadata": ["x"]},
    )
    report = lint_dir(tmp_path / "checked")
    assert "compatibility-type" in rule_ids(report)
    assert "metadata-type" in rule_ids(report)

    write_skill(
        tmp_path,
        "meta",
        extra={"metadata": {"version": 1.0}, "compatibility": ""},
    )
    report = lint_dir(tmp_path / "meta")
    assert "metadata-value-type" in rule_ids(report)
    assert "compatibility-empty" in rule_ids(report)

    write_skill(tmp_path, "longcompat", extra={"compatibility": "x" * 501})
    report = lint_dir(tmp_path / "longcompat")
    assert "compatibility-length" in rule_ids(report)


def test_license_file_missing_and_present(tmp_path):
    write_skill(tmp_path, "checked", extra={"license": "LICENSE.txt"})
    report = lint_dir(tmp_path / "checked")
    assert "license-file-missing" in rule_ids(report)

    write_skill(
        tmp_path,
        "licensed",
        extra={"license": "LICENSE.txt"},
        files={"LICENSE.txt": "MIT License\n"},
    )
    report = lint_dir(tmp_path / "licensed")
    assert "license-file-missing" not in rule_ids(report)


def test_allowed_tools_and_broad(tmp_path):
    write_skill(tmp_path, "checked", extra={"allowed-tools": 12})
    report = lint_dir(tmp_path / "checked")
    assert "allowed-tools-type" in rule_ids(report)

    write_skill(tmp_path, "empty", extra={"allowed-tools": ""})
    report = lint_dir(tmp_path / "empty")
    assert "allowed-tools-empty" in rule_ids(report)

    write_skill(tmp_path, "broad", extra={"allowed-tools": "Bash Read"})
    report = lint_dir(tmp_path / "broad")
    assert "allowed-tools-broad" in rule_ids(report)

    write_skill(tmp_path, "narrow", extra={"allowed-tools": ["Bash(git:*)", "Read"]})
    report = lint_dir(tmp_path / "narrow")
    assert "allowed-tools-broad" not in rule_ids(report)
    assert "allowed-tools-type" not in rule_ids(report)


def test_legacy_globs_and_unknown_fields(tmp_path):
    write_skill(tmp_path, "checked", extra={"globs": "**/*.py", "desc": "nope"})
    report = lint_dir(tmp_path / "checked")
    assert "legacy-globs" in rule_ids(report)
    assert "unknown-field" in rule_ids(report)
    unknown = rules_in(report, "unknown-field")[0]
    assert "description" in (unknown.hint or "")


def test_field_alias(tmp_path):
    write_skill(tmp_path, "checked", extra={"allowed_tools": "Read"})
    report = lint_dir(tmp_path / "checked")
    assert "field-alias" in rule_ids(report)


def test_spec_profile_rejects_vendor_fields(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        extra={"paths": ["**/*.tsx"], "disable-model-invocation": True},
    )
    report = lint_paths([tmp_path / "checked"], Config(profile="spec"))
    assert "unknown-field" in rule_ids(report)
    assert any(item.severity.value == "error" for item in rules_in(report, "unknown-field"))


def test_boolean_and_color(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        extra={"disable-model-invocation": "sometimes", "color": "sparkly"},
    )
    report = lint_dir(tmp_path / "checked")
    assert "boolean-field-type" in rule_ids(report)
    assert "color-invalid" in rule_ids(report)


def test_duplicate_names(tmp_path):
    write_skill(tmp_path / "a", "one", extra={})
    # second skill with same name, different directory
    other = tmp_path / "b" / "two"
    write_skill(tmp_path / "b", "two")
    text = (other / "SKILL.md").read_text()
    (other / "SKILL.md").write_text(text.replace("name: two", "name: one"))
    report = lint_dir(tmp_path)
    assert "duplicate-name" in rule_ids(report)
    assert "name-mismatch" in rule_ids(report)
