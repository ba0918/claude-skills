#!/usr/bin/env python3
"""Input collection for the brief skill.

Turns raw material into addressable units so the renderer can prove nothing
was dropped. Diffs become hunks, documents become sections, and the
repository state becomes a candidate list the reader chooses from.
"""

import os
import re

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")
PLUS_FILE = re.compile(r"^\+\+\+ b/(.+)$")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

DEFAULT_BRANCHES = ("main", "master", "develop")

PLANS_DIR = os.path.join(".agents", "artifacts", "plans")
HANDOFF_DIR = os.path.join(".agents", "artifacts", "handoff")


def split_diff_hunks(diff_text):
    """Split a unified diff into hunks carrying stable identifiers."""
    hunks = []
    path = None
    current = None

    for line in (diff_text or "").splitlines():
        header = DIFF_HEADER.match(line)
        if header:
            path = header.group(2)
            current = None
            continue

        plus_file = PLUS_FILE.match(line)
        if plus_file:
            path = plus_file.group(1)
            continue

        hunk = HUNK_HEADER.match(line)
        if hunk:
            current = {
                "id": "h%03d" % (len(hunks) + 1),
                "path": path or "",
                "header": line,
                "old_start": int(hunk.group(1)),
                "new_start": int(hunk.group(3)),
                "added": 0,
                "removed": 0,
                "body": "",
            }
            hunks.append(current)
            continue

        if current is None:
            continue

        current["body"] += line + "\n"
        if line.startswith("+"):
            current["added"] += 1
        elif line.startswith("-"):
            current["removed"] += 1

    return hunks


def _split_level(headings):
    """Pick the heading level that separates the document into sections."""
    counts = {}
    for level, _, _ in headings:
        counts[level] = counts.get(level, 0) + 1
    levels = sorted(counts)
    for level in levels:
        if counts[level] >= 2:
            return level
    # A lone top heading is the document title, not a section — go one deeper
    # so a single-section document still yields its section rather than itself.
    return levels[1] if len(levels) > 1 else levels[0]


def split_document_sections(text):
    """Split a document into its top-level sections, nesting deeper headings."""
    lines = (text or "").splitlines()
    headings = []
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2), index))
    if not headings:
        return []

    level = _split_level(headings)
    starts = [h for h in headings if h[0] == level]
    sections = []
    for order, (_, title, start) in enumerate(starts, start=1):
        end = len(lines)
        for other_level, _, other_start in headings:
            if other_start > start and other_level <= level:
                end = other_start
                break
        sections.append(
            {
                "id": "s%03d" % order,
                "title": title,
                "level": level,
                "start_line": start + 1,
                "end_line": end,
                "body": "\n".join(lines[start + 1 : end]).strip(),
            }
        )
    return sections


def resolve_base(runner):
    """Return the merge base against the first resolvable default branch."""
    for branch in DEFAULT_BRANCHES:
        code, out = runner(["merge-base", "HEAD", branch])
        if code == 0 and out.strip():
            return out.strip()
    return None


def _numstat_count(runner, args):
    code, out = runner(args)
    if code != 0:
        return 0
    return len([line for line in out.splitlines() if line.strip()])


def _latest_document(root, relative_dir):
    directory = os.path.join(root, relative_dir)
    if not os.path.isdir(directory):
        return None
    names = sorted(n for n in os.listdir(directory) if n.endswith(".md"))
    if not names:
        return None
    return os.path.join(directory, names[-1])


def scan_candidates(root, runner):
    """List the targets available right now, most concrete first.

    Session context is unconditional, so the result is never empty and the
    skill never has to answer that there is nothing to show.
    """
    candidates = []

    unstaged = _numstat_count(runner, ["diff", "--numstat"])
    if unstaged:
        candidates.append(
            {"kind": "unstaged", "label": "未ステージ差分", "count": unstaged, "ref": None}
        )

    staged = _numstat_count(runner, ["diff", "--cached", "--numstat"])
    if staged:
        candidates.append(
            {"kind": "staged", "label": "ステージ済み差分", "count": staged, "ref": None}
        )

    base = resolve_base(runner)
    if base:
        ref = "%s..HEAD" % base
        branch = _numstat_count(runner, ["diff", "--numstat", ref])
        if branch:
            candidates.append(
                {"kind": "branch", "label": "ブランチ差分", "count": branch, "ref": ref}
            )

    plan = _latest_document(root, PLANS_DIR)
    if plan:
        candidates.append(
            {"kind": "plan", "label": "直近の実装計画", "count": 1, "ref": plan}
        )

    handoff = _latest_document(root, HANDOFF_DIR)
    if handoff:
        candidates.append(
            {"kind": "handoff", "label": "直近の引き継ぎ", "count": 1, "ref": handoff}
        )

    candidates.append(
        {"kind": "discussion", "label": "今の会話", "count": 1, "ref": None}
    )
    return candidates
