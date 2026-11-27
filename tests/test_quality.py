from tests.conftest import lint_dir, rule_ids, write_skill


def test_body_empty(tmp_path):
    write_skill(tmp_path, "checked", body="\n")
    report = lint_dir(tmp_path / "checked")
    assert "body-empty" in rule_ids(report)
    assert "body-too-short" not in rule_ids(report)


def test_body_too_short(tmp_path):
    write_skill(tmp_path, "checked", body="\n# Title\n\nDo it.\n")
    report = lint_dir(tmp_path / "checked")
    assert "body-too-short" in rule_ids(report)


def test_body_too_long(tmp_path):
    steps = "\n".join(f"- step {i} with enough text to be real" for i in range(520))
    write_skill(tmp_path, "checked", body="\n# Long\n\n" + steps + "\n")
    report = lint_dir(tmp_path / "checked")
    assert "body-too-long" in rule_ids(report)
    finding = next(item for item in report.findings if item.rule == "body-too-long")
    assert finding.line >= 500


def test_placeholder(tmp_path):
    write_skill(
        tmp_path,
        "checked",
        body=(
            "# Skill\n\n"
            "TODO: write the actual upload steps after this.\n\n"
            "1. Confirm the destination.\n"
            "2. Follow the remaining steps once they exist.\n"
            "3. Report the outcome.\n"
        ),
    )
    report = lint_dir(tmp_path / "checked")
    assert "placeholder" in rule_ids(report)


def test_wrong_filename(tmp_path):
    write_skill(tmp_path, "checked", filename="skill.md")
    report = lint_dir(tmp_path / "checked")
    assert "skill-md-filename" in rule_ids(report)
