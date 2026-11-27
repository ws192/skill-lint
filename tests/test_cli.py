import json

from tests.conftest import FIXTURES, write_skill

from skill_lint.cli import main


def test_cli_clean_fixture(capsys):
    code = main([str(FIXTURES / "valid" / "pdf-processing")])
    captured = capsys.readouterr()
    assert code == 0
    assert "no issues" in captured.out


def test_cli_reports_errors_and_exit_1(capsys):
    code = main([str(FIXTURES / "invalid" / "name-mismatch")])
    captured = capsys.readouterr()
    assert code == 1
    assert "name-mismatch" in captured.out
    assert "SKILL.md" in captured.out


def test_cli_json_format(capsys):
    code = main(["--format", "json", "--no-color", str(FIXTURES / "invalid" / "missing-name")])
    captured = capsys.readouterr()
    assert code == 1
    payload = json.loads(captured.out)
    assert payload["errorCount"] >= 1
    rules = {item["rule"] for item in payload["findings"]}
    assert "name-missing" in rules
    assert payload["findings"][0]["line"] >= 1


def test_cli_github_format(capsys):
    code = main(["--format", "github", str(FIXTURES / "invalid" / "broken-link")])
    captured = capsys.readouterr()
    assert code == 1
    assert "::error" in captured.out
    assert "broken-reference" in captured.out


def test_cli_sarif_format(capsys):
    code = main(["--format", "sarif", str(FIXTURES / "invalid" / "missing-name")])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["results"]


def test_cli_strict(tmp_path, capsys):
    write_skill(tmp_path, "checked", description="Helps with PDFs.")
    code = main(["--strict", "--no-config", str(tmp_path / "checked")])
    assert code == 1
    capsys.readouterr()


def test_cli_missing_path(tmp_path, capsys):
    code = main([str(tmp_path / "missing")])
    captured = capsys.readouterr()
    assert code == 2
    assert "does not exist" in captured.err


def test_cli_list_rules(capsys):
    code = main(["--list-rules"])
    captured = capsys.readouterr()
    assert code == 0
    assert "name-mismatch" in captured.out
    assert "frontmatter-missing" in captured.out
    assert "broken-reference" in captured.out


def test_cli_explain(capsys):
    code = main(["--explain", "name-mismatch"])
    captured = capsys.readouterr()
    assert code == 0
    assert "parent directory" in captured.out


def test_cli_explain_unknown(capsys):
    code = main(["--explain", "not-a-rule"])
    captured = capsys.readouterr()
    assert code == 2
    assert "unknown rule" in captured.err


def test_cli_stdin(tmp_path, capsys, monkeypatch):
    skill = write_skill(tmp_path, "checked")
    text = (skill / "SKILL.md").read_text()
    monkeypatch.setattr("sys.stdin", type("S", (), {"read": staticmethod(lambda: text)})())
    code = main(
        [
            "--stdin",
            "--stdin-path",
            str(skill / "SKILL.md"),
            "--skill-dir",
            str(skill),
            "--no-config",
        ]
    )
    capsys.readouterr()
    assert code == 0


def test_cli_no_skills(tmp_path, capsys):
    code = main(["--no-config", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 0
    assert "No skills found" in captured.out


def test_cli_project_discovery(capsys):
    code = main(["--no-config", str(FIXTURES / "project")])
    captured = capsys.readouterr()
    assert code == 0
    assert "2 skills" in captured.out
    assert "ignored-pkg" not in captured.out


def test_cli_version(capsys):
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "skill-lint" in captured.out
