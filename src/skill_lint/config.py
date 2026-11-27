"""Configuration loading and rule profiles."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from skill_lint.models import Severity

PROFILES = ("standard", "strict", "spec")
FORMATS = ("text", "json", "github", "sarif")
SEVERITIES = {item.value: item for item in Severity}

# Official Agent Skills specification fields:
# https://agentskills.io/specification
SPEC_FIELDS = frozenset(
    {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "allowed-tools",
    }
)

# Common extensions used by Claude Code and Cursor. These are accepted in the
# standard and strict profiles, and reported as unknown-field under --profile spec.
VENDOR_FIELDS = frozenset(
    {
        "when_to_use",
        "argument-hint",
        "arguments",
        "disable-model-invocation",
        "user-invocable",
        "disallowed-tools",
        "model",
        "paths",
        "icon",
        "color",
        "globs",  # Cursor legacy alias of paths
    }
)

CURSOR_COLORS = frozenset(
    {
        "default",
        "green",
        "cyan",
        "blue",
        "purple",
        "magenta",
        "orange",
        "yellow",
        "red",
        "brand",
    }
)

BOOLEAN_FIELDS = frozenset({"disable-model-invocation", "user-invocable"})
STRING_OR_LIST_FIELDS = frozenset(
    {"allowed-tools", "disallowed-tools", "paths", "globs", "arguments"}
)

KNOWN_FIELDS = SPEC_FIELDS | VENDOR_FIELDS

FIELD_ALIASES = {
    "allowed_tools": "allowed-tools",
    "allowedTools": "allowed-tools",
    "disallowed_tools": "disallowed-tools",
    "disallowedTools": "disallowed-tools",
    "when-to-use": "when_to_use",
    "whenToUse": "when_to_use",
    "argument_hint": "argument-hint",
    "argumentHint": "argument-hint",
    "disable_model_invocation": "disable-model-invocation",
    "disableModelInvocation": "disable-model-invocation",
    "user_invocable": "user-invocable",
    "userInvocable": "user-invocable",
}

CONFIG_FILENAMES = (".skill-lint.toml", "skill-lint.toml")

STRICT_SEVERITY_OVERRIDES = {
    "description-vague": Severity.ERROR,
    "description-no-when": Severity.ERROR,
    "body-too-long": Severity.ERROR,
    "body-too-short": Severity.ERROR,
    "placeholder": Severity.ERROR,
    "unreferenced-script": Severity.ERROR,
    "unknown-field": Severity.ERROR,
    "legacy-globs": Severity.ERROR,
    "allowed-tools-broad": Severity.ERROR,
}


@dataclass
class Config:
    profile: str = "standard"
    format: str = "text"
    strict: bool = False
    quiet: bool = False
    color: bool | None = None
    max_warnings: int | None = None
    ignore: set[str] = field(default_factory=set)
    only: set[str] | None = None
    severity_overrides: dict[str, Severity | None] = field(default_factory=dict)
    min_severity: Severity = Severity.INFO
    description_min_length: int = 40
    body_max_lines: int = 500
    body_min_chars: int = 80

    @property
    def allowed_fields(self) -> frozenset[str]:
        if self.profile == "spec":
            return SPEC_FIELDS
        return KNOWN_FIELDS

    def is_enabled(self, rule_id: str) -> bool:
        if rule_id in self.ignore:
            return False
        return self.only is None or rule_id in self.only

    def severity_for(self, rule_id: str, default: Severity) -> Severity | None:
        """Return the effective severity, or None if the rule is disabled."""
        if not self.is_enabled(rule_id):
            return None
        if rule_id in self.severity_overrides:
            return self.severity_overrides[rule_id]
        if self.profile == "strict" and rule_id in STRICT_SEVERITY_OVERRIDES:
            return STRICT_SEVERITY_OVERRIDES[rule_id]
        if self.profile == "spec" and rule_id == "unknown-field":
            return Severity.ERROR
        return default


def _parse_toml(text: str) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python < 3.11
        import tomli as tomllib  # type: ignore[no-redef]

    return tomllib.loads(text)


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError(f"expected a string or list of strings, got {type(value).__name__}")


def _parse_severity_value(value: Any) -> Severity | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"off", "disable", "disabled"}:
        return None
    if text not in SEVERITIES:
        raise ValueError(f"unknown severity {value!r}; use error, warning, info, or off")
    return SEVERITIES[text]


def apply_mapping(config: Config, data: dict[str, Any]) -> Config:
    """Apply a TOML/JSON-like mapping onto a Config."""
    updates: dict[str, Any] = {}
    if "profile" in data:
        profile = str(data["profile"])
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}; use {', '.join(PROFILES)}")
        updates["profile"] = profile
    if "format" in data:
        fmt = str(data["format"])
        if fmt not in FORMATS:
            raise ValueError(f"unknown format {fmt!r}; use {', '.join(FORMATS)}")
        updates["format"] = fmt
    if "strict" in data:
        updates["strict"] = bool(data["strict"])
    if "quiet" in data:
        updates["quiet"] = bool(data["quiet"])
    if "color" in data:
        updates["color"] = bool(data["color"])
    if "max-warnings" in data or "max_warnings" in data:
        raw = data.get("max-warnings", data.get("max_warnings"))
        updates["max_warnings"] = int(raw)
    if "ignore" in data:
        updates["ignore"] = set(_as_string_list(data["ignore"]))
    if "only" in data and data["only"] is not None:
        updates["only"] = set(_as_string_list(data["only"]))
    if "min-severity" in data or "min_severity" in data:
        raw = data.get("min-severity", data.get("min_severity"))
        severity = _parse_severity_value(raw)
        if severity is None:
            raise ValueError("min-severity cannot be off")
        updates["min_severity"] = severity

    config = replace(config, **updates) if updates else config

    severity_data = data.get("severity") or data.get("severities") or {}
    if severity_data:
        if not isinstance(severity_data, dict):
            raise ValueError("severity must be a table of rule = severity")
        overrides = dict(config.severity_overrides)
        ignore = set(config.ignore)
        for rule_id, raw in severity_data.items():
            parsed = _parse_severity_value(raw)
            if parsed is None:
                ignore.add(str(rule_id))
                overrides.pop(str(rule_id), None)
            else:
                overrides[str(rule_id)] = parsed
        config = replace(config, severity_overrides=overrides, ignore=ignore)

    rules = data.get("rules") or {}
    if "description-vague" in rules and isinstance(rules["description-vague"], dict):
        min_length = rules["description-vague"].get("min-length") or rules["description-vague"].get(
            "min_length"
        )
        if min_length is not None:
            config = replace(config, description_min_length=int(min_length))
    return config


def extract_pyproject_table(data: dict[str, Any]) -> dict[str, Any] | None:
    tool = data.get("tool")
    if isinstance(tool, dict) and isinstance(tool.get("skill-lint"), dict):
        return tool["skill-lint"]
    return None


def load_config_file(path: Path) -> Config:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".toml" or path.name.endswith(".toml"):
        data = _parse_toml(text)
        if path.name == "pyproject.toml":
            table = extract_pyproject_table(data)
            if table is None:
                return Config()
            data = table
    elif suffix in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a mapping")
        data = loaded
    else:
        # Try TOML first, then YAML.
        try:
            data = _parse_toml(text)
        except Exception:
            loaded = yaml.safe_load(text) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"{path} must contain a mapping") from None
            data = loaded
    return apply_mapping(Config(), data)


def find_config(start: Path) -> Path | None:
    start = start.resolve()
    directory = start if start.is_dir() else start.parent
    for current in [directory, *directory.parents]:
        for name in CONFIG_FILENAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        pyproject = current / "pyproject.toml"
        if pyproject.is_file():
            try:
                data = _parse_toml(pyproject.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if extract_pyproject_table(data) is not None:
                return pyproject
    return None


def load_config(explicit: Path | None, start: Path, no_config: bool = False) -> Config:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"config file not found: {explicit}")
        return load_config_file(explicit)
    if no_config:
        return Config()
    found = find_config(start)
    if found is None:
        return Config()
    return load_config_file(found)
