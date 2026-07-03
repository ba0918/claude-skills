#!/usr/bin/env python3
"""
context-audit: pure-function CA-* rule engine.

Each rule is a pure function `check(targets, ctx) -> list[Finding]` registered
in RULES. static_checks is a thin dispatcher: adding a rule = add function +
register + test, without touching existing rules (Open-Closed). The catalog
(references/rule-catalog.md) and RULES are kept in sync by test_catalog_sync.py.

Finding schema (every rule, every finding):
  id, severity(BLOCK/WARN/INFO/PASS), action(AUTO_FIX/NEEDS_JUDGMENT/REPORT_ONLY),
  where(file:line), what, why, how, fix_action({old,new,path} | None)

Security invariant: every string field (incl. line-context) is passed through
mask_secrets before serialization, so no detected secret value ever reaches the
findings JSON — enforced centrally in finalize_findings() and covered by tests.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared", "scripts")
)
import secret_detect  # noqa: E402

# ---------------------------------------------------------------------------
# Finding helpers
# ---------------------------------------------------------------------------

CANONICAL_FINDING_FIELDS = ("id", "severity", "action", "where", "what", "why",
                            "how", "fix_action")


def make_finding(id, severity, action, where, what, why, how, fix_action=None):
    return {"id": id, "severity": severity, "action": action, "where": where,
            "what": what, "why": why, "how": how, "fix_action": fix_action}


def validate_finding_schema(f: dict) -> list[str]:
    """Return the list of required fields missing from a finding (empty = ok)."""
    return [k for k in CANONICAL_FINDING_FIELDS if k not in f]


def finalize_findings(findings: list[dict]) -> list[dict]:
    """Mask secrets in every string field (and fix_action) of every finding."""
    out = []
    for f in findings:
        g = dict(f)
        for k in ("where", "what", "why", "how"):
            if isinstance(g.get(k), str):
                g[k] = secret_detect.mask_secrets(g[k])
        fa = g.get("fix_action")
        if isinstance(fa, dict):
            # 'path' is a routing field (apply_fixes opens the file by it);
            # masking it (home_path pattern matches /home/... , /Users/...)
            # would silently disable AUTO_FIX. Only content fields are masked.
            g["fix_action"] = {
                kk: (secret_detect.mask_secrets(vv)
                     if kk != "path" and isinstance(vv, str) else vv)
                for kk, vv in fa.items()
            }
        out.append(g)
    return out


# ---------------------------------------------------------------------------
# Shared text helpers
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\]\(([^)\s#]+)\)")
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_TIMESTAMP = re.compile(r"^\d{8,}")
_PATHISH = re.compile(r"^[A-Za-z0-9_./-]+$")


def _is_pathish(ref: str) -> bool:
    if not _PATHISH.match(ref):
        return False
    if ref.startswith(("http://", "https://", "mailto:", "#", "/")):
        return False
    if "{" in ref or "*" in ref:
        return False
    if _TIMESTAMP.match(os.path.basename(ref)):
        return False
    if "/" not in ref:
        return False
    has_ext = bool(re.search(r"\.[A-Za-z0-9]+$", os.path.basename(ref)))
    return has_ext or ref.endswith("/")


def _extract_path_refs(content: str) -> list[tuple[str, int, str]]:
    """Extract (path-ref, line_no, source) triples. source is 'link' for
    markdown link targets (carry intent) or 'backtick' for code spans
    (often illustrative prose — consumers may apply stricter filters)."""
    refs: list[tuple[str, int, str]] = []
    for i, line in enumerate(content.splitlines(), start=1):
        for m in _LINK_RE.finditer(line):
            ref = m.group(1)
            if _is_pathish(ref):
                refs.append((ref, i, "link"))
        for m in _BACKTICK_RE.finditer(line):
            ref = m.group(1).strip()
            if _is_pathish(ref):
                refs.append((ref, i, "backtick"))
    return refs


def _backtick_ref_is_anchored(root: str, ref: str) -> bool:
    """False-positive filter for backtick spans (precision over recall):
    only treat a backtick ref as checkable when it has a file extension
    (directory-only mentions like `references/` are prose) AND its parent
    directory exists in the repo (anchored to real structure; a missing
    parent means illustrative shorthand like `skill-improve/collect.py`)."""
    if not re.search(r"\.[A-Za-z0-9]+$", os.path.basename(ref)):
        return False
    parent_abs = os.path.normpath(os.path.join(root, os.path.dirname(ref)))
    return os.path.isdir(parent_abs)


def _ref_exists(root: str, ref: str) -> bool:
    p = os.path.normpath(os.path.join(root, ref))
    return os.path.exists(p)


def _edit_distance_le_1(a: str, b: str) -> bool:
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:  # single substitution
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    # one insertion/deletion: make a the shorter
    if la > lb:
        a, b = b, a
    i = j = 0
    edited = False
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            if edited:
                return False
            edited = True
            j += 1
        else:
            i += 1
            j += 1
    return True


def _autofix_candidate(root: str, ref: str) -> str | None:
    """A unique existing sibling whose basename is edit-distance <=1 from ref."""
    parent = os.path.dirname(ref)
    parent_abs = os.path.normpath(os.path.join(root, parent))
    if not os.path.isdir(parent_abs):
        return None
    base = os.path.basename(ref)
    cands = [
        name for name in os.listdir(parent_abs)
        if _edit_distance_le_1(base, name)
        and os.path.exists(os.path.join(parent_abs, name))
    ]
    if len(cands) == 1:
        return os.path.join(parent, cands[0]).replace(os.sep, "/") if parent else cands[0]
    return None


def _line_of(content: str, needle: str) -> int:
    for i, line in enumerate(content.splitlines(), start=1):
        if needle in line:
            return i
    return 1


# ---------------------------------------------------------------------------
# Frontmatter (regex-based, no PyYAML — mirrors validate_repo.py)
# ---------------------------------------------------------------------------

def parse_frontmatter_lines(content: str) -> list[tuple[str, str, str]] | None:
    """Return [(key, value, raw_line)] for top-level frontmatter keys, or None
    if there is no closed frontmatter block."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", line)
        if m:
            out.append((m.group(1), m.group(2).strip(), line))
    return None  # unclosed


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def check_ca_s001(targets, ctx):
    findings = []
    root = ctx["root"]
    for t in targets:
        if t["category"] != "instruction":
            continue
        for ref, line, source in _extract_path_refs(t["content"]):
            if source == "backtick" and not _backtick_ref_is_anchored(root, ref):
                continue  # prose example, not a checkable reference (fail-safe)
            if _ref_exists(root, ref):
                continue
            cand = _autofix_candidate(root, ref)
            where = f"{t['rel']}:{line}"
            if cand is not None:
                findings.append(make_finding(
                    "CA-S001", "WARN", "AUTO_FIX", where,
                    what=f"存在しないパス参照 `{ref}`（近傍に一意候補あり）",
                    why="指示ファイルが実在しないファイルを指すと LLM が誤誘導される",
                    how=f"`{ref}` を `{cand}` に置換する",
                    fix_action={"path": t["path"], "old": ref, "new": cand}))
            else:
                findings.append(make_finding(
                    "CA-S001", "WARN", "NEEDS_JUDGMENT", where,
                    what=f"存在しないパス参照 `{ref}`",
                    why="指示ファイルが実在しないファイルを指すと LLM が誤誘導される",
                    how="正しいパスに修正するか、参照を削除するか判断する"))
    return findings


_SKILL_DIR_REF = re.compile(r"\b((?:codex-)?skills)/([a-z][a-z0-9-]*)/")


def check_ca_s002(targets, ctx):
    findings = []
    known = ctx["skill_names"]
    for t in targets:
        if t["category"] != "instruction":
            continue
        for i, line in enumerate(t["content"].splitlines(), start=1):
            for m in _SKILL_DIR_REF.finditer(line):
                name = m.group(2)
                if name == "shared" or name in known:
                    continue
                findings.append(make_finding(
                    "CA-S002", "WARN", "NEEDS_JUDGMENT", f"{t['rel']}:{i}",
                    what=f"存在しないスキルディレクトリ参照 `{m.group(1)}/{name}/`",
                    why="実在しないスキルへの言及は陳腐化した指示のサイン",
                    how="スキル名の typo を修正するか、言及を削除する"))
    return findings


_UNSAFE_PATTERNS = [
    ("確認省略", re.compile(r"確認(?:なし|せず|を省略|不要|を飛ば)")),
    ("破壊的操作", re.compile(r"rm\s+-rf|--force\b|--no-verify\b|force\s*push|強制(?:削除|プッシュ|的に削除)")),
    ("無条件許可", re.compile(r"無条件で|without confirmation|skip confirmation|auto-?approve|bypass(?:ing)?\s+permission", re.IGNORECASE)),
]


def check_ca_u001(targets, ctx):
    findings = []
    for t in targets:
        for i, line in enumerate(t["content"].splitlines(), start=1):
            for label, pat in _UNSAFE_PATTERNS:
                if pat.search(line):
                    findings.append(make_finding(
                        "CA-U001", "WARN", "REPORT_ONLY", f"{t['rel']}:{i}",
                        what=f"確認省略・破壊的操作を許可する語彙（{label}）: {line.strip()}",
                        why="無確認・破壊的操作の許可は事故リスクを高める。意図を要確認",
                        how="意図的なら維持、そうでなければ確認ステップを明記する"))
                    break
    return findings


_CLAUDE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit", "TodoWrite")
_CLAUDE_TOOL_RE = re.compile(
    r"`(" + "|".join(_CLAUDE_TOOLS) + r")`|\b(" + "|".join(_CLAUDE_TOOLS) + r")\s+tool\b"
)


def check_ca_d001(targets, ctx):
    findings = []
    for t in targets:
        if t["kind"] != "agents_md":
            continue
        for i, line in enumerate(t["content"].splitlines(), start=1):
            m = _CLAUDE_TOOL_RE.search(line)
            if m:
                tool = m.group(1) or m.group(2)
                findings.append(make_finding(
                    "CA-D001", "INFO", "REPORT_ONLY", f"{t['rel']}:{i}",
                    what=f"AGENTS.md に Claude 専用ツール語彙 `{tool}` が混入",
                    why="Codex は apply_patch/shell を使う。Claude ツール名はクロスツール乖離",
                    how="Codex ネイティブのツール名（apply_patch 等）に置換を検討"))
    return findings


def check_ca_d002(targets, ctx):
    if ctx.get("has_validate_repo"):
        return []  # mechanically deconflict: validate_repo.py owns coverage
    findings = []
    known = ctx["skill_names"]
    if not known:
        return []
    blob = "\n".join(t["content"] for t in targets if t["category"] == "instruction")
    for name in sorted(known):
        # word-boundary match: 'planning' must not count as a mention of 'plan'
        # (skill names may contain '-', so boundaries exclude [A-Za-z0-9-])
        mention = re.search(
            r"(?<![A-Za-z0-9-])" + re.escape(name) + r"(?![A-Za-z0-9-])", blob)
        if not mention:
            findings.append(make_finding(
                "CA-D002", "WARN", "NEEDS_JUDGMENT", "<instruction-files>:0",
                what=f"スキル `{name}` が指示ファイルに記載されていない",
                why="スキル一覧の記載漏れは指示層の陳腐化。意図的省略の可能性もある",
                how="スキル表に追記するか、意図的省略なら無視する"))
    return findings


# --- CA-C001 contradiction candidates (pure over-generation) ---------------

_PROHIBIT = re.compile(r"するな|しない(?:こと)?|禁止|してはならない|べきでない|never\b|don't\b|do not\b|avoid\b|must not\b", re.IGNORECASE)
_ALLOW = re.compile(r"してよい|してもよい|許可|するべき|すること(?:$|。)|always\b|must\b|should\b|allowed\b", re.IGNORECASE)
_ASCII_TOK = re.compile(r"[a-z0-9]{2,}")
_CJK_RUN = re.compile(r"[぀-ヿ一-鿿]+")
_POLARITY_TOKENS = {"する", "しない", "してよい", "するな", "こと", "must", "not", "should",
                    "never", "avoid", "always", "don", "allowed"}


def _subject_tokens(line: str) -> set[str]:
    toks = set(_ASCII_TOK.findall(line.lower()))
    for run in _CJK_RUN.findall(line):
        for i in range(len(run) - 1):
            toks.add(run[i:i + 2])
    return {t for t in toks if t not in _POLARITY_TOKENS}


def _polarity(line: str) -> str | None:
    p = bool(_PROHIBIT.search(line))
    a = bool(_ALLOW.search(line))
    if p and not a:
        return "prohibit"
    if a and not p:
        return "allow"
    return None


def _bucket_claims(claims: list[tuple]) -> dict[str, list[int]]:
    """Index claim positions by subject token. Only claims sharing at least
    one bucket are ever paired (avoids the naive all-pairs O(S^2) scan)."""
    buckets: dict[str, list[int]] = {}
    for idx, (_rel, _line, _pol, toks, _text) in enumerate(claims):
        for tok in toks:
            buckets.setdefault(tok, []).append(idx)
    return buckets


def _candidate_pairs(claims: list[tuple]) -> set[tuple[int, int]]:
    """Opposite-polarity claim index pairs drawn only from shared buckets."""
    buckets = _bucket_claims(claims)
    pairs: set[tuple[int, int]] = set()
    for idxs in buckets.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                x, y = idxs[a], idxs[b]
                if claims[x][2] != claims[y][2]:  # opposite polarity only
                    pairs.add((min(x, y), max(x, y)))
    return pairs


def check_ca_c001(targets, ctx):
    claims = []  # (rel, line_no, polarity, tokens, text)
    for t in targets:
        for i, line in enumerate(t["content"].splitlines(), start=1):
            if not line.strip():
                continue
            pol = _polarity(line)
            if pol is None:
                continue
            toks = _subject_tokens(line)
            if toks:
                claims.append((t["rel"], i, pol, toks, line.strip()))
    findings = []
    for x, y in sorted(_candidate_pairs(claims)):
        ra, la, _pa, ta, xa = claims[x]
        rb, lb, _pb, tb, xb = claims[y]
        union = ta | tb
        jac = len(ta & tb) / len(union) if union else 0.0
        if jac < 0.5:
            continue
        findings.append(make_finding(
            "CA-C001", "WARN", "REPORT_ONLY",
            f"{ra}:{la} vs {rb}:{lb}",
            what=f"矛盾候補（同一主題への禁止/許可の共起）: 「{xa}」 vs 「{xb}」",
            why="同一主題への相反する指示は LLM の行動を不安定化させ得る",
            how="LLM 判定で矛盾/意図的差分/優先順位解決済み/不明を分類する"))
    return findings


# --- Memory rules ----------------------------------------------------------

_REQUIRED_MEMORY_KEYS = ("name", "description")
_KNOWN_MEMORY_TYPES = {"user", "feedback", "reference", "project", "session"}


def check_ca_m001(targets, ctx):
    findings = []
    for t in targets:
        if t["kind"] != "memory":
            continue
        fm = parse_frontmatter_lines(t["content"])
        if fm is None:
            continue  # no frontmatter block: not a schema violation in v1
        keys = {k for k, _, _ in fm}
        for req in _REQUIRED_MEMORY_KEYS:
            if req not in keys:
                findings.append(make_finding(
                    "CA-M001", "WARN", "NEEDS_JUDGMENT", f"{t['rel']}:1",
                    what=f"メモリ frontmatter に必須キー `{req}` がない",
                    why="observed schema（name/description）欠落は不完全なメモリ定義",
                    how=f"`{req}` を補うか、非メモリファイルなら除外する"))
        for k, v, raw in fm:
            if k == "type" and v and v not in _KNOWN_MEMORY_TYPES:
                findings.append(make_finding(
                    "CA-M001", "WARN", "NEEDS_JUDGMENT",
                    f"{t['rel']}:{_line_of(t['content'], raw)}",
                    what=f"未知の memory type `{v}`",
                    why="type は Claude Code ランタイム慣習。未知値は harness drift の可能性",
                    how="既知 type に修正するか、新 type なら許容する（保守的に判断）"))
            canonical = f"{k}: {v}" if v != "" else f"{k}:"
            if raw != canonical and raw.rstrip() != canonical:
                findings.append(make_finding(
                    "CA-M001", "WARN", "AUTO_FIX",
                    f"{t['rel']}:{_line_of(t['content'], raw)}",
                    what=f"frontmatter の非正規な整形: `{raw}`",
                    why="キー整形の揺れは可読性・機械処理を阻害する",
                    how=f"`{raw}` を `{canonical}` に正規化する（body 不変）",
                    fix_action={"path": t["path"], "old": raw, "new": canonical}))
    return findings


def check_ca_m101(targets, ctx):
    findings = []
    root = ctx["root"]
    for t in targets:
        if t["kind"] != "memory":
            continue
        for ref, line, _source in _extract_path_refs(t["content"]):
            if _ref_exists(root, ref):
                continue
            findings.append(make_finding(
                "CA-M101", "WARN", "NEEDS_JUDGMENT", f"{t['rel']}:{line}",
                what=f"メモリが実在しないパスを参照 `{ref}`",
                why="陳腐化した参照はメモリの信頼性を損なう",
                how="参照を更新するか、該当メモリを見直す"))
    return findings


# email / home_path detect PII, not credentials — lower severity to avoid
# every MEMORY.md (which legitimately notes emails/paths) surfacing as BLOCK.
_PII_KINDS = {"email", "home_path"}


def check_ca_m301(targets, ctx):
    findings = []
    for t in targets:
        if t["kind"] != "memory":
            continue
        for i, line in enumerate(t["content"].splitlines(), start=1):
            hits = secret_detect.detect_secrets(line)
            if not hits:
                continue
            kinds = sorted({h["type"] for h in hits})
            credential = [k for k in kinds if k not in _PII_KINDS]
            if credential:
                findings.append(make_finding(
                    "CA-M301", "BLOCK", "REPORT_ONLY", f"{t['rel']}:{i}",
                    what=f"secret/credential 疑いのパターン検出: {', '.join(kinds)}",
                    why="メモリ内の資格情報は漏洩リスク。値は転記しない",
                    how="該当行を確認し、secret を除去・環境変数化する（自動マスクはしない）"))
            else:
                findings.append(make_finding(
                    "CA-M301", "WARN", "REPORT_ONLY", f"{t['rel']}:{i}",
                    what=f"PII 疑いのパターン検出: {', '.join(kinds)}",
                    why="メモリ内の PII（メール・ホームパス）は共有時の漏洩リスク。値は転記しない",
                    how="該当行を確認し、必要なら PII を除去する（自動マスクはしない）"))
    return findings


# ---------------------------------------------------------------------------
# Registry (Open-Closed dispatch). category/severity/action mirror
# references/rule-catalog.md — kept in sync by test_catalog_sync.py.
# ---------------------------------------------------------------------------

RULES: dict[str, dict[str, Any]] = {
    "CA-S001": {"category": "stale", "severity": "WARN",
                "action": "AUTO_FIX / NEEDS_JUDGMENT", "fn": check_ca_s001},
    "CA-S002": {"category": "stale", "severity": "WARN",
                "action": "NEEDS_JUDGMENT", "fn": check_ca_s002},
    "CA-U001": {"category": "unsafe", "severity": "WARN",
                "action": "REPORT_ONLY", "fn": check_ca_u001},
    "CA-D001": {"category": "drift", "severity": "INFO",
                "action": "REPORT_ONLY", "fn": check_ca_d001},
    "CA-D002": {"category": "drift", "severity": "WARN",
                "action": "NEEDS_JUDGMENT", "fn": check_ca_d002},
    "CA-C001": {"category": "contradiction", "severity": "WARN",
                "action": "REPORT_ONLY", "fn": check_ca_c001},
    "CA-M001": {"category": "memory", "severity": "WARN",
                "action": "AUTO_FIX / NEEDS_JUDGMENT", "fn": check_ca_m001},
    "CA-M101": {"category": "memory", "severity": "WARN",
                "action": "NEEDS_JUDGMENT", "fn": check_ca_m101},
    "CA-M301": {"category": "memory", "severity": "BLOCK / WARN",
                "action": "REPORT_ONLY", "fn": check_ca_m301},
}


def run_checks(targets: list[dict], ctx: dict) -> list[dict]:
    """Run every registered rule in ID order; mask secrets; return findings."""
    findings: list[dict] = []
    for rid in sorted(RULES):
        fn: Callable = RULES[rid]["fn"]
        findings.extend(fn(targets, ctx))
    return finalize_findings(findings)


def build_context(root: str, targets: list[dict]) -> dict:
    root = os.path.abspath(root)
    skill_names = set()
    for sub in ("skills", "codex-skills"):
        base = os.path.join(root, sub)
        if os.path.isdir(base):
            for d in os.listdir(base):
                if os.path.isdir(os.path.join(base, d)) and d != "shared":
                    skill_names.add(d)
    command_names = set()
    cdir = os.path.join(root, "commands")
    if os.path.isdir(cdir):
        command_names = {os.path.splitext(f)[0] for f in os.listdir(cdir) if f.endswith(".md")}
    return {
        "root": root,
        "skill_names": skill_names,
        "command_names": command_names,
        "has_validate_repo": os.path.isfile(os.path.join(root, "scripts", "validate_repo.py")),
    }


def _attach_content(targets: list[dict]) -> list[dict]:
    out = []
    for t in targets:
        content = t.get("content")
        if content is None:
            try:
                with open(t["path"], encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue
        out.append({**t, "content": content})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Run context-audit static checks")
    parser.add_argument("targets_json", help="collect_targets.py output (path or '-')")
    parser.add_argument("--root", default=".", help="Repo root")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    raw = sys.stdin.read() if args.targets_json == "-" else Path(args.targets_json).read_text(encoding="utf-8")
    data = json.loads(raw)
    targets = _attach_content(data["targets"] if isinstance(data, dict) else data)
    ctx = build_context(args.root, targets)
    findings = run_checks(targets, ctx)
    result = {"finding_count": len(findings), "findings": findings}

    js = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(js + "\n", encoding="utf-8")
    else:
        print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
