"""Render lint findings."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from skill_lint.models import Finding, Report, Severity

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
DIM = "\033[2m"

SEVERITY_COLOR = {
    Severity.ERROR: RED,
    Severity.WARNING: YELLOW,
    Severity.INFO: CYAN,
}


def use_color(stream, requested: bool | None) -> bool:
    if requested is False:
        return False
    if requested is True:
        return True
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


def _c(enabled: bool, code: str, text: str) -> str:
    if not enabled:
        return text
    return f"{code}{text}{RESET}"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def format_text(report: Report, color: bool = False) -> str:
    if not report.findings and report.skill_count == 0:
        return "No skills found.\n"
    if not report.findings:
        noun = "skill" if report.skill_count == 1 else "skills"
        return _c(color, BLUE, "ok") + f"  {report.skill_count} {noun}, no issues\n"

    grouped: dict[str, list[Finding]] = {}
    for item in report.sorted_findings():
        grouped.setdefault(_rel(item.path), []).append(item)

    lines: list[str] = []
    for file_path, items in grouped.items():
        lines.append(_c(color, BOLD, file_path))
        for item in items:
            sev = _c(color, SEVERITY_COLOR[item.severity], f"{item.severity.value:<7}")
            rule = _c(color, DIM, item.rule)
            lines.append(f"  {item.line:>4}:{item.column:<3}  {sev}  {rule}  {item.message}")
            if item.hint:
                for hint_line in item.hint.splitlines():
                    lines.append(_c(color, DIM, f"              {hint_line}"))
        lines.append("")

    errors, warnings, infos = report.error_count, report.warning_count, report.info_count
    parts = []
    if errors:
        parts.append(_c(color, RED, f"{errors} error" + ("s" if errors != 1 else "")))
    if warnings:
        parts.append(_c(color, YELLOW, f"{warnings} warning" + ("s" if warnings != 1 else "")))
    if infos:
        parts.append(_c(color, CYAN, f"{infos} info"))
    noun = "skill" if report.skill_count == 1 else "skills"
    summary = ", ".join(parts) + f" in {report.skill_count} {noun}"
    glyph = _c(color, RED, "x") if errors else _c(color, YELLOW, "!")
    lines.append(f"{glyph}  {summary}")
    return "\n".join(lines) + "\n"


def _finding_dict(item: Finding) -> dict:
    payload = {
        "file": _rel(item.path),
        "line": item.line,
        "column": item.column,
        "endLine": item.location.end_line,
        "endColumn": item.location.end_column,
        "severity": item.severity.value,
        "rule": item.rule,
        "message": item.message,
        "hint": item.hint,
    }
    return payload


def format_json(report: Report) -> str:
    payload = {
        "skillCount": report.skill_count,
        "errorCount": report.error_count,
        "warningCount": report.warning_count,
        "infoCount": report.info_count,
        "findings": [_finding_dict(item) for item in report.sorted_findings()],
    }
    return json.dumps(payload, indent=2) + "\n"


def _github_severity(severity: Severity) -> str:
    if severity is Severity.ERROR:
        return "error"
    if severity is Severity.WARNING:
        return "warning"
    return "notice"


def format_github(report: Report) -> str:
    lines: list[str] = []
    for item in report.sorted_findings():
        bits = [
            f"file={_rel(item.path)}",
            f"line={item.line}",
            f"col={item.column}",
        ]
        if item.location.end_line is not None:
            bits.append(f"endLine={item.location.end_line}")
        if item.location.end_column is not None:
            bits.append(f"endColumn={item.location.end_column}")
        bits.append(f"title={item.rule}")
        message = item.message
        if item.hint:
            message = f"{message} ({item.hint})"
        # GitHub annotations must stay on one line.
        message = message.replace("\n", " ")
        lines.append(f"::{_github_severity(item.severity)} {','.join(bits)}::{message}")
    if report.findings:
        lines.append(
            f"::notice ::skill-lint found {report.error_count} error(s), "
            f"{report.warning_count} warning(s) in {report.skill_count} skill(s)"
        )
    elif report.skill_count:
        lines.append(f"::notice ::skill-lint found no issues in {report.skill_count} skill(s)")
    else:
        lines.append("::notice ::skill-lint found no skills")
    return "\n".join(lines) + "\n"


def format_sarif(report: Report) -> str:
    rules_seen: dict[str, dict] = {}
    results = []
    for item in report.sorted_findings():
        if item.rule not in rules_seen:
            rules_seen[item.rule] = {
                "id": item.rule,
                "shortDescription": {"text": item.rule},
                "fullDescription": {"text": item.message},
                "helpUri": f"https://github.com/ws192/skill-lint#rule-{item.rule}",
            }
        region = {
            "startLine": max(item.line, 1),
            "startColumn": max(item.column, 1),
        }
        if item.location.end_line is not None:
            region["endLine"] = item.location.end_line
        if item.location.end_column is not None:
            region["endColumn"] = item.location.end_column
        level = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "note"}[
            item.severity
        ]
        results.append(
            {
                "ruleId": item.rule,
                "level": level,
                "message": {"text": item.message + (f" {item.hint}" if item.hint else "")},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": _rel(item.path)},
                            "region": region,
                        }
                    }
                ],
            }
        )
    payload = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "skill-lint",
                        "informationUri": "https://github.com/ws192/skill-lint",
                        "rules": list(rules_seen.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def render(report: Report, fmt: str, color: bool = False) -> str:
    if fmt == "json":
        return format_json(report)
    if fmt == "github":
        return format_github(report)
    if fmt == "sarif":
        return format_sarif(report)
    return format_text(report, color=color)


def write_report(report: Report, fmt: str, color: bool | None, stream=None) -> None:
    stream = stream or sys.stdout
    enabled = use_color(stream, color) if fmt == "text" else False
    stream.write(render(report, fmt, color=enabled))
