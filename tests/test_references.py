from tests.conftest import FIXTURES, lint_dir, rule_ids, write_skill


def test_broken_reference_fixture():
    report = lint_dir(FIXTURES / "invalid" / "broken-link")
    assert "broken-reference" in rule_ids(report)
    messages = " ".join(item.message for item in report.findings)
    assert "references/missing.md" in messages
    assert "scripts/not-there.py" in messages


def test_http_links_are_not_flagged(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        body=(
            "# Skill\n\n"
            "See the [docs](https://example.com/guide) and also [an anchor](#workflow).\n\n"
            "1. Confirm the request.\n"
            "2. Follow the public documentation if needed.\n"
            "3. Return the result.\n"
        ),
    )
    report = lint_dir(tmp_path / "checked")
    assert "broken-reference" not in rule_ids(report)


def test_unreferenced_and_empty_dirs(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        files={
            "scripts/extract.py": "print('ok')\n",
            "references/forms.md": "# forms\n",
        },
    )
    report = lint_dir(tmp_path / "checked")
    assert "unreferenced-script" in rule_ids(report)
    assert "unreferenced-reference" in rule_ids(report)

    write_skill(tmp_path, "emptyish", files={"scripts/.keep": ""})
    # .keep is ignored as a hidden file, so scripts/ is treated as empty
    report = lint_dir(tmp_path / "emptyish")
    assert "empty-resource-dir" in rule_ids(report)


def test_absolute_and_windows_paths(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        body=(
            "# Skill\n\n"
            "Run /usr/local/bin/extract and also scripts\\extract.py for output.\n\n"
            "1. Confirm the input file.\n"
            "2. Run the command shown above.\n"
            "3. Return the extracted text.\n"
        ),
        files={"scripts/extract.py": "print('ok')\n"},
    )
    report = lint_dir(tmp_path / "checked")
    ids = rule_ids(report)
    assert "absolute-path" in ids
    assert "windows-path" in ids


def test_nested_reference(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        body=(
            "# Skill\n\n"
            "Read the [overview](references/overview.md) and the [details](references/details.md).\n\n"
            "1. Confirm the document type.\n"
            "2. Follow the overview.\n"
            "3. Return the result.\n"
        ),
        files={
            "references/overview.md": "See the [details](details.md) next.\n",
            "references/details.md": "Detail lives here.\n",
        },
    )
    report = lint_dir(tmp_path / "checked")
    assert "nested-reference" in rule_ids(report)


def test_valid_skill_references_are_ok():
    report = lint_dir(FIXTURES / "valid" / "pdf-processing")
    assert "broken-reference" not in rule_ids(report)
    assert "unreferenced-script" not in rule_ids(report)
    assert "unreferenced-reference" not in rule_ids(report)
