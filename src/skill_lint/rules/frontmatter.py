"""Frontmatter field rules based on the Agent Skills spec and vendor extensions."""

from __future__ import annotations

import re
import unicodedata
from difflib import get_close_matches
from typing import Any

from skill_lint.config import (
    BOOLEAN_FIELDS,
    CURSOR_COLORS,
    FIELD_ALIASES,
    SPEC_FIELDS,
    VENDOR_FIELDS,
)
from skill_lint.models import Finding, Severity, SkillDocument
from skill_lint.parse import locate_key
from skill_lint.rules.base import LintContext, finding

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
RESERVED_NAME_TOKENS = ("anthropic", "claude")
XML_RE = re.compile(r"<[^>]+>")
WHEN_TO_USE_RE = re.compile(
    r"\b("
    r"use when|used when|useful when|needed when|applies when|"
    r"when to use|when the user|when a user|when users|"
    r"when working|when handling|when asked|when dealing|"
    r"when you|when an? agent|when claude|when cursor|when codex|"
    r"if the user|if you need|if asked|"
    r"trigger"
    r")\b",
    re.IGNORECASE,
)
VAGUE_DESCRIPTION_RE = re.compile(
    r"^\s*(this\s+)?(skill|helper|utility|tool)?\s*"
    r"(helps? with|for|does|is used for)?\s*[\w./-]*\.?\s*$",
    re.IGNORECASE,
)


def _value_location(doc: SkillDocument, key: str) -> Any:
    return locate_key(doc, key)


class NameMissing:
    id = "name-missing"
    description = "Frontmatter must include a name field."
    default_severity = Severity.ERROR
    explanation = (
        "The Agent Skills specification requires name. Agents use it as the skill "
        "identifier and it must match the skill directory name."
    )
    examples = "Good:\n---\nname: pdf-processing\ndescription: ...\n---"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None:
            return []
        if "name" in doc.frontmatter:
            return []
        return [
            finding(
                self.id,
                "missing required frontmatter field 'name'",
                doc.path,
                locate_key(doc, "name"),
                Severity.ERROR,
                hint="Add a name field: lowercase letters, digits, and hyphens, matching the directory name.",
            )
        ]


class NameType:
    id = "name-type"
    description = "name must be a string."
    default_severity = Severity.ERROR
    explanation = "The name field must be a YAML string, not a number, boolean, or list."
    examples = "Bad: name: true\nGood: name: pdf-processing"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "name" not in doc.frontmatter:
            return []
        value = doc.frontmatter["name"]
        if isinstance(value, str):
            return []
        return [
            finding(
                self.id,
                f"name must be a string, not {type(value).__name__}",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint="Quote the name if YAML is treating it as another type, for example name: \"true\".",
            )
        ]


def _normalized_name(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip())


class NameEmpty:
    id = "name-empty"
    description = "name must be a non-empty string."
    default_severity = Severity.ERROR
    explanation = "An empty or whitespace-only name is not a valid skill identifier."
    examples = "Bad: name: ''\nGood: name: pdf-processing"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        if _normalized_name(doc.frontmatter["name"]):
            return []
        return [
            finding(
                self.id,
                "name must be a non-empty string",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint="Set name to a hyphen-case identifier that matches the skill directory.",
            )
        ]


class NameLength:
    id = "name-length"
    description = "name must be at most 64 characters."
    default_severity = Severity.ERROR
    explanation = "The Agent Skills specification limits name to 64 characters."
    examples = "Bad: a 70-character name\nGood: a short hyphen-case identifier"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        name = _normalized_name(doc.frontmatter["name"])
        if not name or len(name) <= MAX_NAME_LENGTH:
            return []
        return [
            finding(
                self.id,
                f"name is {len(name)} characters; the maximum is {MAX_NAME_LENGTH}",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint="Shorten the name. The directory name must use the same shortened value.",
            )
        ]


class NameCase:
    id = "name-case"
    description = "name must be lowercase."
    default_severity = Severity.ERROR
    explanation = "Skill names must be lowercase so they are stable identifiers across systems."
    examples = "Bad: name: PDF-Processing\nGood: name: pdf-processing"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        name = _normalized_name(doc.frontmatter["name"])
        if not name or name == name.lower():
            return []
        return [
            finding(
                self.id,
                f"name {name!r} must be lowercase",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint=f"Use {name.lower()!r} and rename the directory to match.",
            )
        ]


class NameCharset:
    id = "name-charset"
    description = "name may only contain lowercase letters, digits, and hyphens."
    default_severity = Severity.ERROR
    explanation = (
        "The Agent Skills specification allows unicode lowercase alphanumeric "
        "characters and hyphens only. Spaces, underscores, and punctuation are rejected."
    )
    examples = "Bad: name: pdf_processing\nGood: name: pdf-processing"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        name = _normalized_name(doc.frontmatter["name"])
        if not name:
            return []
        invalid = sorted({ch for ch in name if not (ch.isalnum() or ch == "-")})
        if not invalid:
            return []
        shown = ", ".join(repr(ch) for ch in invalid)
        return [
            finding(
                self.id,
                f"name {name!r} contains invalid characters: {shown}",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint="Use only letters, digits, and hyphens. Replace underscores or spaces with a single hyphen.",
            )
        ]


class NameHyphen:
    id = "name-hyphen"
    description = "name must not start or end with a hyphen, or contain consecutive hyphens."
    default_severity = Severity.ERROR
    explanation = (
        "Leading, trailing, or doubled hyphens are rejected by the Agent Skills "
        "specification and by common skill validators."
    )
    examples = "Bad: name: -pdf--tools-\nGood: name: pdf-tools"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        name = _normalized_name(doc.frontmatter["name"])
        if not name:
            return []
        problems = []
        if name.startswith("-") or name.endswith("-"):
            problems.append("start or end with a hyphen")
        if "--" in name:
            problems.append("contain consecutive hyphens")
        if not problems:
            return []
        return [
            finding(
                self.id,
                f"name {name!r} must not {' or '.join(problems)}",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint="Use a single hyphen between words, with no hyphen at either end.",
            )
        ]


class NameMismatch:
    id = "name-mismatch"
    description = "name must match the parent directory name."
    default_severity = Severity.ERROR
    explanation = (
        "The skill directory is the package. The Agent Skills specification requires "
        "the name field to match that directory so agents can resolve the skill reliably."
    )
    examples = "Bad: pdf-tools/SKILL.md with name: invoices\nGood: pdf-tools/SKILL.md with name: pdf-tools"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        name = _normalized_name(doc.frontmatter["name"])
        if not name:
            return []
        dir_name = unicodedata.normalize("NFKC", doc.skill_dir.name)
        if dir_name == name:
            return []
        return [
            finding(
                self.id,
                f"name {name!r} does not match directory {dir_name!r}",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint=f"Rename the directory to {name!r}, or set name to {dir_name!r}.",
            )
        ]


class NameReserved:
    id = "name-reserved"
    description = "name must not contain reserved words such as anthropic or claude."
    default_severity = Severity.ERROR
    explanation = (
        "Anthropic's skill authoring rules reserve words such as 'anthropic' and "
        "'claude' in skill names. Using them can cause the skill to be rejected."
    )
    examples = "Bad: name: claude-review\nGood: name: pr-review"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        name = _normalized_name(doc.frontmatter["name"]).lower()
        if not name:
            return []
        tokens = set(name.split("-"))
        hit = [word for word in RESERVED_NAME_TOKENS if word in tokens or word == name]
        if not hit:
            return []
        return [
            finding(
                self.id,
                f"name {doc.frontmatter['name']!r} contains reserved word {hit[0]!r}",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint="Choose a name that does not include 'anthropic' or 'claude'.",
            )
        ]


class NameXml:
    id = "name-xml"
    description = "name must not contain XML tags or angle brackets."
    default_severity = Severity.ERROR
    explanation = (
        "Angle brackets in name are treated as XML by some hosts and can break "
        "skill loading. This is also forbidden by Anthropic's authoring rules."
    )
    examples = "Bad: name: pdf<tool>\nGood: name: pdf-tool"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("name"), str):
            return []
        name = doc.frontmatter["name"]
        if "<" not in name and ">" not in name:
            return []
        return [
            finding(
                self.id,
                "name contains angle brackets, which some hosts treat as XML",
                doc.path,
                _value_location(doc, "name"),
                Severity.ERROR,
                hint="Remove '<' and '>' from the name.",
            )
        ]


class DescriptionMissing:
    id = "description-missing"
    description = "Frontmatter must include a description field."
    default_severity = Severity.ERROR
    explanation = (
        "description is required by the Agent Skills specification. Agents load "
        "name and description for every installed skill and use the description to "
        "decide when the skill applies. If it is missing, the skill is unlikely to be selected."
    )
    examples = (
        "Good: description: Extract text and tables from PDF files. "
        "Use when working with PDFs or form filling."
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None:
            return []
        if "description" in doc.frontmatter:
            return []
        return [
            finding(
                self.id,
                "missing required frontmatter field 'description'",
                doc.path,
                locate_key(doc, "description"),
                Severity.ERROR,
                hint="Add a description that says what the skill does and when to use it.",
            )
        ]


class DescriptionType:
    id = "description-type"
    description = "description must be a string."
    default_severity = Severity.ERROR
    explanation = "description must be a YAML string, not a list or mapping."
    examples = "Bad: description: [pdf, forms]\nGood: description: Extract text from PDFs. Use when..."

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "description" not in doc.frontmatter:
            return []
        value = doc.frontmatter["description"]
        if isinstance(value, str):
            return []
        return [
            finding(
                self.id,
                f"description must be a string, not {type(value).__name__}",
                doc.path,
                _value_location(doc, "description"),
                Severity.ERROR,
                hint="Write the description as a single YAML string. Use quotes if it contains colons.",
            )
        ]


class DescriptionEmpty:
    id = "description-empty"
    description = "description must be a non-empty string."
    default_severity = Severity.ERROR
    explanation = "An empty description cannot tell an agent when to apply the skill."
    examples = "Bad: description: ''\nGood: a one or two sentence description with triggers"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("description"), str):
            return []
        if doc.frontmatter["description"].strip():
            return []
        return [
            finding(
                self.id,
                "description must be a non-empty string",
                doc.path,
                _value_location(doc, "description"),
                Severity.ERROR,
                hint="Describe what the skill does and when an agent should use it.",
            )
        ]


class DescriptionLength:
    id = "description-length"
    description = "description must be at most 1024 characters."
    default_severity = Severity.ERROR
    explanation = (
        "The Agent Skills specification limits description to 1024 characters. "
        "Claude Code also truncates combined description and when_to_use text in listings."
    )
    examples = "Bad: a 2000-character essay in description\nGood: a concise paragraph with triggers"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("description"), str):
            return []
        text = doc.frontmatter["description"]
        if len(text) <= MAX_DESCRIPTION_LENGTH:
            return []
        return [
            finding(
                self.id,
                f"description is {len(text)} characters; the maximum is {MAX_DESCRIPTION_LENGTH}",
                doc.path,
                _value_location(doc, "description"),
                Severity.ERROR,
                hint="Shorten the description. Put extra guidance in the Markdown body or in when_to_use.",
            )
        ]


class DescriptionXml:
    id = "description-xml"
    description = "description must not contain XML tags or angle brackets."
    default_severity = Severity.ERROR
    explanation = (
        "Claude and Codex skill validators reject angle brackets in description "
        "because they are treated as XML. Avoid < and > even in examples."
    )
    examples = (
        "Bad: description: Use when the user mentions <file> paths.\n"
        "Good: Use when the user mentions file paths."
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("description"), str):
            return []
        text = doc.frontmatter["description"]
        if "<" not in text and ">" not in text:
            return []
        tags = [match.group(0) for match in XML_RE.finditer(text)]
        detail = (
            "tag-like text " + ", ".join(repr(tag) for tag in tags[:3])
            if tags
            else "angle brackets"
        )
        return [
            finding(
                self.id,
                f"description contains {detail}, which Claude and Codex reject",
                doc.path,
                _value_location(doc, "description"),
                Severity.ERROR,
                hint="Remove '<' and '>' from the description. Spell out names instead of writing them as tags.",
            )
        ]


class DescriptionVague:
    id = "description-vague"
    description = "description should be specific, not a short generic phrase."
    default_severity = Severity.WARNING
    explanation = (
        "Agents choose skills from the description alone. A phrase such as "
        "'Helps with PDFs.' does not give enough signal. The specification asks "
        "for what the skill does, when to use it, and useful keywords."
    )
    examples = (
        "Bad: description: Helps with PDFs.\n"
        "Good: description: Extract text and tables from PDF files, fill forms, "
        "and merge documents. Use when working with PDFs or form filling."
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("description"), str):
            return []
        text = " ".join(doc.frontmatter["description"].split())
        if not text:
            return []
        too_short = len(text) < ctx.config.description_min_length
        vague = bool(VAGUE_DESCRIPTION_RE.match(text)) and len(text) < 80
        if not too_short and not vague:
            return []
        if too_short:
            message = (
                f"description is only {len(text)} characters; write a specific summary "
                f"of at least {ctx.config.description_min_length} characters"
            )
        else:
            message = f"description {text!r} is too generic to help an agent decide when to use this skill"
        return [
            finding(
                self.id,
                message,
                doc.path,
                _value_location(doc, "description"),
                Severity.WARNING,
                hint="Say what the skill does, when to use it, and include concrete keywords.",
            )
        ]


class DescriptionNoWhen:
    id = "description-no-when"
    description = "description should say when the skill should be used."
    default_severity = Severity.WARNING
    explanation = (
        "Only the description (and, in Claude Code, when_to_use) is available when "
        "an agent decides whether to activate a skill. Trigger phrases belong there, "
        "not only in a 'When to use' section of the body, which is loaded later."
    )
    examples = (
        "Bad: description: Extracts text from PDF files.\n"
        "Good: description: Extracts text from PDF files. Use when the user mentions PDFs or form filling."
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or not isinstance(doc.frontmatter.get("description"), str):
            return []
        text = doc.frontmatter["description"]
        if not text.strip():
            return []
        when_to_use = doc.frontmatter.get("when_to_use")
        if isinstance(when_to_use, str) and when_to_use.strip():
            return []
        if WHEN_TO_USE_RE.search(text):
            return []
        return [
            finding(
                self.id,
                "description does not say when to use this skill",
                doc.path,
                _value_location(doc, "description"),
                Severity.WARNING,
                hint="Add a trigger clause such as 'Use when the user asks to ...' or set when_to_use (Claude Code).",
            )
        ]


class CompatibilityType:
    id = "compatibility-type"
    description = "compatibility must be a string of at most 500 characters."
    default_severity = Severity.ERROR
    explanation = (
        "compatibility is an optional Agent Skills field describing environment "
        "requirements. It must be a string of at most 500 characters."
    )
    examples = "Good: compatibility: Requires Python 3.10+ and ffmpeg"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "compatibility" not in doc.frontmatter:
            return []
        value = doc.frontmatter["compatibility"]
        if not isinstance(value, str):
            return [
                finding(
                    self.id,
                    f"compatibility must be a string, not {type(value).__name__}",
                    doc.path,
                    _value_location(doc, "compatibility"),
                    Severity.ERROR,
                    hint="Write environment requirements as a short string.",
                )
            ]
        if len(value) > MAX_COMPATIBILITY_LENGTH:
            return [
                finding(
                    "compatibility-length",
                    f"compatibility is {len(value)} characters; the maximum is {MAX_COMPATIBILITY_LENGTH}",
                    doc.path,
                    _value_location(doc, "compatibility"),
                    Severity.ERROR,
                    hint="Shorten the compatibility note to the required tools or packages.",
                )
            ]
        if not value.strip():
            return [
                finding(
                    "compatibility-empty",
                    "compatibility is empty; omit the field if there are no special requirements",
                    doc.path,
                    _value_location(doc, "compatibility"),
                    Severity.WARNING,
                    hint="Remove compatibility, or list the actual requirements.",
                )
            ]
        return []


class CompatibilityLength:
    """Placeholder so --explain and --list-rules can show this id.

    The check itself lives on CompatibilityType so we inspect the field once.
    """

    id = "compatibility-length"
    description = "compatibility must be at most 500 characters."
    default_severity = Severity.ERROR
    explanation = CompatibilityType.explanation
    examples = CompatibilityType.examples

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


class CompatibilityEmpty:
    id = "compatibility-empty"
    description = "Empty compatibility fields should be omitted."
    default_severity = Severity.WARNING
    explanation = CompatibilityType.explanation
    examples = CompatibilityType.examples

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


class MetadataType:
    id = "metadata-type"
    description = "metadata must be a mapping of string keys to string values."
    default_severity = Severity.ERROR
    explanation = (
        "The Agent Skills specification defines metadata as a map of string keys "
        "to string values for client-specific properties."
    )
    examples = 'Good:\nmetadata:\n  author: example-org\n  version: "1.0"'

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "metadata" not in doc.frontmatter:
            return []
        value = doc.frontmatter["metadata"]
        location = _value_location(doc, "metadata")
        if not isinstance(value, dict):
            return [
                finding(
                    self.id,
                    f"metadata must be a mapping, not {type(value).__name__}",
                    doc.path,
                    location,
                    Severity.ERROR,
                    hint="Use a YAML mapping such as metadata:\\n  author: your-name",
                )
            ]
        findings: list[Finding] = []
        for key, item in value.items():
            if not isinstance(key, str):
                findings.append(
                    finding(
                        self.id,
                        f"metadata key {key!r} must be a string",
                        doc.path,
                        location,
                        Severity.ERROR,
                    )
                )
            if not isinstance(item, str):
                findings.append(
                    finding(
                        "metadata-value-type",
                        f"metadata[{key!r}] must be a string, not {type(item).__name__}",
                        doc.path,
                        location,
                        Severity.ERROR,
                        hint="Quote numbers and booleans, for example version: \"1.0\".",
                    )
                )
        return findings


class MetadataValueType:
    id = "metadata-value-type"
    description = "metadata values must be strings."
    default_severity = Severity.ERROR
    explanation = MetadataType.explanation
    examples = MetadataType.examples

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


class LicenseType:
    id = "license-type"
    description = "license must be a short string, optionally naming a bundled license file."
    default_severity = Severity.ERROR
    explanation = (
        "license is an optional field. It should be a short license name or a "
        "reference to a license file in the skill directory."
    )
    examples = "Good: license: MIT\nGood: license: LICENSE.txt"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "license" not in doc.frontmatter:
            return []
        value = doc.frontmatter["license"]
        if not isinstance(value, str):
            return [
                finding(
                    self.id,
                    f"license must be a string, not {type(value).__name__}",
                    doc.path,
                    _value_location(doc, "license"),
                    Severity.ERROR,
                    hint="Use a short string such as MIT, or the name of a bundled license file.",
                )
            ]
        if not value.strip():
            return [
                finding(
                    self.id,
                    "license is empty; omit the field or name the license",
                    doc.path,
                    _value_location(doc, "license"),
                    Severity.WARNING,
                )
            ]
        findings: list[Finding] = []
        text = value.strip()
        looks_like_file = (
            text in {"LICENSE", "LICENCE", "COPYING", "COPYING.LESSER"}
            or text.startswith("LICENSE.")
            or text.startswith("LICENCE.")
            or text.endswith((".txt", ".md", ".rst"))
        )
        if looks_like_file:
            candidate = (doc.skill_dir / text).resolve()
            try:
                candidate.relative_to(doc.skill_dir.resolve())
            except ValueError:
                candidate = None
            if candidate is not None and not candidate.is_file():
                findings.append(
                    finding(
                        "license-file-missing",
                        f"license refers to {text!r}, but that file is not in the skill directory",
                        doc.path,
                        _value_location(doc, "license"),
                        Severity.ERROR,
                        hint=f"Add {text} next to SKILL.md, or set license to a license name such as MIT.",
                    )
                )
        return findings


class LicenseFileMissing:
    id = "license-file-missing"
    description = "A license field that names a file must point to a file that exists."
    default_severity = Severity.ERROR
    explanation = LicenseType.explanation
    examples = LicenseType.examples

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


def _split_tool_tokens(value: Any) -> list[str] | None:
    if isinstance(value, str):
        text = value.replace(",", " ")
        return [token for token in text.split() if token]
    if isinstance(value, list):
        tokens: list[str] = []
        for item in value:
            if not isinstance(item, str):
                return None
            tokens.extend(part for part in item.replace(",", " ").split() if part)
        return tokens
    return None


class AllowedToolsType:
    id = "allowed-tools-type"
    description = "allowed-tools must be a string or list of tool names."
    default_severity = Severity.ERROR
    explanation = (
        "allowed-tools is an experimental Agent Skills field listing tools that "
        "may run without asking for permission while the skill is active. The "
        "specification uses a space-separated string; Claude Code also accepts a "
        "comma-separated string or a YAML list."
    )
    examples = "Good: allowed-tools: Read Grep\nGood: allowed-tools: Bash(git:*) Read"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "allowed-tools" not in doc.frontmatter:
            return []
        value = doc.frontmatter["allowed-tools"]
        location = _value_location(doc, "allowed-tools")
        tokens = _split_tool_tokens(value)
        if tokens is None:
            return [
                finding(
                    self.id,
                    f"allowed-tools must be a string or list of strings, not {type(value).__name__}",
                    doc.path,
                    location,
                    Severity.ERROR,
                    hint="Use a space-separated string, for example: allowed-tools: Bash(git:*) Read",
                )
            ]
        if not tokens:
            return [
                finding(
                    "allowed-tools-empty",
                    "allowed-tools is empty; omit the field if no tools should be pre-approved",
                    doc.path,
                    location,
                    Severity.WARNING,
                    hint="Remove the field, or list the specific tools this skill needs.",
                )
            ]
        findings: list[Finding] = []
        broad = [token for token in tokens if token in {"Bash", "Shell"} or token.endswith("(*)")]
        if broad:
            findings.append(
                finding(
                    "allowed-tools-broad",
                    f"allowed-tools pre-approves broad shell access via {', '.join(broad)}",
                    doc.path,
                    location,
                    Severity.WARNING,
                    hint="Prefer a narrower grant such as Bash(git:*) if the skill only needs specific commands.",
                )
            )
        return findings


class AllowedToolsEmpty:
    id = "allowed-tools-empty"
    description = "Empty allowed-tools fields should be omitted."
    default_severity = Severity.WARNING
    explanation = AllowedToolsType.explanation
    examples = AllowedToolsType.examples

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


class AllowedToolsBroad:
    id = "allowed-tools-broad"
    description = "Avoid pre-approving unconstrained shell access."
    default_severity = Severity.WARNING
    explanation = (
        "allowed-tools grants tools without a permission prompt for the turn that "
        "invokes the skill. A bare Bash or Shell grant is a wide permission and is "
        "usually broader than the skill needs."
    )
    examples = "Bad: allowed-tools: Bash\nGood: allowed-tools: Bash(git:*) Read"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


class DisallowedToolsType:
    id = "disallowed-tools-type"
    description = "disallowed-tools must be a string or list of tool names."
    default_severity = Severity.ERROR
    explanation = (
        "disallowed-tools is a Claude Code extension that removes tools from the "
        "available pool while the skill is active. It accepts a space- or "
        "comma-separated string, or a YAML list."
    )
    examples = "Good: disallowed-tools: AskUserQuestion"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "disallowed-tools" not in doc.frontmatter:
            return []
        value = doc.frontmatter["disallowed-tools"]
        tokens = _split_tool_tokens(value)
        if tokens is not None:
            return []
        return [
            finding(
                self.id,
                f"disallowed-tools must be a string or list of strings, not {type(value).__name__}",
                doc.path,
                _value_location(doc, "disallowed-tools"),
                Severity.ERROR,
                hint="Use a space-separated string or a YAML list of tool names.",
            )
        ]


class PathsType:
    id = "paths-type"
    description = "paths and globs must be a glob string or a list of glob strings."
    default_severity = Severity.ERROR
    explanation = (
        "Cursor uses paths to scope a skill to matching files. It accepts a "
        "comma-separated string or a YAML list. The older globs field is still "
        "accepted but new skills should use paths."
    )
    examples = "Good:\npaths:\n  - \"**/*.tsx\"\n  - packages/ui/**/*.ts"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None:
            return []
        findings: list[Finding] = []
        for key in ("paths", "globs"):
            if key not in doc.frontmatter:
                continue
            value = doc.frontmatter[key]
            tokens = _split_tool_tokens(value)
            if tokens is None:
                findings.append(
                    finding(
                        self.id,
                        f"{key} must be a glob string or a list of strings, not {type(value).__name__}",
                        doc.path,
                        _value_location(doc, key),
                        Severity.ERROR,
                        hint="Use a YAML list of glob patterns, or a comma-separated string.",
                    )
                )
            elif any(not token.strip() for token in tokens):
                findings.append(
                    finding(
                        self.id,
                        f"{key} contains an empty pattern",
                        doc.path,
                        _value_location(doc, key),
                        Severity.ERROR,
                        hint="Remove empty entries from the pattern list.",
                    )
                )
        return findings


class LegacyGlobs:
    id = "legacy-globs"
    description = "New skills should use paths instead of the legacy globs field."
    default_severity = Severity.WARNING
    explanation = (
        "Cursor still accepts globs as a fallback for older skills, but new skills "
        "should use paths."
    )
    examples = "Bad: globs: \"**/*.py\"\nGood: paths: \"**/*.py\""

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "globs" not in doc.frontmatter:
            return []
        hint = "Rename globs to paths."
        if "paths" in doc.frontmatter:
            hint = "Remove globs and keep paths."
        return [
            finding(
                self.id,
                "frontmatter uses legacy field 'globs'; prefer 'paths'",
                doc.path,
                _value_location(doc, "globs"),
                Severity.WARNING,
                hint=hint,
            )
        ]


class BooleanFieldType:
    id = "boolean-field-type"
    description = "Boolean frontmatter fields must be true/false or a recognized YAML boolean."
    default_severity = Severity.ERROR
    explanation = (
        "Claude Code and Cursor boolean fields such as disable-model-invocation and "
        "user-invocable accept true/false, and Claude Code also accepts yes/no, "
        "on/off, and 1/0. Other strings are ignored or misread."
    )
    examples = "Good: disable-model-invocation: true"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None:
            return []
        findings: list[Finding] = []
        allowed_strings = {"true", "false", "yes", "no", "on", "off", "1", "0"}
        for key in BOOLEAN_FIELDS:
            if key not in doc.frontmatter:
                continue
            value = doc.frontmatter[key]
            if isinstance(value, bool):
                continue
            if isinstance(value, int) and value in (0, 1):
                continue
            if isinstance(value, str) and value.strip().lower() in allowed_strings:
                continue
            findings.append(
                finding(
                    self.id,
                    f"{key} must be a boolean, not {type(value).__name__} {value!r}",
                    doc.path,
                    _value_location(doc, key),
                    Severity.ERROR,
                    hint=f"Set {key}: true or {key}: false.",
                )
            )
        return findings


class ColorInvalid:
    id = "color-invalid"
    description = "color must be one of the Cursor badge color names."
    default_severity = Severity.ERROR
    explanation = (
        "Cursor uses color for the skill badge when the skill is used as a Custom "
        "Mode. Allowed values are default, green, cyan, blue, purple, magenta, "
        "orange, yellow, red, and brand."
    )
    examples = "Good: color: blue"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None or "color" not in doc.frontmatter:
            return []
        value = doc.frontmatter["color"]
        if not isinstance(value, str):
            return [
                finding(
                    self.id,
                    f"color must be a string, not {type(value).__name__}",
                    doc.path,
                    _value_location(doc, "color"),
                    Severity.ERROR,
                    hint="Use one of: " + ", ".join(sorted(CURSOR_COLORS)) + ".",
                )
            ]
        if value in CURSOR_COLORS:
            return []
        return [
            finding(
                self.id,
                f"color {value!r} is not a known Cursor badge color",
                doc.path,
                _value_location(doc, "color"),
                Severity.ERROR,
                hint="Use one of: " + ", ".join(sorted(CURSOR_COLORS)) + ".",
            )
        ]


class UnknownField:
    id = "unknown-field"
    description = "Frontmatter should only use known Agent Skills or documented vendor fields."
    default_severity = Severity.WARNING
    explanation = (
        "Unknown frontmatter keys are ignored by most hosts, which usually means a typo. "
        "The open specification allows name, description, license, compatibility, "
        "metadata, and allowed-tools. Claude Code and Cursor add a few documented "
        "extensions, which skill-lint accepts unless you pass --profile spec."
    )
    examples = "Bad: desc: ...\nGood: description: ..."

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.frontmatter is None:
            return []
        allowed = ctx.config.allowed_fields
        findings: list[Finding] = []
        for key in doc.frontmatter:
            if key in allowed:
                continue
            if key in FIELD_ALIASES:
                canonical = FIELD_ALIASES[key]
                extra = ""
                if ctx.config.profile == "spec" and canonical in VENDOR_FIELDS:
                    extra = (
                        f" '{canonical}' is a vendor extension; --profile spec only allows "
                        + ", ".join(sorted(SPEC_FIELDS))
                    )
                findings.append(
                    finding(
                        "field-alias",
                        f"frontmatter field {key!r} should be written as {canonical!r}{extra}",
                        doc.path,
                        _value_location(doc, key),
                        Severity.ERROR,
                        hint=f"Rename {key} to {canonical}.",
                    )
                )
                continue
            suggestion = get_close_matches(key, list(allowed | set(FIELD_ALIASES)), n=1, cutoff=0.6)
            hint = f"Did you mean {suggestion[0]!r}?" if suggestion else (
                "Known fields: " + ", ".join(sorted(allowed)) + "."
            )
            if ctx.config.profile == "spec" and key in VENDOR_FIELDS:
                hint = (
                    f"{key!r} is a Claude Code or Cursor extension. Use --profile standard "
                    "to allow vendor fields, or move this information into the body or metadata."
                )
            findings.append(
                finding(
                    self.id,
                    f"unknown frontmatter field {key!r}",
                    doc.path,
                    _value_location(doc, key),
                    Severity.WARNING,
                    hint=hint,
                )
            )
        return findings


class FieldAlias:
    id = "field-alias"
    description = "Frontmatter field names should use the canonical hyphenated form."
    default_severity = Severity.ERROR
    explanation = (
        "Hosts match field names exactly. allowed_tools, when-to-use, or similar "
        "aliases are ignored, so the permission or trigger you thought you set is not applied."
    )
    examples = "Bad: allowed_tools: Read\nGood: allowed-tools: Read"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


class DuplicateName:
    id = "duplicate-name"
    description = "Skill names in a single lint run should be unique."
    default_severity = Severity.WARNING
    explanation = (
        "Two skills with the same name are hard to invoke and may override each other "
        "depending on load order."
    )
    examples = "Bad: two directories both named pdf-processing, or two files with the same name field"

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        name = doc.name
        if not name:
            return []
        peers = [other for other in ctx.documents if other is not doc and other.name == name]
        if not peers:
            return []
        others = ", ".join(str(peer.skill_dir) for peer in peers)
        return [
            finding(
                self.id,
                f"skill name {name!r} is also used by {others}",
                doc.path,
                _value_location(doc, "name"),
                Severity.WARNING,
                hint="Give each skill a unique name and directory.",
            )
        ]
