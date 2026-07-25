#!/usr/bin/env python3
"""Input collection for the brief skill.

Turns raw material into addressable units so the renderer can prove nothing
was dropped. Diffs become hunks, documents become sections, and the
repository state becomes a candidate list the reader chooses from.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")
PLUS_FILE = re.compile(r"^\+\+\+ b/(.+)$")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_ITEM = re.compile(r"^[-*+]\s+(.+?)\s*$")
ANY_ITEM = re.compile(r"^(?:[-*+]|\d+\.)\s+(.+?)\s*$")

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


def _split_list_items(lines):
    """Split a body into its unindented list items.

    A document whose headings do not divide it is still divided — by its
    bullets. Without this the finest addressable unit is the whole document,
    and nothing can be withheld from the page without withholding all of it.
    """
    starts = [
        (index, match.group(1))
        for index, match in ((i, LIST_ITEM.match(l)) for i, l in enumerate(lines))
        if match
    ]
    items = []
    for order, (start, title) in enumerate(starts, start=1):
        end = starts[order][0] if order < len(starts) else len(lines)
        items.append(
            {
                "id": "b%03d" % order,
                "title": title.strip(),
                "unit": "item",
                "start_line": start + 1,
                "end_line": end,
                "body": "\n".join(lines[start:end]).strip(),
            }
        )
    return items


def split_document_sections(text):
    """Split a document into its top-level sections, nesting deeper headings.

    Falls back to list items when the headings fail to divide the document,
    which is the shape most memos take: one title and a run of bullets.
    """
    lines = (text or "").splitlines()
    headings = []
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2), index))
    if not headings:
        return _split_list_items(lines)

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
                "unit": "section",
                "level": level,
                "start_line": start + 1,
                "end_line": end,
                "body": "\n".join(lines[start + 1 : end]).strip(),
            }
        )
    if len(sections) > 1:
        return sections
    # One section is the document itself, not a division of it. Go to the
    # bullets rather than hand back a universe of size one.
    items = _split_list_items(lines)
    return items if len(items) > 1 else sections


def split_open_items(text):
    """Every item a state document lists, bulleted or numbered.

    The orientation view checks that no open item silently left the page, and
    that check needs the list of items to check against. Nothing produced it
    before, so the one view meant to answer "what is left" was the one view
    whose input had to be assembled by hand.
    """
    items = []
    for line in (text or "").splitlines():
        match = ANY_ITEM.match(line)
        if match:
            items.append(
                {
                    "id": "o%03d" % (len(items) + 1),
                    "title": match.group(1).strip(),
                    "unit": "item",
                }
            )
    return items


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


def _document_detail(path):
    """A line that tells two documents apart: name, size, and what it is about.

    Without this every document candidate reports `count: 1` and the choice
    offered to a human is between things that look identical, so whoever
    presents the list has to go gather this themselves — differently each time.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return os.path.basename(path)
    title = ""
    for line in lines:
        match = HEADING.match(line)
        if match:
            title = match.group(2)
            break
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    parts = [os.path.basename(path), "%d 行" % len(lines), stamp]
    if title:
        parts.append(title)
    return " / ".join(parts)


def scan_candidates(root, runner):
    """List the targets available right now, most concrete first.

    Session context is unconditional, so the result is never empty and the
    skill never has to answer that there is nothing to show.
    """
    candidates = []

    unstaged = _numstat_count(runner, ["diff", "--numstat"])
    if unstaged:
        candidates.append(
            {
                "kind": "unstaged",
                "label": "未ステージ差分",
                "count": unstaged,
                "detail": "%d ファイル" % unstaged,
                "ref": None,
            }
        )

    staged = _numstat_count(runner, ["diff", "--cached", "--numstat"])
    if staged:
        candidates.append(
            {
                "kind": "staged",
                "label": "ステージ済み差分",
                "count": staged,
                "detail": "%d ファイル" % staged,
                "ref": None,
            }
        )

    base = resolve_base(runner)
    if base:
        ref = "%s..HEAD" % base
        branch = _numstat_count(runner, ["diff", "--numstat", ref])
        if branch:
            candidates.append(
                {
                    "kind": "branch",
                    "label": "ブランチ差分",
                    "count": branch,
                    "detail": "%d ファイル / %s" % (branch, ref),
                    "ref": ref,
                }
            )

    plan = _latest_document(root, PLANS_DIR)
    if plan:
        candidates.append(
            {
                "kind": "plan",
                "label": "直近の実装計画",
                "count": 1,
                "detail": _document_detail(plan),
                "ref": plan,
            }
        )

    handoff = _latest_document(root, HANDOFF_DIR)
    if handoff:
        candidates.append(
            {
                "kind": "handoff",
                "label": "直近の引き継ぎ",
                "count": 1,
                "detail": _document_detail(handoff),
                "ref": handoff,
            }
        )

    candidates.append(
        {
            "kind": "discussion",
            "label": "今の会話",
            "count": 1,
            "detail": "ファイル入力なし。そのまま解説できる",
            "ref": None,
        }
    )
    return candidates


# ---------------------------------------------------------------------------
# CLI
#
# The skill body drives this through a shell, so every step it describes has a
# command behind it. Output is JSON on stdout: the caller is a language model
# building the brief model, not a person reading a table.
# ---------------------------------------------------------------------------

DIFF_ARGS = {
    "unstaged": ["diff"],
    "staged": ["diff", "--cached"],
    "branch": ["diff"],
}


def git_runner(root):
    def run(args):
        result = subprocess.run(
            ["git"] + args, cwd=root, capture_output=True, text=True
        )
        return result.returncode, result.stdout

    return run


def _emit(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="brief input collection")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("candidates", help="what can be explained right now")
    scan.add_argument("--repo", default=".")

    hunks = sub.add_parser("hunks", help="split a diff into addressable hunks")
    hunks.add_argument("--repo", default=".")
    hunks.add_argument("--source", choices=sorted(DIFF_ARGS), default="unstaged")
    hunks.add_argument("--ref", help="revision range, required for --source branch")

    sections = sub.add_parser("sections", help="split a document into sections")
    sections.add_argument("--file", required=True)

    openitems = sub.add_parser("open-items", help="list what a state document leaves open")
    openitems.add_argument("--file", required=True)

    args = parser.parse_args(argv)

    if args.command == "candidates":
        _emit(scan_candidates(args.repo, git_runner(args.repo)))
        return 0

    if args.command == "hunks":
        command = list(DIFF_ARGS[args.source])
        if args.source == "branch":
            if not args.ref:
                parser.error("--source branch needs --ref")
            command.append(args.ref)
        code, out = git_runner(args.repo)(command)
        if code != 0:
            print("git diff が失敗した: %s" % " ".join(command), file=sys.stderr)
            return 1
        collected = split_diff_hunks(out)
        _emit({"hunks": [h["id"] for h in collected], "detail": collected})
        return 0

    with open(args.file, encoding="utf-8") as handle:
        text = handle.read()
    if args.command == "open-items":
        collected = split_open_items(text)
        _emit({"open_items": [i["id"] for i in collected], "detail": collected})
        return 0
    collected = split_document_sections(text)
    _emit({"sections": [s["id"] for s in collected], "detail": collected})
    return 0


if __name__ == "__main__":
    sys.exit(main())
