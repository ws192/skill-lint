"""Built-in skill-lint rules."""

from __future__ import annotations

from skill_lint.models import Finding, SkillDocument
from skill_lint.rules.base import LintContext, Rule
from skill_lint.rules.frontmatter import (
    AllowedToolsBroad,
    AllowedToolsEmpty,
    AllowedToolsType,
    BooleanFieldType,
    ColorInvalid,
    CompatibilityEmpty,
    CompatibilityLength,
    CompatibilityType,
    DescriptionEmpty,
    DescriptionLength,
    DescriptionMissing,
    DescriptionNoWhen,
    DescriptionType,
    DescriptionVague,
    DescriptionXml,
    DisallowedToolsType,
    DuplicateName,
    FieldAlias,
    LegacyGlobs,
    LicenseFileMissing,
    LicenseType,
    MetadataType,
    MetadataValueType,
    NameCase,
    NameCharset,
    NameEmpty,
    NameHyphen,
    NameLength,
    NameMismatch,
    NameMissing,
    NameReserved,
    NameType,
    NameXml,
    PathsType,
    UnknownField,
)
from skill_lint.rules.references import (
    AbsolutePath,
    BrokenReference,
    EmptyResourceDir,
    NestedReference,
    UnreferencedReference,
    UnreferencedScript,
    WindowsPath,
)
from skill_lint.rules.structure import (
    BodyEmpty,
    BodyTooLong,
    BodyTooShort,
    Placeholder,
    SkillMdFilename,
)

# Parse findings are produced while reading the file, then filtered like other rules.
PARSE_RULE_IDS = frozenset(
    {
        "frontmatter-missing",
        "frontmatter-unclosed",
        "frontmatter-invalid",
        "frontmatter-not-mapping",
        "frontmatter-leading-content",
    }
)

PARSE_RULE_DOCS: dict[str, dict[str, str]] = {
    "frontmatter-missing": {
        "description": "SKILL.md must start with YAML frontmatter delimited by '---' lines.",
        "severity": "error",
        "explanation": (
            "Agents read skill metadata from YAML frontmatter at the top of SKILL.md. "
            "If the file does not start with ---, many hosts treat the entire file as "
            "unstructured text and never see the name or description."
        ),
        "examples": "---\nname: my-skill\ndescription: What it does and when to use it.\n---\n",
    },
    "frontmatter-unclosed": {
        "description": "YAML frontmatter must be closed with a '---' line.",
        "severity": "error",
        "explanation": "An opening --- without a matching closer means the frontmatter cannot be parsed.",
        "examples": "Close the block with a line that contains only ---.",
    },
    "frontmatter-invalid": {
        "description": "YAML frontmatter must parse as valid YAML.",
        "severity": "error",
        "explanation": "If the YAML is invalid, some hosts load the skill with no fields set.",
        "examples": "Check indentation, colons, and quoting.",
    },
    "frontmatter-not-mapping": {
        "description": "YAML frontmatter must be a mapping of field names to values.",
        "severity": "error",
        "explanation": "A list or a bare string in the frontmatter cannot provide name and description.",
        "examples": "Use keys such as name: and description:.",
    },
    "frontmatter-leading-content": {
        "description": "The opening '---' must be the first line of SKILL.md.",
        "severity": "error",
        "explanation": (
            "Claude Code only reads frontmatter when the opening --- is the first line. "
            "A BOM, blank line, or leading whitespace will cause the metadata to be ignored."
        ),
        "examples": "Make --- the first characters of the file.",
    },
}


def _all_rule_objects() -> list[Rule]:
    return [
        SkillMdFilename(),
        NameMissing(),
        NameType(),
        NameEmpty(),
        NameLength(),
        NameCase(),
        NameCharset(),
        NameHyphen(),
        NameMismatch(),
        NameReserved(),
        NameXml(),
        DescriptionMissing(),
        DescriptionType(),
        DescriptionEmpty(),
        DescriptionLength(),
        DescriptionXml(),
        DescriptionVague(),
        DescriptionNoWhen(),
        CompatibilityType(),
        CompatibilityLength(),
        CompatibilityEmpty(),
        MetadataType(),
        MetadataValueType(),
        LicenseType(),
        LicenseFileMissing(),
        AllowedToolsType(),
        AllowedToolsEmpty(),
        AllowedToolsBroad(),
        DisallowedToolsType(),
        PathsType(),
        LegacyGlobs(),
        BooleanFieldType(),
        ColorInvalid(),
        UnknownField(),
        FieldAlias(),
        DuplicateName(),
        BodyEmpty(),
        BodyTooLong(),
        BodyTooShort(),
        Placeholder(),
        BrokenReference(),
        AbsolutePath(),
        WindowsPath(),
        UnreferencedScript(),
        UnreferencedReference(),
        EmptyResourceDir(),
        NestedReference(),
    ]


RULES: list[Rule] = _all_rule_objects()
RULES_BY_ID: dict[str, Rule] = {rule.id: rule for rule in RULES}


class _ParseRule:
    """Adapter so parse-time checks appear in --list-rules and --explain."""

    def __init__(self, rule_id: str, docs: dict[str, str]) -> None:
        from skill_lint.models import Severity

        self.id = rule_id
        self.description = docs["description"]
        self.default_severity = Severity(docs["severity"])
        self.explanation = docs["explanation"]
        self.examples = docs["examples"]

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        return []


def all_rule_docs() -> list[Rule]:
    parse_rules = [_ParseRule(rule_id, docs) for rule_id, docs in PARSE_RULE_DOCS.items()]
    # Put parse rules first, then the rest, de-duplicating by id.
    combined: list[Rule] = []
    seen: set[str] = set()
    for rule in [*parse_rules, *RULES]:
        if rule.id in seen:
            continue
        seen.add(rule.id)
        combined.append(rule)
    return combined
