from pathlib import Path

from tests.conftest import rule_ids, write_skill

from skill_lint.config import Config, apply_mapping, find_config, load_config, load_config_file
from skill_lint.lint import exit_code, lint_paths
from skill_lint.models import Report, Severity


def test_load_toml_config(tmp_path):
    config_path = tmp_path / ".skill-lint.toml"
    config_path.write_text(
        'profile = "strict"\n'
        'ignore = ["placeholder"]\n'
        "strict = true\n"
        "[severity]\n"
        'unknown-field = "off"\n'
        "[rules.description-vague]\n"
        "min-length = 20\n",
        encoding="utf-8",
    )
    config = load_config_file(config_path)
    assert config.profile == "strict"
    assert "placeholder" in config.ignore
    assert config.severity_overrides.get("unknown-field") is None
    assert "unknown-field" in config.ignore
    assert config.description_min_length == 20
    assert config.strict is True


def test_pyproject_table(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = 'demo'\nversion = '0'\n\n[tool.skill-lint]\nformat = 'json'\n",
        encoding="utf-8",
    )
    found = find_config(tmp_path)
    assert found == pyproject
    config = load_config(None, start=tmp_path)
    assert config.format == "json"


def test_ignore_and_only(tmp_path):
    write_skill(tmp_path, "checked", description="Helps with PDFs.")
    report = lint_paths([tmp_path / "checked"], Config(ignore={"description-vague"}))
    assert "description-vague" not in rule_ids(report)
    report = lint_paths([tmp_path / "checked"], Config(only={"description-vague"}))
    assert rule_ids(report) == {"description-vague"}


def test_exit_codes():
    clean = Report(findings=[], skill_count=1)
    assert exit_code(clean, Config()) == 0

    from skill_lint.models import Finding, Location

    warning = Finding(
        rule="description-vague",
        severity=Severity.WARNING,
        message="vague",
        path=Path("SKILL.md"),
        location=Location(1),
    )
    report = Report(findings=[warning], skill_count=1)
    assert exit_code(report, Config()) == 0
    assert exit_code(report, Config(strict=True)) == 1
    assert exit_code(report, Config(max_warnings=0)) == 1
    assert exit_code(report, Config(max_warnings=5)) == 0

    error = Finding(
        rule="name-missing",
        severity=Severity.ERROR,
        message="missing",
        path=Path("SKILL.md"),
        location=Location(1),
    )
    assert exit_code(Report(findings=[error], skill_count=1), Config()) == 1


def test_apply_mapping_rejects_bad_profile():
    try:
        apply_mapping(Config(), {"profile": "nope"})
    except ValueError as exc:
        assert "profile" in str(exc)
    else:
        raise AssertionError("expected ValueError")
