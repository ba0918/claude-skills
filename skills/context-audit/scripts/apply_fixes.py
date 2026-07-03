#!/usr/bin/env python3
"""
context-audit: deterministic AUTO_FIX application (pure functions).

Given a file's content + the findings targeting it, produce the new content.
Only AUTO_FIX findings with a fix_action are applied. Two fix kinds:
  - CA-S001 path typo  : replace the reference inside markdown links / backticks.
  - CA-M001 frontmatter: normalize a key line *inside the frontmatter block only*
                         (body bytes are guaranteed unchanged).

All replacements are idempotent: applying the result again is a no-op. The
replacement strings are computed by static_checks.py (pure) — this module never
synthesizes new content, it only substitutes old -> new.
"""

import argparse
import json
import sys
from pathlib import Path


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    """Return (start, end) line indices of the frontmatter body (exclusive of
    the '---' fences), or None if there is no closed block."""
    if not lines or lines[0].strip() != "---":
        return None
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            return (1, j)
    return None


def _apply_frontmatter(content: str, old: str, new: str) -> str:
    lines = content.split("\n")
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return content
    start, end = bounds
    for i in range(start, end):
        # CRLF tolerance: match with or without a trailing '\r' and preserve
        # the original terminator (no line-ending churn).
        if lines[i] == old:
            lines[i] = new
            break  # first matching frontmatter line only; body untouched
        if lines[i] == old + "\r":
            lines[i] = new + "\r"
            break
    return "\n".join(lines)


def _apply_ref(content: str, old: str, new: str) -> str:
    content = content.replace(f"]({old})", f"]({new})")
    content = content.replace(f"`{old}`", f"`{new}`")
    return content


def _apply_one(content: str, finding: dict) -> str:
    if finding.get("action") != "AUTO_FIX":
        return content
    fa = finding.get("fix_action")
    if not isinstance(fa, dict) or "old" not in fa or "new" not in fa:
        return content
    old, new = fa["old"], fa["new"]
    if old == new:
        return content
    if str(finding.get("id", "")).startswith("CA-M001"):
        return _apply_frontmatter(content, old, new)
    return _apply_ref(content, old, new)


def apply_fixes(content: str, findings: list[dict]) -> str:
    """Apply every AUTO_FIX finding to content, in order. Idempotent."""
    for f in findings:
        content = _apply_one(content, f)
    return content


def group_by_path(findings: list[dict]) -> dict[str, list[dict]]:
    """Group AUTO_FIX findings by their target file path."""
    groups: dict[str, list[dict]] = {}
    for f in findings:
        if f.get("action") != "AUTO_FIX":
            continue
        fa = f.get("fix_action") or {}
        path = fa.get("path")
        if path:
            groups.setdefault(path, []).append(f)
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply context-audit AUTO_FIX findings")
    parser.add_argument("findings_json", help="static_checks.py output (path or '-')")
    parser.add_argument("--write", action="store_true", help="Write files in place (default: dry-run diff count)")
    args = parser.parse_args()

    raw = sys.stdin.read() if args.findings_json == "-" else Path(args.findings_json).read_text(encoding="utf-8")
    data = json.loads(raw)
    findings = data["findings"] if isinstance(data, dict) else data
    groups = group_by_path(findings)

    changed = 0
    for path, fs in sorted(groups.items()):
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError:
            continue
        new_content = apply_fixes(content, fs)
        if new_content != content:
            changed += 1
            if args.write:
                Path(path).write_text(new_content, encoding="utf-8")
    print(json.dumps({"files_changed": changed, "auto_fix_files": len(groups)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
