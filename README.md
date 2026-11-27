# skill-lint

A linter for [Agent Skills](https://agentskills.io/specification) — the `SKILL.md` format used by Claude Code, Cursor, Codex, and other coding agents.

It checks skill structure and frontmatter against the open specification, understands common Claude Code and Cursor extensions, and flags practical problems such as missing triggers, broken file references, and overly broad tool grants.

skill-lint runs entirely on your machine. It does not send your files or usage data anywhere.

## Install

Python 3.10 or later is required.

```bash
# from the repo
pip install .

# or, without checking the repo out first
pip install git+https://github.com/ws192/skill-lint.git
```

With [uv](https://docs.astral.sh/uv/) or pipx:

```bash
uv tool install git+https://github.com/ws192/skill-lint.git
# or
pipx install git+https://github.com/ws192/skill-lint.git
```

For local development:

```bash
pip install -e ".[dev]"
pytest
```

## Usage

```bash
# lint the current directory (finds SKILL.md files, including under
# .agents/skills, .cursor/skills, .claude/skills, .codex/skills, and skills/)
skill-lint

# lint one skill or a directory of skills
skill-lint path/to/my-skill
skill-lint path/to/my-skill/SKILL.md
skill-lint .cursor/skills

# CI-friendly formats
skill-lint --format github
skill-lint --format json
skill-lint --format sarif > skill-lint.sarif

# treat warnings as errors
skill-lint --strict

# fail if there are more than 10 warnings
skill-lint --max-warnings 10

# inspect the rule set
skill-lint --list-rules
skill-lint --explain name-mismatch
```

You can also lint a buffer:

```bash
skill-lint --stdin --stdin-path SKILL.md --skill-dir ./my-skill < my-skill/SKILL.md
```

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | No errors (warnings are allowed unless `--strict` or `--max-warnings` is set) |
| 1 | Lint issues found |
| 2 | Bad usage, missing path, or invalid config |

## What it checks

### Structure and frontmatter

- `SKILL.md` is present and named with that exact casing
- The file starts with YAML frontmatter (a leading BOM, blank line, or whitespace is flagged; many hosts only read frontmatter when `---` is the first line)
- YAML parses and is a mapping
- Required `name` and `description` fields
- `name` is 1–64 characters, lowercase letters/digits/hyphens only, no leading, trailing, or doubled hyphens, and it matches the skill directory name
- Reserved tokens such as `anthropic` and `claude` are rejected in `name`
- Angle brackets in `name` or `description` (Claude and Codex treat these as XML and may refuse the skill)
- `description` is non-empty and at most 1024 characters
- Optional spec fields: `license`, `compatibility` (≤500 characters), `metadata` (string-to-string map), `allowed-tools`

### Tool and permission declarations

- `allowed-tools` and `disallowed-tools` are a string or list of tool names
- A bare `Bash` or `Shell` grant is flagged as overly broad; prefer a filter such as `Bash(git:*)`
- Cursor `paths` / legacy `globs`, badge `color`, and boolean fields such as `disable-model-invocation` are type-checked
- Unknown frontmatter keys and common aliases (`allowed_tools`, `when-to-use`, …) are reported, with a suggestion when the typo is obvious

Use `--profile spec` if you want to allow only the six fields from the [Agent Skills specification](https://agentskills.io/specification). The default `standard` profile also accepts documented Claude Code and Cursor fields.

### Quality and references

- Descriptions that are too short or never say when the skill should be used
- An empty, very short, or >500-line instruction body (the spec recommends keeping `SKILL.md` under 500 lines and moving detail into `references/`)
- `TODO`, `FIXME`, `TBD`, and similar placeholders
- Broken relative links and missing `scripts/…` or `references/…` paths
- Bundled scripts or reference files that `SKILL.md` never mentions
- Empty `scripts/`, `references/`, or `assets/` directories
- Absolute machine paths and Windows backslashes in skill file paths
- Reference chains more than one level deep from `SKILL.md`
- Duplicate skill names in a single run

Each finding includes the file, line (and column when known), a rule id, a short message, and a hint on how to fix it.

## Output

Default text output looks like this:

```
path/to/name-mismatch/SKILL.md
     2:1    error    name-mismatch  name 'invoices' does not match directory 'name-mismatch'
                    Rename the directory to 'invoices', or set name to 'name-mismatch'.

x  1 error in 1 skill
```

`--format json` is a stable object with `findings`, `errorCount`, `warningCount`, and `skillCount`. `--format github` emits [workflow commands](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions) so annotations show up on pull requests. `--format sarif` is SARIF 2.1.0, suitable for code scanning uploads.

## Configuration

skill-lint looks for `.skill-lint.toml`, `skill-lint.toml`, or a `[tool.skill-lint]` table in `pyproject.toml`, walking up from the first path you pass (or the current directory).

```toml
# .skill-lint.toml
profile = "standard"          # standard | strict | spec
format = "text"
strict = false
max-warnings = 20
ignore = ["unreferenced-reference"]  # rule ids to disable

[severity]
# error | warning | info | off
allowed-tools-broad = "error"

[rules.description-vague]
min-length = 40
```

`strict` as a profile promotes several quality warnings (vague descriptions, placeholders, unreferenced scripts, unknown fields, and others) to errors. `--strict` on the command line treats every remaining warning as an error, which is usually what you want in CI.

Command-line flags override the config file. `--no-config` ignores config files entirely.

## GitHub Actions

```yaml
name: skill-lint
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install git+https://github.com/ws192/skill-lint.git
      - run: skill-lint --strict --format github
```

## Library use

```python
from pathlib import Path
from skill_lint.config import Config
from skill_lint.lint import lint_paths

report = lint_paths([Path("path/to/skills")], Config())
for finding in report.sorted_findings():
    print(f"{finding.path}:{finding.line} {finding.rule}: {finding.message}")
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

## License

MIT. See [LICENSE](LICENSE).
