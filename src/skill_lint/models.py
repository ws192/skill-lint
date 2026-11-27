"""Shared data types for skill-lint."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {Severity.ERROR: 3, Severity.WARNING: 2, Severity.INFO: 1}[self]


@dataclass(frozen=True, slots=True)
class Location:
    """1-based source location. column may be 0 when only the line is known."""

    line: int
    column: int = 1
    end_line: int | None = None
    end_column: int | None = None

    def with_span(self, end_line: int, end_column: int) -> Location:
        return Location(self.line, self.column, end_line, end_column)


@dataclass(frozen=True, slots=True)
class Finding:
    rule: str
    severity: Severity
    message: str
    path: Path
    location: Location
    hint: str | None = None

    @property
    def line(self) -> int:
        return self.location.line

    @property
    def column(self) -> int:
        return self.location.column


@dataclass(slots=True)
class SkillDocument:
    """A parsed SKILL.md and the skill directory it belongs to."""

    path: Path
    skill_dir: Path
    raw: str
    frontmatter: dict | None
    frontmatter_raw: str | None
    frontmatter_start_line: int | None
    frontmatter_end_line: int | None
    key_locations: dict[str, Location]
    body: str
    body_start_line: int
    parse_findings: list[Finding] = field(default_factory=list)

    @property
    def name(self) -> str | None:
        if not isinstance(self.frontmatter, dict):
            return None
        value = self.frontmatter.get("name")
        return value if isinstance(value, str) else None


@dataclass(slots=True)
class Report:
    findings: list[Finding]
    skill_count: int
    paths_scanned: list[Path] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.findings if item.severity is Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.findings if item.severity is Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for item in self.findings if item.severity is Severity.INFO)

    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda item: (str(item.path), item.line, item.column, item.rule),
        )
