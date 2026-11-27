"""Lint orchestration."""

from __future__ import annotations

from pathlib import Path

from skill_lint.config import Config
from skill_lint.discover import SkillTarget, discover
from skill_lint.models import Finding, Report, Severity, SkillDocument
from skill_lint.parse import parse_skill_file, parse_skill_markdown
from skill_lint.rules import RULES, LintContext
from skill_lint.rules.base import Rule


def _apply_severity(finding: Finding, config: Config, default: Severity) -> Finding | None:
    severity = config.severity_for(finding.rule, default)
    if severity is None:
        return None
    if finding.severity is severity:
        return finding
    return Finding(
        rule=finding.rule,
        severity=severity,
        message=finding.message,
        path=finding.path,
        location=finding.location,
        hint=finding.hint,
    )


def _rule_default(rule_id: str, rules_by_id: dict[str, Rule], fallback: Severity) -> Severity:
    rule = rules_by_id.get(rule_id)
    if rule is None:
        return fallback
    return rule.default_severity


def lint_document(doc: SkillDocument, ctx: LintContext) -> list[Finding]:
    rules_by_id = {rule.id: rule for rule in RULES}
    findings: list[Finding] = []

    for item in doc.parse_findings:
        default = _rule_default(item.rule, rules_by_id, item.severity)
        applied = _apply_severity(item, ctx.config, default)
        if applied is not None:
            findings.append(applied)

    for rule in RULES:
        if not ctx.config.is_enabled(rule.id):
            continue
        for item in rule.check(doc, ctx):
            default = rule.default_severity if item.rule == rule.id else _rule_default(
                item.rule, rules_by_id, item.severity
            )
            applied = _apply_severity(item, ctx.config, default)
            if applied is not None:
                findings.append(applied)
    return findings


def lint_targets(targets: list[SkillTarget], config: Config) -> Report:
    documents = [parse_skill_file(target.skill_md, target.skill_dir) for target in targets]
    # Preserve a filename casing finding if discover already noticed it, by
    # leaving it to the skill-md-filename rule (it inspects doc.path.name).
    ctx = LintContext(config=config, documents=documents)
    findings: list[Finding] = []
    for doc in documents:
        findings.extend(lint_document(doc, ctx))
    findings = [item for item in findings if item.severity.rank >= config.min_severity.rank]
    if config.quiet:
        findings = [item for item in findings if item.severity is Severity.ERROR]
    return Report(
        findings=findings,
        skill_count=len(documents),
        paths_scanned=[doc.path for doc in documents],
    )


def lint_paths(paths: list[Path], config: Config) -> Report:
    targets = discover(paths)
    return lint_targets(targets, config)


def lint_text(raw: str, path: Path, skill_dir: Path, config: Config) -> Report:
    doc = parse_skill_markdown(raw, path=path, skill_dir=skill_dir)
    ctx = LintContext(config=config, documents=[doc])
    findings = lint_document(doc, ctx)
    findings = [item for item in findings if item.severity.rank >= config.min_severity.rank]
    if config.quiet:
        findings = [item for item in findings if item.severity is Severity.ERROR]
    return Report(findings=findings, skill_count=1, paths_scanned=[path])


def exit_code(report: Report, config: Config) -> int:
    errors = report.error_count
    warnings = report.warning_count
    if config.strict:
        errors += warnings
        warnings = 0
    if errors:
        return 1
    if config.max_warnings is not None and warnings > config.max_warnings:
        return 1
    return 0
