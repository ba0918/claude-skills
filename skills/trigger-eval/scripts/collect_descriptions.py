#!/usr/bin/env python3
"""
trigger-eval: Collect skill frontmatter descriptions from a skill set.

Reads `<dir>/*/SKILL.md` frontmatter and emits a normalized
`{name, description}` list as JSON. Skill names are normalized to the
plugin-prefix-free "bare name" so that downstream case labels, judge
choices and aggregation share a single namespace.

v1 scope: flat skill directories only (`skills/`, `~/.claude/skills`,
`--dir PATH`). The plugin cache's hash-nested layout
(`~/.claude/plugins/cache/<mp>/<plugin>/<hash>/skills/`) is out of scope.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# plugin prefix like "claude-skills:" or "wiki:"
_PLUGIN_PREFIX_RE = re.compile(r"^[a-z][a-z0-9-]*:")


class DuplicateSkillError(Exception):
    """Raised when two skills normalize to the same bare name (v1 unsupported)."""


def normalize_bare_name(name: str) -> str:
    """Strip a leading `<plugin>:` prefix, returning the bare skill name."""
    return _PLUGIN_PREFIX_RE.sub("", name.strip(), count=1)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse YAML-ish frontmatter into {name, description}.

    Returns None when no `---` delimited frontmatter block is present.
    A missing `description` becomes an empty string. Multi-line
    descriptions (indented continuation lines) are joined with spaces.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body: list[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        body.append(line)
    if not closed:
        return None

    name = ""
    desc_lines: list[str] = []
    in_desc = False
    for line in body:
        m_name = re.match(r"^name:\s*(.*)$", line)
        if m_name:
            name = m_name.group(1).strip()
            in_desc = False
            continue
        m_desc = re.match(r"^description:\s*(.*)$", line)
        if m_desc:
            in_desc = True
            desc_lines.append(m_desc.group(1).strip())
            continue
        if in_desc:
            # continuation only if indented (still part of description)
            if re.match(r"^[A-Za-z_-]+:", line):
                in_desc = False
                continue
            desc_lines.append(line.strip())

    if desc_lines and desc_lines[0] in (">", "|", ">-", "|-"):
        desc_lines = desc_lines[1:]
    description = " ".join(l for l in desc_lines if l).strip()
    return {"name": name, "description": description}


def collect_from_dir(dir_path: Path) -> list[dict[str, str]]:
    """Collect {name, description} from `<dir_path>/*/SKILL.md`.

    - Only `SKILL.md` files are considered (other markdown is ignored).
    - Symlinked skill directories and symlinked SKILL.md files are skipped
      (path-traversal / symlink-escape prevention).
    - Skill names are normalized to bare names; a missing frontmatter name
      falls back to the directory name.
    - Duplicate bare names raise DuplicateSkillError (fail-fast).
    """
    skills: list[dict[str, str]] = []
    seen: dict[str, str] = {}

    for child in sorted(dir_path.iterdir()):
        if child.is_symlink():
            continue
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        if skill_md.is_symlink():
            continue

        text = skill_md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm is None:
            continue
        raw_name = fm["name"] or child.name
        name = normalize_bare_name(raw_name)
        if not name:
            name = child.name
        if name in seen:
            raise DuplicateSkillError(
                f"duplicate bare skill name '{name}': "
                f"'{seen[name]}' and '{child.name}' (v1 does not support "
                f"colliding namespaces)"
            )
        seen[name] = child.name
        skills.append({"name": name, "description": fm["description"]})

    return skills


def resolve_source_dir(args: argparse.Namespace) -> Path:
    """Determine the skill source directory from CLI args."""
    if args.dir:
        return Path(args.dir)
    if args.user_scope:
        return Path.home() / ".claude" / "skills"
    return Path.cwd() / "skills"


def build_result(dir_path: Path) -> dict[str, Any]:
    """Collect skills under dir_path and wrap into the output envelope."""
    skills = collect_from_dir(dir_path)
    return {
        "source": str(dir_path),
        "count": len(skills),
        "skills": skills,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect skill frontmatter descriptions as JSON"
    )
    parser.add_argument(
        "--dir", type=str, default=None,
        help="Skill directory containing */SKILL.md (default: ./skills)",
    )
    parser.add_argument(
        "--user-scope", action="store_true", default=False,
        help="Use ~/.claude/skills instead of the current repo",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    source = resolve_source_dir(args)
    if not source.is_dir():
        print(f"error: not a directory: {source}", file=sys.stderr)
        return 2

    try:
        result = build_result(source)
    except DuplicateSkillError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(json_str + "\n", encoding="utf-8")
    else:
        print(json_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
