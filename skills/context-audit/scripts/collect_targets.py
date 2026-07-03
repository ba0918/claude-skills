#!/usr/bin/env python3
"""
context-audit: audit-target discovery & classification.

Deterministic path-allowlist discovery (no content inference). Only files on
an explicit allowlist are collected, so archival/temp areas (docs/plans,
docs/ideas, .claude/tmp, ...) are excluded by construction. Missing targets
graceful-skip; a single unreadable file never aborts the whole audit.

Memory auditing defaults to the cwd-corresponding project only. The cwd->slug
mapping mirrors real Claude Code (every non-alphanumeric char -> '-', not just
'/'), and the resolved dir is reverse-verified to live directly under
~/.claude/projects/ (fail-safe skip otherwise) to avoid reading another
project's memory. Global / cross-project targets require --include-global.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Repo-relative instruction-bearing files (positive allowlist). Directories are
# expanded to their top-level *.md (nested subdir CLAUDE.md/AGENTS.md are v1
# out of scope). Each entry: (relpath_or_dir, kind, is_dir).
REPO_FILE_TARGETS: list[tuple[str, str]] = [
    ("CLAUDE.md", "claude_md"),
    ("AGENTS.md", "agents_md"),
    (".claude/review-rules.md", "review_rules"),
]
REPO_DIR_TARGETS: list[tuple[str, str]] = [
    (".claude/rules", "rules"),
    ("rules", "rules"),
]

_SLUG_RE = re.compile(r"[^A-Za-z0-9]")


def slugify_cwd(path: str) -> str:
    """Replicate Claude Code's project-slug: every non-alphanumeric char -> '-'.

    e.g. '/x/.claude' -> '-x--claude', '/a/b' -> '-a-b'.
    """
    return _SLUG_RE.sub("-", path)


def resolve_memory_dir(cwd: str, home: Path) -> Path | None:
    """Resolve the cwd-corresponding project memory dir, or None (fail-safe).

    Verifies: (1) the dir exists, (2) after symlink resolution it lives directly
    under {home}/.claude/projects/ (so a symlink escape or collision is rejected).
    """
    projects_root = (home / ".claude" / "projects").resolve()
    candidate = home / ".claude" / "projects" / slugify_cwd(cwd) / "memory"
    if not candidate.is_dir():
        return None
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, ValueError):
        return None
    # resolved must be <projects_root>/<slug>/memory : exactly 2 levels deep.
    try:
        rel = resolved.relative_to(projects_root)
    except ValueError:
        return None
    if len(rel.parts) != 2 or rel.parts[1] != "memory":
        return None
    return candidate


def read_target(path: str) -> str | None:
    """Read a file, tolerating non-UTF-8 (errors='replace'). None on failure."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _target(path: Path, root: str, kind: str, category: str) -> dict[str, Any]:
    abspath = str(path)
    try:
        rel = os.path.relpath(abspath, root)
    except ValueError:
        rel = abspath
    return {"path": abspath, "rel": rel, "kind": kind, "category": category}


def collect_repo_targets(root: str) -> dict[str, Any]:
    """Collect repo-local instruction files by allowlist. Missing = skipped."""
    targets: list[dict[str, Any]] = []
    skipped: list[str] = []
    root_p = Path(root)
    for rel, kind in REPO_FILE_TARGETS:
        p = root_p / rel
        if p.is_file():
            targets.append(_target(p, root, kind, "instruction"))
        else:
            skipped.append(rel)
    for rel, kind in REPO_DIR_TARGETS:
        d = root_p / rel
        if d.is_dir():
            for md in sorted(d.glob("*.md")):
                if md.is_file():
                    targets.append(_target(md, root, kind, "instruction"))
        else:
            skipped.append(rel + "/")
    return {"targets": targets, "skipped": skipped}


def collect_targets(
    root: str, home: Path, cwd: str, include_global: bool = False
) -> dict[str, Any]:
    """Assemble all audit targets: repo instruction files + project memory,
    plus global files when opted in."""
    result = collect_repo_targets(root)
    targets = result["targets"]
    skipped = result["skipped"]

    memory_dir = resolve_memory_dir(cwd, home)
    if memory_dir is not None:
        for md in sorted(memory_dir.glob("*.md")):
            if md.is_file():
                targets.append(_target(md, root, "memory", "memory"))
    else:
        skipped.append("<project-memory>")

    if include_global:
        gclaude = home / ".claude" / "CLAUDE.md"
        if gclaude.is_file():
            targets.append(_target(gclaude, root, "global_claude_md", "instruction"))
        grules = home / ".claude" / "rules"
        if grules.is_dir():
            for md in sorted(grules.glob("*.md")):
                if md.is_file():
                    targets.append(_target(md, root, "global_rules", "instruction"))

    return {
        "targets": targets,
        "skipped": skipped,
        "memory_dir": str(memory_dir) if memory_dir else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover context-audit targets")
    parser.add_argument("root", nargs="?", default=".", help="Repo root (default cwd)")
    parser.add_argument("--include-global", action="store_true",
                        help="Also audit ~/.claude/CLAUDE.md and ~/.claude/rules")
    parser.add_argument("--output", default=None, help="Output file (default stdout)")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    result = collect_targets(root, Path.home(), root, include_global=args.include_global)

    js = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(js + "\n", encoding="utf-8")
    else:
        print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
