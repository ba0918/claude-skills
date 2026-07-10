#!/usr/bin/env python3
"""
skill-interface-audit: pure-function SI-S* rule engine.

Each rule is `check(targets, ctx) -> list[Finding]` registered in RULES.
Adding a rule = add function + register + test (Open-Closed).

Finding schema:
  id, severity, action, where(skill:file:line), what, why, how, fix_draft
"""

import argparse
import json
import os
import re
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Finding helpers
# ---------------------------------------------------------------------------

CANONICAL_FIELDS = ("id", "severity", "action", "where", "what", "why", "how", "fix_draft")


def make_finding(rule_id, severity, action, where, what, why, how, fix_draft=None):
    return {"id": rule_id, "severity": severity, "action": action, "where": where,
            "what": what, "why": why, "how": how, "fix_draft": fix_draft}


def _assign_ids(findings: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for f in findings:
        base = f["id"]
        counts[base] = counts.get(base, 0) + 1
    multi = {k for k, v in counts.items() if v > 1}
    counters: dict[str, int] = {}
    for f in findings:
        base = f["id"]
        if base in multi:
            counters[base] = counters.get(base, 0) + 1
            f["id"] = f"{base}-{counters[base]}"
    return findings


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\]\(([^)\s#]+\.md[^)]*)\)")
_FENCED_BLOCK = re.compile(r"^(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"`{1,2}[^`\n]+`{1,2}")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _strip_frontmatter(content: str) -> str:
    m = _FRONTMATTER_RE.match(content)
    return content[m.end():] if m else content


def _extract_frontmatter(content: str) -> str:
    m = _FRONTMATTER_RE.match(content)
    return m.group(1) if m else ""


def _extract_description(content: str) -> str:
    fm = _extract_frontmatter(content)
    for line in fm.split("\n"):
        if line.startswith("description:"):
            return line[len("description:"):].strip()
    return ""


def _lines_outside_code_blocks(content: str) -> list[tuple[int, str]]:
    lines = content.split("\n")
    result = []
    in_fence = False
    for i, line in enumerate(lines, 1):
        if _FENCED_BLOCK.match(line.strip()):
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append((i, line))
    return result


def _strip_inline_code(line: str) -> str:
    return _INLINE_CODE.sub("", line)


def _is_quote_line(line: str) -> bool:
    return line.strip().startswith(">")


def _is_heading(line: str) -> bool:
    return line.strip().startswith("#")


def _startswith_dir(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + os.sep)


# ---------------------------------------------------------------------------
# SI-S001: Reference chain depth
# ---------------------------------------------------------------------------

def _extract_md_links(content: str) -> list[tuple[str, int]]:
    result = []
    for lineno, line in _lines_outside_code_blocks(content):
        for m in _LINK_RE.finditer(line):
            target = m.group(1).split("#")[0]
            if target:
                result.append((target, lineno))
    return result


def check_si_s001(targets: list[dict], ctx: dict) -> list[dict]:
    findings = []
    for t in targets:
        skill_md = t.get("skill_md_content", "")
        skill_dir = t.get("skill_dir", "")
        skill_name = t.get("name", "")
        refs_dir = os.path.normpath(os.path.join(skill_dir, "references"))
        shared_dir = os.path.normpath(
            os.path.join(ctx["root"], "skills", "shared", "references"))

        first_level_refs = []
        for link, lineno in _extract_md_links(skill_md):
            resolved = os.path.normpath(os.path.join(skill_dir, link))
            if _startswith_dir(resolved, refs_dir):
                first_level_refs.append((link, lineno, resolved))

        for ref_link, ref_lineno, ref_path in first_level_refs:
            if not os.path.isfile(ref_path):
                continue
            try:
                with open(ref_path, encoding="utf-8", errors="replace") as f:
                    ref_content = f.read()
            except OSError:
                continue

            for second_link, second_lineno in _extract_md_links(ref_content):
                second_resolved = os.path.normpath(
                    os.path.join(os.path.dirname(ref_path), second_link))
                if _startswith_dir(second_resolved, shared_dir):
                    continue
                # A5 fix: flag ANY non-shared md link from first-level refs
                findings.append(make_finding(
                    rule_id="SI-S001",
                    severity="WARN",
                    action="REPORT_ONLY",
                    where=f"{skill_name}:{os.path.basename(ref_path)}:{second_lineno}",
                    what=f"参照チェーン深度超過: {os.path.basename(ref_path)} -> {second_link}",
                    why="Progressive disclosure は1階層まで (skill-authoring #4)",
                    how="二次参照を shared/references/ に移動するか、SKILL.md から直接リンクする",
                ))
    return findings


# ---------------------------------------------------------------------------
# SI-S002: Description workflow summary leakage
# ---------------------------------------------------------------------------

_PHASE_STEP_RE = re.compile(r"Phase\s*\d|Step\s*\d", re.IGNORECASE)
_NUMBERED_LIST_RE = re.compile(r"\d+[.)]\s")
_PROCEDURE_JA_RE = re.compile(r"まず.*次に|最初に.*その後")
_ARROW_CHAIN_RE = re.compile(r"→.*→")


def check_si_s002(targets: list[dict], ctx: dict) -> list[dict]:
    findings = []
    for t in targets:
        desc = t.get("description", "")
        skill_name = t.get("name", "")
        if not desc:
            continue

        violations = []
        if _PHASE_STEP_RE.search(desc):
            violations.append("Phase/Step 番号")
        if _NUMBERED_LIST_RE.search(desc):
            violations.append("番号付きリスト")
        if _PROCEDURE_JA_RE.search(desc):
            violations.append("手順接続詞")
        if _ARROW_CHAIN_RE.search(desc):
            violations.append("→ 連鎖")

        if violations:
            findings.append(make_finding(
                rule_id="SI-S002",
                severity="WARN",
                action="REPORT_ONLY",
                where=f"{skill_name}:SKILL.md:frontmatter",
                what=f"description にワークフロー要約が混入: {', '.join(violations)}",
                why="description は「何をするか + いつ使うか」に留める (skill-authoring frontmatter)",
                how="Phase/Step 番号・手順記述を削除し、能力とトリガー語のみにする",
            ))
    return findings


# ---------------------------------------------------------------------------
# SI-S003: Prose bloat
# ---------------------------------------------------------------------------

_WORKFLOW_KEYWORDS = {"workflow", "phase", "step", "フロー", "ワークフロー"}


def _classify_heading(heading_text: str) -> str:
    lower = heading_text.lower().strip().lstrip("#").strip()
    for kw in _WORKFLOW_KEYWORDS:
        if kw in lower:
            return "workflow"
    return "prose"


def check_si_s003(targets: list[dict], ctx: dict) -> list[dict]:
    findings = []
    for t in targets:
        content = t.get("skill_md_content", "")
        skill_name = t.get("name", "")
        body = _strip_frontmatter(content)
        if not body.strip():
            continue

        lines = body.split("\n")
        total = len(lines)
        if total == 0:
            continue

        current_h2_class = "prose"
        workflow_lines = 0
        prose_lines = 0

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                current_h2_class = _classify_heading(stripped)
            if current_h2_class == "workflow":
                workflow_lines += 1
            else:
                prose_lines += 1

        ratio = prose_lines / total if total > 0 else 0
        if ratio > 0.6:
            findings.append(make_finding(
                rule_id="SI-S003",
                severity="INFO",
                action="REPORT_ONLY",
                where=f"{skill_name}:SKILL.md",
                what=f"prose 肥大: {prose_lines}/{total} 行 ({ratio:.0%})",
                why="Process over prose (skill-authoring #1)",
                how="知識の羅列は references/ に逃がし、SKILL.md はワークフローに徹する",
            ))
    return findings


# ---------------------------------------------------------------------------
# SI-S004: Platform-specific tool vocabulary
# ---------------------------------------------------------------------------

_TOOL_NAMES_SORTED = sorted([
    "Edit", "Write", "Read", "Bash", "Agent", "Workflow",
    "WebFetch", "WebSearch", "Grep", "Glob", "LSP", "NotebookEdit",
])

_TOOL_JA_RE = re.compile(
    r"(" + "|".join(re.escape(t) for t in _TOOL_NAMES_SORTED) + r")\s*ツール"
)

_MODEL_RE = re.compile(
    r"claude-(?:opus|sonnet|haiku)-[\d.*]+|gpt-[\d.]+|o1-[\d.]+",
    re.IGNORECASE,
)


def _is_at_sentence_start(line: str, match_start: int) -> bool:
    if match_start == 0:
        return True
    before = line[:match_start].rstrip()
    if not before:
        return True
    if before[-1] in ".!?。！？:：":
        return True
    m = re.match(r"^\s*\d+[.)]\s", line)
    if m and match_start <= m.end():
        return True
    return False


def check_si_s004(targets: list[dict], ctx: dict) -> list[dict]:
    findings = []
    for t in targets:
        skill_name = t.get("name", "")
        skill_dir = t.get("skill_dir", "")

        files_to_check = []
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        if os.path.isfile(skill_md_path):
            files_to_check.append(("SKILL.md", t.get("skill_md_content", "")))
        refs_dir = os.path.join(skill_dir, "references")
        if os.path.isdir(refs_dir):
            for fname in sorted(os.listdir(refs_dir)):
                if fname.endswith(".md"):
                    fpath = os.path.join(refs_dir, fname)
                    if os.path.islink(fpath):
                        continue
                    try:
                        with open(fpath, encoding="utf-8", errors="replace") as f:
                            files_to_check.append((f"references/{fname}", f.read()))
                    except OSError:
                        pass

        for relpath, content in files_to_check:
            for lineno, line in _lines_outside_code_blocks(content):
                if _is_quote_line(line):
                    continue
                if _is_heading(line):
                    continue

                clean = _strip_inline_code(line)

                # Track positions consumed by JA pattern to avoid double-counting
                ja_consumed: set[int] = set()

                for m in _TOOL_JA_RE.finditer(clean):
                    for pos in range(m.start(), m.end()):
                        ja_consumed.add(pos)
                    findings.append(make_finding(
                        rule_id="SI-S004",
                        severity="WARN", action="NEEDS_JUDGMENT",
                        where=f"{skill_name}:{relpath}:{lineno}",
                        what=f"プラットフォーム固有ツール語彙: {m.group(0)}",
                        why="AGENTS.md: 特定プラットフォームのツール API 名を避ける",
                        how="プラットフォーム非依存の表現に置換する",
                    ))

                for tool in _TOOL_NAMES_SORTED:
                    pattern = re.compile(r"\b" + re.escape(tool) + r"\b")
                    for tm in pattern.finditer(clean):
                        if any(pos in ja_consumed for pos in range(tm.start(), tm.end())):
                            continue
                        if tool == "LSP":
                            context_after = clean[tm.end():tm.end() + 10].strip()
                            if any(kw in context_after for kw in
                                   ["準拠", "サポート", "対応", "プロトコル"]):
                                continue
                        if _is_at_sentence_start(clean, tm.start()):
                            continue
                        if tm.start() > 0 and clean[tm.start() - 1] in "/#.":
                            continue
                        findings.append(make_finding(
                            rule_id="SI-S004",
                            severity="WARN", action="NEEDS_JUDGMENT",
                            where=f"{skill_name}:{relpath}:{lineno}",
                            what=f"プラットフォーム固有ツール語彙: {tool}",
                            why="AGENTS.md: 特定プラットフォームのツール API 名を避ける",
                            how="プラットフォーム非依存の表現に置換する",
                        ))

                for mm in _MODEL_RE.finditer(clean):
                    findings.append(make_finding(
                        rule_id="SI-S004",
                        severity="WARN", action="NEEDS_JUDGMENT",
                        where=f"{skill_name}:{relpath}:{lineno}",
                        what=f"モデル固有名: {mm.group(0)}",
                        why="AGENTS.md: 特定プラットフォームのモデル名を避ける",
                        how="「高性能モデル」「軽量モデル」等の表現に置換する",
                    ))

    return findings


# ---------------------------------------------------------------------------
# RULES registry
# ---------------------------------------------------------------------------

RULES: dict[str, dict[str, Any]] = {
    "SI-S001": {"category": "structural", "severity": "WARN",
                "action": "REPORT_ONLY", "fn": check_si_s001},
    "SI-S002": {"category": "structural", "severity": "WARN",
                "action": "REPORT_ONLY", "fn": check_si_s002},
    "SI-S003": {"category": "structural", "severity": "INFO",
                "action": "REPORT_ONLY", "fn": check_si_s003},
    "SI-S004": {"category": "structural", "severity": "WARN",
                "action": "NEEDS_JUDGMENT", "fn": check_si_s004},
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def collect_targets(skills_dir: str) -> list[dict]:
    targets = []
    if not os.path.isdir(skills_dir):
        return targets
    for name in sorted(os.listdir(skills_dir)):
        if name == "shared":
            continue
        skill_dir = os.path.join(skills_dir, name)
        if os.path.islink(skill_dir):
            continue
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        try:
            with open(skill_md, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        targets.append({
            "name": name,
            "skill_dir": skill_dir,
            "skill_md_content": content,
            "description": _extract_description(content),
        })
    return targets


def run_checks(targets: list[dict], ctx: dict) -> list[dict]:
    findings = []
    for rid in sorted(RULES):
        fn = RULES[rid]["fn"]
        findings.extend(fn(targets, ctx))
    return _assign_ids(findings)


def main():
    parser = argparse.ArgumentParser(description="SI-S* static checks")
    parser.add_argument("--skills-dir", default="skills")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=None)
    parser.add_argument("--skill", nargs="*", default=None,
                        help="Audit specific skill(s)")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    targets = collect_targets(os.path.join(root, args.skills_dir))
    if args.skill:
        skill_set = set(args.skill)
        targets = [t for t in targets if t["name"] in skill_set]

    ctx = {"root": root}
    findings = run_checks(targets, ctx)

    output = json.dumps(findings, ensure_ascii=False, indent=2)
    if args.output:
        d = os.path.dirname(args.output)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"{len(findings)} findings written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
