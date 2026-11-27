"""Rule protocol and finding helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from skill_lint.config import Config
from skill_lint.models import Finding, Location, Severity, SkillDocument


@dataclass
class LintContext:
    config: Config
    documents: Sequence[SkillDocument] = field(default_factory=list)


class Rule(Protocol):
    id: str
    description: str
    default_severity: Severity
    explanation: str
    examples: str

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        """Return findings for one skill. Return an empty list when clean."""
        ...


def loc(line: int, column: int = 1, end_line: int | None = None, end_column: int | None = None) -> Location:
    return Location(line=line, column=column, end_line=end_line, end_column=end_column)


def finding(
    rule: str,
    message: str,
    path: Path,
    location: Location,
    severity: Severity,
    hint: str | None = None,
) -> Finding:
    return Finding(
        rule=rule,
        severity=severity,
        message=message,
        path=path,
        location=location,
        hint=hint,
    )


def file_start(doc: SkillDocument) -> Location:
    return loc(1)


def body_location(doc: SkillDocument, line_in_body: int = 1, column: int = 1) -> Location:
    line = max(1, doc.body_start_line + line_in_body - 1)
    return loc(line, column)
