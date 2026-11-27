"""Parse SKILL.md files, preserving line numbers for findings."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from skill_lint.models import Finding, Location, Severity, SkillDocument

_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:")


def _location(line: int, column: int = 1, end_line: int | None = None, end_column: int | None = None) -> Location:
    return Location(line=line, column=column, end_line=end_line, end_column=end_column)


def _finding(
    rule: str,
    message: str,
    path: Path,
    location: Location,
    hint: str | None = None,
    severity: Severity = Severity.ERROR,
) -> Finding:
    return Finding(
        rule=rule,
        severity=severity,
        message=message,
        path=path,
        location=location,
        hint=hint,
    )


def key_locations(frontmatter_raw: str, start_line: int) -> dict[str, Location]:
    """Map top-level YAML keys to their first source location."""
    locations: dict[str, Location] = {}
    for offset, raw_line in enumerate(frontmatter_raw.splitlines()):
        if raw_line.startswith(" ") or raw_line.startswith("\t"):
            continue
        match = _KEY_RE.match(raw_line)
        if not match:
            continue
        key = match.group(1)
        if key not in locations:
            column = raw_line.find(key) + 1
            locations[key] = _location(
                start_line + offset,
                column,
                start_line + offset,
                column + len(key),
            )
    return locations


def locate_key(doc: SkillDocument, key: str) -> Location:
    """Return the location of a frontmatter key, or the frontmatter block."""
    if key in doc.key_locations:
        return doc.key_locations[key]
    if doc.frontmatter_start_line is not None:
        end = doc.frontmatter_end_line or doc.frontmatter_start_line
        return _location(doc.frontmatter_start_line, 1, end, 1)
    return _location(1)


def parse_skill_markdown(raw: str, path: Path, skill_dir: Path) -> SkillDocument:
    """Parse SKILL.md content into a SkillDocument.

    Parsing problems are recorded as findings rather than raised, so later
    rules can still inspect whatever was recovered.
    """
    findings: list[Finding] = []
    text = raw
    if text.startswith("\ufeff"):
        findings.append(
            _finding(
                "frontmatter-leading-content",
                "SKILL.md starts with a UTF-8 BOM; agents only read frontmatter when '---' is the first line",
                path,
                _location(1),
                hint="Save the file as UTF-8 without a BOM.",
            )
        )
        text = text.lstrip("\ufeff")

    stripped_prefix = text.lstrip(" \t")
    if stripped_prefix != text and stripped_prefix.startswith("---"):
        findings.append(
            _finding(
                "frontmatter-leading-content",
                "SKILL.md has leading whitespace before the opening '---'; many agents will ignore the frontmatter",
                path,
                _location(1),
                hint="Make '---' the very first characters of the file.",
            )
        )

    if text.startswith("\n") or text.startswith("\r\n"):
        findings.append(
            _finding(
                "frontmatter-leading-content",
                "SKILL.md has a blank line before the opening '---'; many agents will ignore the frontmatter",
                path,
                _location(1),
                hint="Make '---' the very first line of the file.",
            )
        )

    lines = text.splitlines()
    first_nonempty = next((index for index, line in enumerate(lines) if line.strip()), None)

    if first_nonempty is None or lines[first_nonempty].strip() != "---":
        body = text
        return SkillDocument(
            path=path,
            skill_dir=skill_dir,
            raw=raw,
            frontmatter=None,
            frontmatter_raw=None,
            frontmatter_start_line=None,
            frontmatter_end_line=None,
            key_locations={},
            body=body,
            body_start_line=1,
            parse_findings=findings
            + [
                _finding(
                    "frontmatter-missing",
                    "SKILL.md must start with YAML frontmatter delimited by '---' lines",
                    path,
                    _location(1),
                    hint=(
                        "Add a frontmatter block at the top, for example:\n"
                        "---\nname: my-skill\ndescription: What it does and when to use it.\n---"
                    ),
                )
            ],
        )

    start_index = first_nonempty
    close_index = None
    for index in range(start_index + 1, len(lines)):
        if lines[index].strip() == "---":
            close_index = index
            break

    if close_index is None:
        return SkillDocument(
            path=path,
            skill_dir=skill_dir,
            raw=raw,
            frontmatter=None,
            frontmatter_raw=None,
            frontmatter_start_line=start_index + 1,
            frontmatter_end_line=None,
            key_locations={},
            body="",
            body_start_line=len(lines) + 1,
            parse_findings=findings
            + [
                _finding(
                    "frontmatter-unclosed",
                    "YAML frontmatter is missing the closing '---' line",
                    path,
                    _location(start_index + 1),
                    hint="Close the frontmatter with a line that contains only '---'.",
                )
            ],
        )

    fm_start_line = start_index + 1
    fm_end_line = close_index + 1
    frontmatter_raw = "\n".join(lines[start_index + 1 : close_index])
    if frontmatter_raw:
        frontmatter_raw += "\n"
    body_lines = lines[close_index + 1 :]
    body = "\n".join(body_lines)
    if raw.endswith("\n") or raw.endswith("\r\n"):
        body += "\n"
    body_start_line = close_index + 2 if body_lines else close_index + 1
    locations = key_locations(frontmatter_raw, fm_start_line + 1)

    try:
        loaded = yaml.safe_load(frontmatter_raw) if frontmatter_raw.strip() else {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = fm_start_line + 1
        column = 1
        if mark is not None:
            line = fm_start_line + 1 + int(mark.line)
            column = int(mark.column) + 1
        problem = str(exc).strip().split("\n")[0]
        findings.append(
            _finding(
                "frontmatter-invalid",
                f"YAML frontmatter could not be parsed: {problem}",
                path,
                _location(line, column),
                hint="Check indentation, colons, and quoting in the frontmatter.",
            )
        )
        return SkillDocument(
            path=path,
            skill_dir=skill_dir,
            raw=raw,
            frontmatter=None,
            frontmatter_raw=frontmatter_raw,
            frontmatter_start_line=fm_start_line,
            frontmatter_end_line=fm_end_line,
            key_locations=locations,
            body=body,
            body_start_line=body_start_line,
            parse_findings=findings,
        )

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        findings.append(
            _finding(
                "frontmatter-not-mapping",
                f"YAML frontmatter must be a mapping of fields, not {type(loaded).__name__}",
                path,
                _location(fm_start_line + 1),
                hint="Use keys such as name: and description: in the frontmatter.",
            )
        )
        loaded = None

    return SkillDocument(
        path=path,
        skill_dir=skill_dir,
        raw=raw,
        frontmatter=loaded,
        frontmatter_raw=frontmatter_raw,
        frontmatter_start_line=fm_start_line,
        frontmatter_end_line=fm_end_line,
        key_locations=locations,
        body=body,
        body_start_line=body_start_line,
        parse_findings=findings,
    )


def parse_skill_file(path: Path, skill_dir: Path | None = None) -> SkillDocument:
    path = path.resolve()
    skill_dir = (skill_dir or path.parent).resolve()
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        doc = SkillDocument(
            path=path,
            skill_dir=skill_dir,
            raw="",
            frontmatter=None,
            frontmatter_raw=None,
            frontmatter_start_line=None,
            frontmatter_end_line=None,
            key_locations={},
            body="",
            body_start_line=1,
            parse_findings=[
                _finding(
                    "frontmatter-invalid",
                    f"SKILL.md is not valid UTF-8: {exc.reason}",
                    path,
                    _location(1),
                    hint="Save the file as UTF-8.",
                )
            ],
        )
        return doc
    return parse_skill_markdown(raw, path, skill_dir)
