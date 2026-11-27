"""Command-line interface for skill-lint."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from skill_lint import __version__
from skill_lint.config import FORMATS, PROFILES, Config, apply_mapping, load_config
from skill_lint.discover import PathError
from skill_lint.lint import exit_code, lint_paths, lint_text
from skill_lint.report import write_report
from skill_lint.rules import all_rule_docs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-lint",
        description=(
            "Lint Agent Skills (SKILL.md files) for structure, frontmatter, "
            "permission declarations, and common quality problems."
        ),
        epilog="Exit status: 0 clean, 1 lint issues, 2 usage or tool error.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="SKILL.md files, skill directories, or a project root (default: current directory)",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="fmt",
        choices=FORMATS,
        help="output format (text, json, github, sarif)",
    )
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        help="rule profile: standard (default), strict, or spec (open standard fields only)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as errors",
    )
    parser.add_argument(
        "--max-warnings",
        type=int,
        metavar="N",
        help="exit with status 1 if the warning count exceeds N",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="show only errors",
    )
    parser.add_argument(
        "-s",
        "--severity",
        choices=("error", "warning", "info"),
        help="minimum severity to report",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="RULE",
        help="disable a rule (repeatable, or comma-separated)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="RULE",
        help="run only the given rule(s) (repeatable, or comma-separated)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="config file (.skill-lint.toml or pyproject.toml)",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="ignore config files",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read a SKILL.md from standard input",
    )
    parser.add_argument(
        "--stdin-path",
        type=Path,
        default=Path("SKILL.md"),
        help="path to display when using --stdin (default: SKILL.md)",
    )
    parser.add_argument(
        "--skill-dir",
        type=Path,
        help="skill directory used for name and file-reference checks with --stdin",
    )
    color = parser.add_mutually_exclusive_group()
    color.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="force color in text output",
    )
    color.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="disable color in text output",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="list available rules and exit",
    )
    parser.add_argument(
        "--explain",
        metavar="RULE",
        help="explain a rule and exit",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"skill-lint {__version__}",
    )
    return parser


def _split_rule_ids(values: Sequence[str]) -> list[str]:
    rules: list[str] = []
    for value in values:
        for part in value.split(","):
            part = part.strip()
            if part:
                rules.append(part)
    return rules


def _print_rules() -> int:
    docs = all_rule_docs()
    width = max(len(rule.id) for rule in docs)
    for rule in docs:
        print(f"{rule.id.ljust(width)}  {rule.default_severity.value:<7}  {rule.description}")
    return 0


def _print_explain(rule_id: str) -> int:
    docs = {rule.id: rule for rule in all_rule_docs()}
    rule = docs.get(rule_id)
    if rule is None:
        print(f"unknown rule: {rule_id}", file=sys.stderr)
        similar = [item for item in docs if rule_id in item or item in rule_id]
        if similar:
            print("did you mean: " + ", ".join(sorted(similar)), file=sys.stderr)
        return 2
    print(f"{rule.id} ({rule.default_severity.value})")
    print()
    print(rule.description)
    print()
    print(rule.explanation)
    if rule.examples:
        print()
        print("Examples:")
        print(rule.examples)
    return 0


def _merge_cli_config(config: Config, args: argparse.Namespace) -> Config:
    data: dict = {}
    if args.profile:
        data["profile"] = args.profile
    if args.fmt:
        data["format"] = args.fmt
    if args.strict:
        data["strict"] = True
    if args.quiet:
        data["quiet"] = True
    if args.max_warnings is not None:
        data["max-warnings"] = args.max_warnings
    if args.severity:
        data["min-severity"] = args.severity
    if args.color is not None:
        data["color"] = args.color
    if data:
        config = apply_mapping(config, data)
    ignore = set(config.ignore)
    ignore.update(_split_rule_ids(args.ignore))
    only = set(_split_rule_ids(args.only))
    if only:
        existing = set(config.only or [])
        config = apply_mapping(config, {})  # copy via apply? better replace
        from dataclasses import replace

        config = replace(config, ignore=ignore, only=(existing | only) if config.only else only)
    elif ignore != config.ignore:
        from dataclasses import replace

        config = replace(config, ignore=ignore)
    if args.color is not None:
        from dataclasses import replace

        config = replace(config, color=args.color)
    return config


def run(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_rules:
        return _print_rules()
    if args.explain:
        return _print_explain(args.explain)

    paths = list(args.paths) or [Path(".")]
    start = paths[0] if paths else Path(".")
    try:
        config = load_config(args.config, start=start, no_config=args.no_config)
    except FileNotFoundError as exc:
        print(f"skill-lint: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"skill-lint: invalid config: {exc}", file=sys.stderr)
        return 2

    try:
        config = _merge_cli_config(config, args)
    except ValueError as exc:
        print(f"skill-lint: {exc}", file=sys.stderr)
        return 2

    if args.stdin:
        raw = sys.stdin.read()
        display = args.stdin_path
        skill_dir = (args.skill_dir or display.parent).resolve()
        report = lint_text(raw, path=display, skill_dir=skill_dir, config=config)
        write_report(report, config.format, config.color)
        return exit_code(report, config)

    if args.skill_dir and not args.stdin:
        print("skill-lint: --skill-dir is only used with --stdin", file=sys.stderr)
        return 2

    try:
        report = lint_paths(paths, config)
    except PathError as exc:
        print(f"skill-lint: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"skill-lint: {exc}", file=sys.stderr)
        return 2

    write_report(report, config.format, config.color)
    return exit_code(report, config)


def entry() -> None:
    try:
        raise SystemExit(run())
    except BrokenPipeError:  # pragma: no cover - depends on the caller
        sys.stderr.close()
        raise SystemExit(0) from None
    except KeyboardInterrupt:  # pragma: no cover
        print("skill-lint: interrupted", file=sys.stderr)
        raise SystemExit(130) from None


def main(argv: Sequence[str] | None = None) -> int:
    """Library-friendly entry point used by tests."""
    return run(argv)


if __name__ == "__main__":  # pragma: no cover
    entry()
