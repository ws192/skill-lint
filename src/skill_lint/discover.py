"""Discover SKILL.md files and skill directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".jj",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "site-packages",
        ".direnv",
        ".cursor-cache",
        ".next",
        "coverage",
        "target",
        ".eggs",
        "egg-info",
    }
)

# Common project locations where agents load skills.
KNOWN_SKILL_ROOTS = (
    Path(".agents") / "skills",
    Path(".cursor") / "skills",
    Path(".claude") / "skills",
    Path(".codex") / "skills",
    Path("skills"),
)

MAX_WALK_DEPTH = 12


@dataclass(frozen=True, slots=True)
class SkillTarget:
    skill_md: Path
    skill_dir: Path
    exact_filename: bool


class PathError(Exception):
    """A user-supplied path could not be used."""


def is_skill_md_name(name: str) -> bool:
    return name.lower() == "skill.md"


def find_skill_md(skill_dir: Path) -> Path | None:
    exact = skill_dir / "SKILL.md"
    if exact.is_file():
        return exact
    try:
        entries = list(skill_dir.iterdir())
    except OSError:
        return None
    matches = [path for path in entries if path.is_file() and is_skill_md_name(path.name)]
    return matches[0] if matches else None


def _should_skip_dir(path: Path) -> bool:
    name = path.name
    return name in SKIP_DIR_NAMES or name.endswith(".egg-info")


def _iter_skill_md_files(root: Path, max_depth: int = MAX_WALK_DEPTH) -> list[Path]:
    found: list[Path] = []

    def walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = list(current.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink():
                # Do not follow symlinks, to avoid cycles and surprises.
                if entry.is_file() and is_skill_md_name(entry.name):
                    found.append(entry)
                continue
            if entry.is_file() and is_skill_md_name(entry.name):
                found.append(entry)
            elif entry.is_dir() and not _should_skip_dir(entry):
                walk(entry, depth + 1)

    walk(root, 0)
    return found


def _target_from_skill_md(path: Path) -> SkillTarget:
    resolved = path.resolve()
    return SkillTarget(
        skill_md=resolved,
        skill_dir=resolved.parent,
        exact_filename=resolved.name == "SKILL.md",
    )


def collect_from_directory(path: Path) -> list[SkillTarget]:
    path = path.resolve()
    targets = [_target_from_skill_md(item) for item in _iter_skill_md_files(path)]
    # Prefer exact SKILL.md over a same-directory case variant if both exist.
    by_dir: dict[Path, SkillTarget] = {}
    for target in targets:
        existing = by_dir.get(target.skill_dir)
        if existing is None or (target.exact_filename and not existing.exact_filename):
            by_dir[target.skill_dir] = target
    return sorted(by_dir.values(), key=lambda item: str(item.skill_md))


def discover(paths: list[Path]) -> list[SkillTarget]:
    """Resolve user paths into unique skill targets.

    Raises PathError if a supplied path does not exist.
    """
    collected: list[SkillTarget] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise PathError(f"path does not exist: {path}")
        if path.is_file():
            target = _target_from_skill_md(path)
            if target.skill_md not in seen:
                collected.append(target)
                seen.add(target.skill_md)
            continue
        if not path.is_dir():
            raise PathError(f"not a file or directory: {path}")
        for target in collect_from_directory(path):
            if target.skill_md not in seen:
                collected.append(target)
                seen.add(target.skill_md)
    return collected
