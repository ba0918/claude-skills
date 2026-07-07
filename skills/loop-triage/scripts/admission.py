"""Loop-triage の admission ロジック（純関数のみ）。

loop-engineering.md 契約の §4 Admission Policy（fix_action x severity -> route）と
§5 Self-Modification Gate（loop-defining ファイル判定 + 依存グラフ逆引きによる
enqueue 降格）を実装する。I/O・time・random を一切使わない。呼び出し側（orchestrator）が
ファイルシステム走査・dep_graph 逆引き関数を DI で注入する。
"""

# --- §5.1 loop-defining glob ------------------------------------------------

LOOP_DEFINING_GLOBS = [
    "skills/*/SKILL.md",
    "skills/*/references/**",
    "skills/shared/**",
    "commands/**",
    "scripts/validate_repo.py",
    ".claude/review-rules.md",
]


def _match_segments(pattern_segs, path_segs):
    """glob セグメント列がパスセグメント列に一致するか。

    `*` は path_segs の1セグメントに一致（空セグメントは想定しない）。
    `**` は path_segs の0個以上のセグメントに一致し、パス区切りを跨ぐ。
    """
    if not pattern_segs:
        return not path_segs

    head = pattern_segs[0]

    if head == "**":
        # 0 セグメント消費で残りに委譲
        if _match_segments(pattern_segs[1:], path_segs):
            return True
        # 1 セグメント消費して再帰（path が尽きたら False で終わる）
        if path_segs and _match_segments(pattern_segs, path_segs[1:]):
            return True
        return False

    if not path_segs:
        return False

    if head == "*":
        return _match_segments(pattern_segs[1:], path_segs[1:])

    if head != path_segs[0]:
        return False

    return _match_segments(pattern_segs[1:], path_segs[1:])


def _glob_match(pattern, path):
    return _match_segments(pattern.split("/"), path.split("/"))


def is_loop_defining(path):
    """posix 相対パスが LOOP_DEFINING_GLOBS のいずれかに一致するか。"""
    return any(_glob_match(pattern, path) for pattern in LOOP_DEFINING_GLOBS)


# --- §4 Admission Policy -----------------------------------------------------

_ROUTE_TABLE = {
    ("AUTO_FIX", "BLOCK"): "enqueue",
    ("AUTO_FIX", "WARN"): "enqueue",
    ("AUTO_FIX", "INFO"): "digest",
    ("NEEDS_JUDGMENT", "BLOCK"): "inbox",
    ("NEEDS_JUDGMENT", "WARN"): "inbox",
    ("NEEDS_JUDGMENT", "INFO"): "digest",
    ("REPORT_ONLY", "BLOCK"): "digest",
    ("REPORT_ONLY", "WARN"): "digest",
    ("REPORT_ONLY", "INFO"): "digest",
}


def route_base(fix_action, severity):
    """§4 の表そのまま。未知の組み合わせは "digest"（fail-safe）。"""
    return _ROUTE_TABLE.get((fix_action, severity), "digest")


# --- §5.2 Self-Modification Gate ---------------------------------------------

def gate_decision(affected_paths, path_to_skills, skills_with_fixtures):
    """自己修飾ゲート判定。

    affected_paths のうち loop-defining なものを path_to_skills で影響スキルへ
    逆引きし、fixture カバレッジで enqueue 可否を判定する。
    """
    loop_defining_paths = [p for p in affected_paths if is_loop_defining(p)]

    if not loop_defining_paths:
        return {
            "gated": False,
            "demote": False,
            "affected_skills": [],
            "missing_fixtures": [],
        }

    affected_skills = set()
    unresolved = False
    for p in loop_defining_paths:
        skills = path_to_skills(p)
        if not skills:
            # この loop-defining パスはどのスキルの挙動面にも解決できない
            # -> ゲートで守れない変更なので per-path で安全側に倒す
            unresolved = True
        affected_skills.update(skills)

    missing = sorted(s for s in affected_skills if s not in skills_with_fixtures)
    if unresolved:
        missing.append("(unresolved)")

    return {
        "gated": True,
        "demote": bool(missing),
        "affected_skills": sorted(affected_skills),
        "missing_fixtures": missing,
    }


# --- Finding routing ----------------------------------------------------------

_KNOWN_FIX_ACTIONS = ("AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY")


def route(finding, *, queue_ids, baseline, fid, path_to_skills,
          skills_with_fixtures, enqueue_used, max_enqueue_per_run=5):
    """1 finding の最終ルーティング（優先順にショートサーキット）。"""
    if fid in baseline:
        return {"route": "suppressed"}

    if fid in queue_ids:
        return {"route": "duplicate"}

    fix_action = finding.get("fix_action")
    if fix_action not in _KNOWN_FIX_ACTIONS:
        # fix_action 不明・欠落の finding は REPORT_ONLY に正規化する（fail-safe）
        fix_action = "REPORT_ONLY"
    severity = finding.get("severity")

    base = route_base(fix_action, severity)

    if base != "enqueue":
        return {"route": base}

    affected_paths = finding.get("affected_paths", [])
    gate = gate_decision(affected_paths, path_to_skills, skills_with_fixtures)

    if gate["demote"]:
        result = {"route": "inbox", "reason": "gate"}
        result.update(gate)
        return result

    if enqueue_used >= max_enqueue_per_run:
        return {"route": "inbox", "reason": "budget"}

    result = {"route": "enqueue"}
    if gate["gated"]:
        result["gate"] = "skill-regression"
    return result
