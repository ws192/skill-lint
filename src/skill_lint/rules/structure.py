"""Structure and file-level rules."""

from __future__ import annotations

from skill_lint.models import Finding, Location, Severity, SkillDocument
from skill_lint.parse import locate_key
from skill_lint.rules.base import LintContext, body_location, file_start, finding, loc


class SkillMdFilename:
    id = "skill-md-filename"
    description = "The skill file should be named SKILL.md, with that exact casing."
    default_severity = Severity.ERROR
    explanation = (
        "The Agent Skills specification requires a file named SKILL.md in the skill "
        "directory. Some tools only look for that exact name and will skip skill.md "
        "or Skill.md."
    )
    examples = (
        "Bad: my-skill/skill.md\n"
        "Good: my-skill/SKILL.md"
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        if doc.path.name == "SKILL.md":
            return []
        return [
            finding(
                self.id,
                f"skill file is named {doc.path.name!r}; the spec requires 'SKILL.md'",
                doc.path,
                file_start(doc),
                Severity.ERROR,
                hint="Rename the file to SKILL.md.",
            )
        ]


class BodyEmpty:
    id = "body-empty"
    description = "SKILL.md must include Markdown instructions after the frontmatter."
    default_severity = Severity.ERROR
    explanation = (
        "The frontmatter tells an agent when to use a skill. The Markdown body is "
        "the actual recipe it will follow once the skill is activated. An empty body "
        "leaves the agent with no instructions."
    )
    examples = (
        "Bad: a file that ends right after the closing ---\n"
        "Good: frontmatter followed by clear step-by-step instructions"
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        parse_failed = doc.frontmatter is None and any(
            item.rule in {"frontmatter-missing", "frontmatter-unclosed", "frontmatter-invalid"}
            for item in doc.parse_findings
        )
        # If we could not isolate a body, skip to avoid a noisy second error
        # on files that are completely unparsable, except a missing frontmatter
        # with no body at all is still useful.
        if parse_failed and doc.body.strip():
            return []
        if doc.body.strip():
            return []
        line = doc.body_start_line if doc.frontmatter_end_line else 1
        return [
            finding(
                self.id,
                "SKILL.md has no instruction body after the frontmatter",
                doc.path,
                loc(line),
                Severity.ERROR,
                hint="Add Markdown instructions describing the steps the agent should follow.",
            )
        ]


class BodyTooLong:
    id = "body-too-long"
    description = "Keep the SKILL.md body under 500 lines and move detail into referenced files."
    default_severity = Severity.WARNING
    explanation = (
        "Agents load the entire SKILL.md body when a skill is activated. The Agent "
        "Skills specification recommends keeping that body under 500 lines and moving "
        "detailed reference material into files under references/."
    )
    examples = (
        "Bad: a 900-line SKILL.md that inlines a full API reference\n"
        "Good: a short recipe that points to references/api.md"
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        body = doc.body
        # Count lines the way an editor would, ignoring a trailing newline.
        lines = body.splitlines()
        count = len(lines)
        limit = ctx.config.body_max_lines
        if count <= limit:
            return []
        return [
            finding(
                self.id,
                f"SKILL.md body is {count} lines; keep it under {limit} and move detail to referenced files",
                doc.path,
                body_location(doc, limit + 1),
                Severity.WARNING,
                hint="Move long reference material into references/ and link to it from SKILL.md.",
            )
        ]


class BodyTooShort:
    id = "body-too-short"
    description = "Instruction bodies should be substantial enough to follow."
    default_severity = Severity.WARNING
    explanation = (
        "A heading or a single vague sentence is rarely enough for an agent to "
        "carry out the task reliably. Write concrete steps, examples, or rules."
    )
    examples = (
        "Bad: '# My Skill\\n\\nDo the thing.'\n"
        "Good: a short but specific sequence of steps, with examples where they help"
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        text = doc.body.strip()
        if not text:
            return []  # body-empty covers this
        # Ignore heading markers and backticks when measuring useful text.
        useful = "".join(ch for ch in text if ch not in "#*`")
        useful = " ".join(useful.split())
        if len(useful) >= ctx.config.body_min_chars:
            return []
        return [
            finding(
                self.id,
                f"instruction body is only {len(useful)} useful characters; add concrete steps or examples",
                doc.path,
                body_location(doc),
                Severity.WARNING,
                hint="Describe the workflow in enough detail that another person could follow it.",
            )
        ]


class Placeholder:
    id = "placeholder"
    description = "Skills should not ship with TODO, TBD, FIXME, or lorem ipsum placeholders."
    default_severity = Severity.WARNING
    explanation = (
        "Placeholder text means the skill is unfinished. Agents will treat those "
        "notes as instructions or skip important steps."
    )
    examples = (
        "Bad: 'TODO: write the upload steps'\n"
        "Good: the actual upload steps"
    )

    _patterns = (
        ("TODO", r"\bTODO\b"),
        ("TBD", r"\bTBD\b"),
        ("FIXME", r"\bFIXME\b"),
        ("XXX", r"\bXXX\b"),
        ("lorem ipsum", r"lorem ipsum"),
        ("your text here", r"your text here"),
        ("coming soon", r"coming soon"),
    )

    def check(self, doc: SkillDocument, ctx: LintContext) -> list[Finding]:
        import re

        findings: list[Finding] = []
        # Check description and body.
        sources: list[tuple[str, str, Location]] = []
        if isinstance(doc.frontmatter, dict) and isinstance(doc.frontmatter.get("description"), str):
            sources.append(
                ("description", doc.frontmatter["description"], locate_key(doc, "description"))
            )
        if doc.body:
            sources.append(("body", doc.body, body_location(doc)))

        compiled = [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in self._patterns]
        seen: set[tuple[int, str]] = set()
        for where, text, fallback in sources:
            for label, regex in compiled:
                for match in regex.finditer(text):
                    if where == "body":
                        line_offset = text[: match.start()].count("\n")
                        column = match.start() - text.rfind("\n", 0, match.start())
                        location = body_location(doc, line_offset + 1, column)
                    else:
                        location = fallback
                    key = (location.line, label)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        finding(
                            self.id,
                            f"{where} contains placeholder text {label!r}",
                            doc.path,
                            location,
                            Severity.WARNING,
                            hint="Replace the placeholder with finished instructions.",
                        )
                    )
        return findings
