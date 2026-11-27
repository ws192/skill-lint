"""Shared test helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from skill_lint.config import Config
from skill_lint.lint import lint_paths
from skill_lint.models import Finding, Report

FIXTURES = Path(__file__).parent / "fixtures"


def skill_markdown(
    *,
    name: str | None = "sample-skill",
    description: str | None = (
        "Do a specific useful task for the user. Use when the user asks for that task."
    ),
    extra: dict[str, Any] | None = None,
    body: str | None = None,
    raw_frontmatter: str | None = None,
) -> str:
    if raw_frontmatter is not None:
        fm = raw_frontmatter
    else:
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if extra:
            data.update(extra)
        dumped = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
        fm = dumped
    if body is None:
        body = (
            "\n# Sample skill\n\n"
            "1. Confirm the request and any inputs.\n"
            "2. Carry out the documented steps carefully.\n"
            "3. Report the result, including anything that could not be done.\n"
        )
    if not body.startswith("\n"):
        body = "\n" + body
    if not body.endswith("\n"):
        body += "\n"
    return f"---\n{fm}\n---{body}"


def write_skill(
    root: Path,
    name: str = "sample-skill",
    *,
    description: str | None = None,
    extra: dict[str, Any] | None = None,
    body: str | None = None,
    raw_frontmatter: str | None = None,
    filename: str = "SKILL.md",
    files: dict[str, str] | None = None,
    content: str | None = None,
) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = content or skill_markdown(
        name=None if raw_frontmatter is not None else name,
        description=description
        if description is not None or raw_frontmatter is not None
        else (
            "Do a specific useful task for the user. Use when the user asks for that task."
        ),
        extra=extra,
        body=body,
        raw_frontmatter=raw_frontmatter,
    )
    (skill_dir / filename).write_text(text, encoding="utf-8")
    if files:
        for relative, file_body in files.items():
            path = skill_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file_body, encoding="utf-8")
    return skill_dir


def lint_dir(path: Path, **overrides: Any) -> Report:
    config = Config(**overrides) if overrides else Config()
    return lint_paths([path], config)


def rules_in(report: Report, rule: str) -> list[Finding]:
    return [item for item in report.findings if item.rule == rule]


def rule_ids(report: Report) -> set[str]:
    return {item.rule for item in report.findings}


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES
