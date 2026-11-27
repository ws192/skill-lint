"""Checks for file references, bundled resources, and path quality."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from skill_lint.models import Finding, Severity, SkillDocument
from skill_lint.rules.base import LintContext, body_location, finding, loc

# Match [text](url) and ![alt](url), including optional angle brackets around the url.
MD_LINK_RE = re.compile(
    r"!?\[(?:[^\]]|\\\])*\]\(\s*<?(?P<url>[^>\s)][^>\)]*?)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)

# Backtick or bare references to bundled resources, and explicit relative paths.
BUNDLE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])(?P<path>(?:\./)?(?:scripts|references|assets)/[A-Za-z0-9_./@+-]+)"
)

ABSOLUTE_POSIX_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<path>/(?:usr|home|Users|tmp|var|opt|etc|root)/[A-Za-z0-9_./+-]+)"
)
ABSOLUTE_WINDOWS_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<path>[A-Za-z]:\\[^\s`\"')]+)"
)
WINDOWS_BUNDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<path>(?:scripts|references|assets)\\[A-Za-z0-9_.\\@+-]+)"
)

URL_SCHEMES = {"http", "https", "mailto", "data", "ftp"}
RESOURCE_DIRS = ("scripts", "references", "assets")


def _line_col(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    column = index - last_nl
    return line, column


def _is_external(url: str) -> bool:
    stripped = url.strip()
    if not stripped or stripped.startswith("#"):
        return True
    parsed = urlparse(stripped)
    if parsed.scheme.lower() in URL_SCHEMES:
        return True
    return stripped.startswith("//")


def _clean_url(url: str) -> str:
    text = unquote(url.strip())
    if " " in text:
        text = text.split()[0]
    return text


def _local_target(url: str) -> str | None:
    if _is_external(url):
        return None
    cleaned = _clean_url(url)
    # Drop fragment / query
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0]
    if not cleaned:
        return None
    return cleaned


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_in_skill(skill_dir: Path, relative: str, source_file: Path | None = None) -> Path | None:
    """Resolve a local path against the linking file, then the skill root."""
    # Disallow absolute paths here; those are reported separately.
    if relative.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", relative):
        return None
    normalized = relative.replace("\\", "/")
    candidates: list[Path] = []
    if source_file is not None:
        candidates.append((source_file.parent / normalized).resolve())
    candidates.append((skill_dir / normalized).resolve())
    for candidate in candidates:
        if candidate.exists() and _is_inside(candidate, skill_dir):
            return candidate
    return candidates[-1]


def _iter_markdown_files(doc: SkillDocument) -> list[tuple[Path, str, int]]:
    """Return (path, text, start_line) for SKILL.md and bundled markdown files."""
    items = [(doc.path, doc.body, doc.body_start_line)]
    for folder in ("references", "assets", "scripts"):
        root = doc.skill_dir / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".markdown"}:
                try:
                    items.append((path, path.read_text(encoding="utf-8"), 1))
                except OSError:
                    continue
    return items


class BrokenReference:
    id = "broken-reference"
    description = "Relative file references in the skill should point to files that exist."
    default_severity = Severity.ERROR
    explanation = (
        "Skills should reference bundled files with paths relative to the skill "
        "root, such as references/guide.md or scripts/extract.py. A broken path "
        "means the agent cannot load the resource when it follows the instructions."
    )
    examples = (
        "Bad: See [the guide](references/missing.md)\n"
        "Good: See [the guide](references/guide.md) and keep that file in the skill"
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[tuple[Path, int, str]] = set()
        for path, text, start_line in _iter_markdown_files(doc):
            for match in MD_LINK_RE.finditer(text):
                target = _local_target(match.group("url"))
                if target is None:
                    continue
                resolved = _resolve_in_skill(doc.skill_dir, target, path)
                if resolved is not None and resolved.exists():
                    continue
                line, column = _line_col(text, match.start("url"))
                line = start_line + line - 1
                key = (path, line, target)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    finding(
                        self.id,
                        f"referenced file {target!r} does not exist",
                        path,
                        loc(line, column),
                        Severity.ERROR,
                        hint="Fix the path, or add the file relative to the skill directory.",
                    )
                )
            for match in BUNDLE_PATH_RE.finditer(text):
                target = match.group("path")
                # Skip if this occurrence is already inside a markdown link url
                # that we handled above. Still worth checking existence.
                resolved = _resolve_in_skill(doc.skill_dir, target, path)
                if resolved is not None and resolved.exists():
                    continue
                line, column = _line_col(text, match.start("path"))
                line = start_line + line - 1
                key = (path, line, target)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    finding(
                        self.id,
                        f"referenced file {target!r} does not exist",
                        path,
                        loc(line, column),
                        Severity.ERROR,
                        hint="Fix the path, or add the file relative to the skill directory.",
                    )
                )
        return findings


class AbsolutePath:
    id = "absolute-path"
    description = "Reference skill files with paths relative to the skill root, not absolute paths."
    default_severity = Severity.WARNING
    explanation = (
        "The Agent Skills specification says to use relative paths from the skill "
        "root. Absolute machine paths will not work for anyone else, or for the "
        "same person on another computer."
    )
    examples = "Bad: /Users/you/skills/pdf/scripts/run.py\nGood: scripts/run.py"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        findings: list[Finding] = []
        text = doc.body
        for regex in (ABSOLUTE_POSIX_RE, ABSOLUTE_WINDOWS_RE):
            for match in regex.finditer(text):
                path_text = match.group("path")
                line, column = _line_col(text, match.start("path"))
                findings.append(
                    finding(
                        self.id,
                        f"instruction uses absolute path {path_text!r}",
                        doc.path,
                        body_location(doc, line, column),
                        Severity.WARNING,
                        hint="Use a path relative to the skill directory, such as scripts/run.py.",
                    )
                )
        return findings


class WindowsPath:
    id = "windows-path"
    description = "Use forward slashes in skill file paths."
    default_severity = Severity.WARNING
    explanation = (
        "Anthropic's skill authoring checklist asks authors to avoid Windows-style "
        "backslashes in paths so the same skill works on every platform."
    )
    examples = r"Bad: scripts\extract.py" + "\nGood: scripts/extract.py"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        findings: list[Finding] = []
        text = doc.body
        for match in WINDOWS_BUNDLE_RE.finditer(text):
            path_text = match.group("path")
            line, column = _line_col(text, match.start("path"))
            findings.append(
                finding(
                    self.id,
                    f"path {path_text!r} uses Windows backslashes",
                    doc.path,
                    body_location(doc, line, column),
                    Severity.WARNING,
                    hint="Replace backslashes with forward slashes: " + path_text.replace("\\", "/") + ".",
                )
            )
        return findings


def _referenced_paths(doc: SkillDocument) -> set[str]:
    """Return skill-relative POSIX paths mentioned in SKILL.md (and other md)."""
    mentioned: set[str] = set()
    text = doc.body
    # Also consider frontmatter license and compatibility, which may name files.
    if isinstance(doc.frontmatter, dict):
        for key in ("license", "compatibility"):
            value = doc.frontmatter.get(key)
            if isinstance(value, str):
                text = text + "\n" + value
    for match in MD_LINK_RE.finditer(text):
        target = _local_target(match.group("url"))
        if target:
            mentioned.add(target.replace("\\", "/").lstrip("./"))
    for match in BUNDLE_PATH_RE.finditer(text):
        mentioned.add(match.group("path").replace("\\", "/").lstrip("./"))
    # Also accept basename mentions in backticks: `extract.py`
    for match in re.finditer(r"`([^`]+)`", text):
        mentioned.add(match.group(1).replace("\\", "/").lstrip("./"))
    return mentioned


def _is_mentioned(relative: str, mentioned: set[str]) -> bool:
    posix = relative.replace("\\", "/")
    name = Path(posix).name
    candidates = {posix, posix.lstrip("./"), name, f"./{posix}"}
    return any(item in mentioned for item in candidates)


class UnreferencedScript:
    id = "unreferenced-script"
    description = "Scripts bundled in scripts/ should be mentioned in SKILL.md."
    default_severity = Severity.WARNING
    explanation = (
        "Agents only learn about bundled scripts from the skill instructions. If a "
        "script is never named, it is unlikely to be used. List available scripts "
        "and show how to run them with a path relative to the skill root."
    )
    examples = "Good: Run `python scripts/extract.py \"$INPUT\"`"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        scripts_dir = doc.skill_dir / "scripts"
        if not scripts_dir.is_dir():
            return []
        mentioned = _referenced_paths(doc)
        findings: list[Finding] = []
        try:
            files = [path for path in scripts_dir.rglob("*") if path.is_file()]
        except OSError:
            return []
        # Ignore obvious non-scripts.
        skip_names = {".ds_store", "thumbs.db"}
        for path in sorted(files):
            if path.name.lower() in skip_names or path.name.startswith("."):
                continue
            relative = path.relative_to(doc.skill_dir).as_posix()
            if _is_mentioned(relative, mentioned):
                continue
            findings.append(
                finding(
                    self.id,
                    f"bundled script {relative!r} is never mentioned in SKILL.md",
                    doc.path,
                    loc(1),
                    Severity.WARNING,
                    hint=f"List {relative} in the instructions and show the command used to run it.",
                )
            )
        return findings


class UnreferencedReference:
    id = "unreferenced-reference"
    description = "Files in references/ should be linked from SKILL.md."
    default_severity = Severity.WARNING
    explanation = (
        "Reference files are loaded on demand. If SKILL.md never points to them, "
        "the agent will not know they exist."
    )
    examples = "Good: See [the format notes](references/format.md) for field details."

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        refs_dir = doc.skill_dir / "references"
        if not refs_dir.is_dir():
            return []
        mentioned = _referenced_paths(doc)
        findings: list[Finding] = []
        try:
            files = [path for path in refs_dir.rglob("*") if path.is_file()]
        except OSError:
            return []
        for path in sorted(files):
            if path.name.startswith("."):
                continue
            relative = path.relative_to(doc.skill_dir).as_posix()
            if _is_mentioned(relative, mentioned):
                continue
            findings.append(
                finding(
                    self.id,
                    f"reference file {relative!r} is never mentioned in SKILL.md",
                    doc.path,
                    loc(1),
                    Severity.WARNING,
                    hint=f"Link to {relative} from the instructions so the agent can load it when needed.",
                )
            )
        return findings


class EmptyResourceDir:
    id = "empty-resource-dir"
    description = "Do not leave empty scripts/, references/, or assets/ directories."
    default_severity = Severity.WARNING
    explanation = (
        "An empty resource directory looks like an unfinished skill and can confuse "
        "authors and agents. Remove it, or add the files the instructions expect."
    )
    examples = "Bad: an empty scripts/ folder\nGood: omit the folder, or put a real script in it"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        findings: list[Finding] = []
        for name in RESOURCE_DIRS:
            folder = doc.skill_dir / name
            if not folder.is_dir():
                continue
            try:
                entries = [path for path in folder.rglob("*") if path.is_file() and not path.name.startswith(".")]
            except OSError:
                continue
            if entries:
                continue
            findings.append(
                finding(
                    self.id,
                    f"{name}/ exists but contains no files",
                    doc.path,
                    loc(1),
                    Severity.WARNING,
                    hint=f"Add files under {name}/ or remove the empty directory.",
                )
            )
        return findings


class NestedReference:
    id = "nested-reference"
    description = "Keep file references one level deep from SKILL.md."
    default_severity = Severity.WARNING
    explanation = (
        "The Agent Skills specification recommends keeping file references one "
        "level deep from SKILL.md. If a referenced Markdown file itself points at "
        "another local file, the agent may never follow that chain."
    )
    examples = (
        "Bad: SKILL.md -> references/a.md -> references/b.md\n"
        "Good: SKILL.md links to both references/a.md and references/b.md"
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        findings: list[Finding] = []
        # Files linked directly from SKILL.md
        direct: list[Path] = []
        for match in MD_LINK_RE.finditer(doc.body):
            target = _local_target(match.group("url"))
            if not target:
                continue
            resolved = _resolve_in_skill(doc.skill_dir, target, doc.path)
            if (
                resolved is not None
                and resolved.is_file()
                and resolved.suffix.lower() in {".md", ".markdown"}
                and resolved.resolve() != doc.path.resolve()
            ):
                direct.append(resolved)
        for match in BUNDLE_PATH_RE.finditer(doc.body):
            resolved = _resolve_in_skill(doc.skill_dir, match.group("path"), doc.path)
            if (
                resolved is not None
                and resolved.is_file()
                and resolved.suffix.lower() in {".md", ".markdown"}
                and resolved.resolve() != doc.path.resolve()
            ):
                direct.append(resolved)

        seen_files: set[Path] = set()
        for path in direct:
            resolved = path.resolve()
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in MD_LINK_RE.finditer(text):
                target = _local_target(match.group("url"))
                if not target:
                    continue
                nested = _resolve_in_skill(doc.skill_dir, target, path)
                if nested is None or not nested.exists():
                    continue
                if nested.resolve() in {doc.path.resolve(), resolved}:
                    continue
                line, column = _line_col(text, match.start("url"))
                if path.is_relative_to(doc.skill_dir):
                    relative = path.relative_to(doc.skill_dir).as_posix()
                else:
                    relative = str(path)
                findings.append(
                    finding(
                        self.id,
                        f"{relative} links to {target}, which is a second-level reference from SKILL.md",
                        path,
                        loc(line, column),
                        Severity.WARNING,
                        hint="Link to that file directly from SKILL.md as well, and keep the chain one level deep.",
                    )
                )
        return findings
