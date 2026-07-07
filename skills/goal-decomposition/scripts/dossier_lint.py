#!/usr/bin/env python3
"""goal-decomposition: pure-function GD-* dossier lint engine.

A dossier (Loop Readiness Dossier) is JSON canonical; this linter type-checks it
against the schema fixed in shared/references/goal-decomposition-pattern.md §2.
Each rule is a pure function `check(dossier, ctx) -> list[Finding]` registered in
RULES. run_checks is a thin dispatcher: adding a rule = add function + register +
test, without touching existing rules (Open-Closed). The contract rule table (§11)
and RULES are kept in sync by test_dossier_lint.TestCatalogSync.

Finding schema (every rule, every finding):
  {rule, severity(error/warn), file, locator, message, fix}

Exit codes (CLI):
  0 = pass (warn-only is still 0) / 1 = error-level finding / 2 = precondition
  failure (JSON parse / duplicate key / bad path / missing file / oversize).

Security invariant: every free-text finding field is passed through mask_secrets
before serialization, so no detected secret value reaches the findings output.
"""

import argparse
import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "shared", "scripts"))
import secret_detect  # noqa: E402

# ---------------------------------------------------------------------------
# Schema constants (single source: goal-decomposition-pattern.md §2)
# ---------------------------------------------------------------------------

MAX_SIZE = 1_000_000  # bytes; larger dossiers are treated as a precondition fail
DOSSIERS_DIR = "docs/loop/dossiers"

REQUIRED_BLOCKS = {
    "goal": dict,
    "oracles": list,
    "sensors": list,
    "inbox": list,
    "measurement": dict,
}
STATUS_VALUES = {"draft", "approved", "superseded", "rejected"}
WIRE_VALUES = {"goal-loop", "loop-triage", "inbox", "plan", "reject"}
EXIT_VALUES = {"ci_gate", "resident_sensor", "dissolve"}
FIX_ACTION_VALUES = {"AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY"}
PROXY_REQUIRED = ("gap_from_true_goal", "failure_modes", "human_limit_approved",
                  "hash_lock", "post_completion_human_check", "judge_type")

# §4.1 wire_to x exit_to compatibility matrix (single source of truth).
_COMPAT = {
    "goal-loop": {"ci_gate", "dissolve"},
    "loop-triage": {"ci_gate", "resident_sensor"},
    "inbox": {"dissolve"},
    "plan": {"dissolve"},
    "reject": {"dissolve"},
}


class DossierLoadError(Exception):
    """Raised for any precondition failure (maps to CLI exit code 2)."""


# ---------------------------------------------------------------------------
# Finding helpers
# ---------------------------------------------------------------------------

CANONICAL_FINDING_FIELDS = ("rule", "severity", "file", "locator", "message", "fix")


def make_finding(rule, severity, file, locator, message, fix):
    return {"rule": rule, "severity": severity, "file": file,
            "locator": locator, "message": message, "fix": fix}


def finalize_findings(findings):
    """Mask secrets in every free-text field of every finding."""
    out = []
    for f in findings:
        g = dict(f)
        for k in ("locator", "message", "fix"):
            if isinstance(g.get(k), str):
                g[k] = secret_detect.mask_secrets(g[k])
        out.append(g)
    return out


# ---------------------------------------------------------------------------
# Accessors (type-safe: a malformed dossier must never raise, only report)
# ---------------------------------------------------------------------------

def _fragments(d):
    v = d.get("fragments")
    return [f for f in v if isinstance(f, dict)] if isinstance(v, list) else []


def _oracles(d):
    v = d.get("oracles")
    return [o for o in v if isinstance(o, dict)] if isinstance(v, list) else []


def _sensors(d):
    v = d.get("sensors")
    return [s for s in v if isinstance(s, dict)] if isinstance(v, list) else []


def _inbox(d):
    v = d.get("inbox")
    return [i for i in v if isinstance(i, dict)] if isinstance(v, list) else []


def _all_ids(d):
    """(id -> occurrence count) across oracles/fragments/sensors/inbox."""
    counts = {}
    for block in (_oracles(d), _fragments(d), _sensors(d), _inbox(d)):
        for item in block:
            i = item.get("id")
            if isinstance(i, str):
                counts[i] = counts.get(i, 0) + 1
    return counts


def _has_secret(value):
    return bool(secret_detect.detect_secrets(value)) if isinstance(value, str) else False


def _is_abs(value):
    return isinstance(value, str) and (value.startswith("/") or "\\" in value[:3])


# ---------------------------------------------------------------------------
# Rules — GD0xx structure
# ---------------------------------------------------------------------------

def check_gd001(d, ctx):
    findings = []
    f = ctx["file"]
    sv = d.get("schema_version")
    # bool is a subclass of int; a bool schema_version is a type error.
    if "schema_version" not in d or not isinstance(sv, int) or isinstance(sv, bool):
        findings.append(make_finding(
            "GD001", "error", f, "schema_version",
            "必須フィールド schema_version が欠落または int でない",
            "schema_version: 1 を int で設定する"))
    for block, typ in REQUIRED_BLOCKS.items():
        if block not in d:
            findings.append(make_finding(
                "GD001", "error", f, block,
                f"必須ブロック {block} が欠落",
                f"{block} ブロックを追加する（型: {typ.__name__}）"))
        elif not isinstance(d[block], typ):
            findings.append(make_finding(
                "GD001", "error", f, block,
                f"必須ブロック {block} の型が不正（期待: {typ.__name__}）",
                f"{block} を {typ.__name__} として定義する"))
    return findings


def check_gd002(d, ctx):
    s = d.get("status")
    if not isinstance(s, str) or s not in STATUS_VALUES:
        return [make_finding(
            "GD002", "error", ctx["file"], "status",
            f"status が enum({'/'.join(sorted(STATUS_VALUES))}) 外または欠落: {s!r}",
            "status を draft/approved/superseded/rejected のいずれかにする")]
    return []


def check_gd003(d, ctx):
    findings = []
    for frag in _fragments(d):
        w = frag.get("wire_to")
        if not isinstance(w, str) or w not in WIRE_VALUES:
            findings.append(make_finding(
                "GD003", "error", ctx["file"], f"{frag.get('id', '?')}.wire_to",
                f"wire_to が enum 外または欠落: {w!r}",
                f"wire_to を {'/'.join(sorted(WIRE_VALUES))} のいずれかにする"))
    return findings


def check_gd004(d, ctx):
    findings = []
    for frag in _fragments(d):
        e = frag.get("exit_to")
        if not isinstance(e, str) or e not in EXIT_VALUES:
            findings.append(make_finding(
                "GD004", "error", ctx["file"], f"{frag.get('id', '?')}.exit_to",
                f"exit_to が enum 外または欠落: {e!r}",
                f"exit_to を {'/'.join(sorted(EXIT_VALUES))} のいずれかにする"))
    return findings


def check_gd005(d, ctx):
    findings = []
    # Contract §11: blocked_by targets are fragment/inbox ids only (an oracle
    # or sensor cannot "resolve" and unblock anything).
    valid = {f.get("id") for f in _fragments(d) if isinstance(f.get("id"), str)}
    valid |= {i.get("id") for i in _inbox(d) if isinstance(i.get("id"), str)}
    for frag in _fragments(d):
        bb = frag.get("blocked_by")
        if not isinstance(bb, list):
            continue
        for ref in bb:
            if ref not in valid:
                findings.append(make_finding(
                    "GD005", "error", ctx["file"], f"{frag.get('id', '?')}.blocked_by",
                    f"blocked_by が実在しない id を参照: {ref!r}",
                    "参照先の fragment/inbox id を実在するものに直す"))
    return findings


def check_gd006(d, ctx):
    findings = []
    for i, n in sorted(_all_ids(d).items()):
        if n > 1:
            findings.append(make_finding(
                "GD006", "error", ctx["file"], i,
                f"id が重複している（{n} 回出現）: {i}",
                "oracles/fragments/sensors/inbox 横断で id を一意にする"))
    return findings


# ---------------------------------------------------------------------------
# Rules — GD1xx routing / proof
# ---------------------------------------------------------------------------

def check_gd101(d, ctx):
    findings = []
    for s in _sensors(d):
        fp = s.get("findings_policy")
        if not isinstance(fp, dict):
            continue
        if fp.get("fix_action") == "REPORT_ONLY" and fp.get("enqueue") is True:
            findings.append(make_finding(
                "GD101", "error", ctx["file"], f"{s.get('id', '?')}.findings_policy",
                "REPORT_ONLY の finding を enqueue: true にしている（不変条件違反）",
                "enqueue を false にする（REPORT_ONLY は絶対に enqueue しない）"))
    return findings


def _missing(v):
    return v is None or (isinstance(v, str) and not v.strip())


def check_gd102(d, ctx):
    findings = []
    approved = d.get("status") == "approved"
    for frag in _fragments(d):
        fid = frag.get("id", "?")
        if approved and _missing(frag.get("routing_proof")):
            findings.append(make_finding(
                "GD102", "error", ctx["file"], f"{fid}.routing_proof",
                "status: approved なのに routing_proof が欠落",
                "各断片に 1 行の routing proof を書く"))
        if frag.get("auto_fix_allowed") is False and _missing(frag.get("why_not_auto_fix")):
            findings.append(make_finding(
                "GD102", "error", ctx["file"], f"{fid}.why_not_auto_fix",
                "auto_fix_allowed: false の断片に why_not_auto_fix が欠落",
                "なぜ AUTO_FIX でないかを明記する"))
    return findings


def check_gd103(d, ctx):
    findings = []
    for frag in _fragments(d):
        w, e = frag.get("wire_to"), frag.get("exit_to")
        if w not in WIRE_VALUES or e not in EXIT_VALUES:
            continue  # enum validity is GD003/GD004's job
        if e not in _COMPAT[w]:
            findings.append(make_finding(
                "GD103", "error", ctx["file"], f"{frag.get('id', '?')}",
                f"wire_to({w}) × exit_to({e}) は非互換（compatibility matrix 違反）",
                f"{w} と両立する exit_to は {'/'.join(sorted(_COMPAT[w]))}"))
    return findings


def check_gd104(d, ctx):
    findings = []
    f = ctx["file"]
    status = d.get("status")
    if status == "approved":
        for frag in _fragments(d):
            bb = frag.get("blocked_by")
            if isinstance(bb, list) and bb:
                findings.append(make_finding(
                    "GD104", "error", f, f"{frag.get('id', '?')}.blocked_by",
                    "status: approved なのに未解決の blocked_by が残存",
                    "承認前に blocked_by を解消する（inbox 問いに決着をつける）"))
    if status == "superseded" and _missing(d.get("superseded_by")):
        findings.append(make_finding(
            "GD104", "error", f, "superseded_by",
            "status: superseded なのに superseded_by が欠落",
            "後継 dossier のファイル名を superseded_by に記す"))
    if status == "rejected":
        for frag in _fragments(d):
            if frag.get("exit_to") in ("ci_gate", "resident_sensor"):
                findings.append(make_finding(
                    "GD104", "error", f, f"{frag.get('id', '?')}.exit_to",
                    "status: rejected の dossier に稼働中の exit_to 配線が残存",
                    "rejected では fragment の exit_to を dissolve にする"))
    return findings


# ---------------------------------------------------------------------------
# Rules — GD2xx proxy / safety
# ---------------------------------------------------------------------------

def check_gd201(d, ctx):
    findings = []
    for o in _oracles(d):
        if o.get("type") != "proxy":
            continue
        oid = o.get("id", "?")
        proxy = o.get("proxy")
        if not isinstance(proxy, dict):
            findings.append(make_finding(
                "GD201", "error", ctx["file"], f"{oid}.proxy",
                "proxy oracle に proxy ブロックがない",
                f"proxy に {', '.join(PROXY_REQUIRED)} を記す"))
            continue
        for key in PROXY_REQUIRED:
            if key not in proxy:
                findings.append(make_finding(
                    "GD201", "error", ctx["file"], f"{oid}.proxy.{key}",
                    f"proxy oracle の必須欄 {key} が欠落",
                    f"{key} を明示する（安全な前進の下限ゲート条件）"))
        if proxy.get("judge_type") == "llm_subjective":
            findings.append(make_finding(
                "GD201", "error", ctx["file"], f"{oid}.proxy.judge_type",
                "proxy oracle の judge_type が llm_subjective（主観評価は禁止）",
                "judge_type を mechanical にする"))
    return findings


def check_gd202(d, ctx):
    findings = []
    for frag in _fragments(d):
        if frag.get("self_modification_risk") == "high" \
                and frag.get("auto_fix_allowed") is True:
            findings.append(make_finding(
                "GD202", "error", ctx["file"], f"{frag.get('id', '?')}",
                "self_modification_risk: high かつ auto_fix_allowed: true（危険組み合わせ）",
                "自己修飾リスクの高い断片を自動修正に載せない（回帰網が先）"))
    return findings


def check_gd203(d, ctx):
    findings = []
    f = ctx["file"]
    for o in _oracles(d):
        oid = o.get("id", "?")
        files = o.get("oracle_files")
        if isinstance(files, list):
            for entry in files:
                if _is_abs(entry) or _has_secret(entry):
                    findings.append(make_finding(
                        "GD203", "error", f, f"{oid}.oracle_files",
                        f"oracle_files に絶対パスまたは secret が混入: {entry}",
                        "repo 相対の明示列挙にする（絶対パス・secret は禁止）"))
        cmd = o.get("command")
        cmd_has_abs = isinstance(cmd, str) and any(
            _is_abs(tok) for tok in cmd.split())
        if _has_secret(cmd) or cmd_has_abs:
            findings.append(make_finding(
                "GD203", "error", f, f"{oid}.command",
                "command に secret または絶対パスが混入",
                "command から secret を除去し（環境変数化）、パスは repo 相対にする"))
    for i in _all_ids(d):
        if _is_abs(i) or _has_secret(i):
            findings.append(make_finding(
                "GD203", "error", f, i,
                f"id に絶対パスまたは secret が混入: {i}",
                "id は slug（例: frag:foo）にする"))
    return findings


# ---------------------------------------------------------------------------
# Rules — GD3xx advisory (warn)
# ---------------------------------------------------------------------------

def check_gd301(d, ctx):
    findings = []
    for o in _oracles(d):
        files = o.get("oracle_files")
        entries = files if isinstance(files, list) else []
        explicit = [e for e in entries if isinstance(e, str) and e and "*" not in e]
        if not explicit:
            findings.append(make_finding(
                "GD301", "warn", ctx["file"], f"{o.get('id', '?')}.oracle_files",
                "oracle_files が空配列または glob のみ（明示列挙がない）",
                "ロック対象を明示的なファイル列挙で書く（goal_loop verify の限界対策）"))
    return findings


def check_gd302(d, ctx):
    goal = d.get("goal")
    if not isinstance(goal, dict):
        return []  # missing/typed goal is GD001's job
    ng = goal.get("non_goals")
    if not isinstance(ng, list) or not ng:
        return [make_finding(
            "GD302", "warn", ctx["file"], "goal.non_goals",
            "goal.non_goals が空（願望の無限拡張リスク）",
            "自動化に載せない範囲を non_goals に明記する")]
    return []


# ---------------------------------------------------------------------------
# Registry (Open-Closed dispatch). severity mirrors the contract §11 table —
# kept in sync by test_dossier_lint.TestCatalogSync.
# ---------------------------------------------------------------------------

RULES = {
    "GD001": {"severity": "error", "fn": check_gd001},
    "GD002": {"severity": "error", "fn": check_gd002},
    "GD003": {"severity": "error", "fn": check_gd003},
    "GD004": {"severity": "error", "fn": check_gd004},
    "GD005": {"severity": "error", "fn": check_gd005},
    "GD006": {"severity": "error", "fn": check_gd006},
    "GD101": {"severity": "error", "fn": check_gd101},
    "GD102": {"severity": "error", "fn": check_gd102},
    "GD103": {"severity": "error", "fn": check_gd103},
    "GD104": {"severity": "error", "fn": check_gd104},
    "GD201": {"severity": "error", "fn": check_gd201},
    "GD202": {"severity": "error", "fn": check_gd202},
    "GD203": {"severity": "error", "fn": check_gd203},
    "GD301": {"severity": "warn", "fn": check_gd301},
    "GD302": {"severity": "warn", "fn": check_gd302},
}


def run_checks(dossier, ctx=None):
    """Run every registered rule in ID order; mask secrets; return findings."""
    if ctx is None:
        ctx = {"file": ""}
    ctx.setdefault("file", "")
    findings = []
    for rid in sorted(RULES):
        findings.extend(RULES[rid]["fn"](dossier, ctx))
    return finalize_findings(findings)


def has_errors(findings):
    return any(f.get("severity") == "error" for f in findings)


# ---------------------------------------------------------------------------
# I/O (isolated from the pure rule engine)
# ---------------------------------------------------------------------------

def _no_dup_pairs(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate key: {k}")
        seen[k] = v
    return seen


def load_dossier(path):
    """Load and parse a dossier JSON. Raise DossierLoadError on any precondition
    failure (missing / oversize / broken JSON / duplicate key / decode error)."""
    try:
        if os.stat(path).st_size > MAX_SIZE:
            raise DossierLoadError(f"dossier がサイズ上限 {MAX_SIZE}B を超過: {path}")
    except OSError as e:
        raise DossierLoadError(f"dossier を stat できない: {path} ({e})")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read(), object_pairs_hook=_no_dup_pairs)
    except (json.JSONDecodeError, RecursionError, ValueError,
            UnicodeDecodeError, OSError) as e:
        raise DossierLoadError(f"dossier を parse できない: {path} ({type(e).__name__})")
    if not isinstance(data, dict):
        raise DossierLoadError(f"dossier のトップレベルが object でない: {path}")
    return data


def check_containment(arg_path, dossiers_dir):
    """Ensure arg_path resolves strictly inside dossiers_dir (commonpath, not
    startswith) and is not a symlink. Return arg_path or raise DossierLoadError."""
    if os.path.islink(arg_path):
        raise DossierLoadError(f"symlink は拒否: {arg_path}")
    real_arg = os.path.realpath(arg_path)
    real_dir = os.path.realpath(dossiers_dir)
    try:
        common = os.path.commonpath([real_arg, real_dir])
    except ValueError:  # different drives / mixed abs-rel
        raise DossierLoadError(f"パスが dossiers ディレクトリ外: {arg_path}")
    if common != real_dir:
        raise DossierLoadError(f"パスが dossiers ディレクトリ外: {arg_path}")
    return arg_path


def _lint_one(path, dossiers_dir):
    """Return (findings, load_error_message | None)."""
    try:
        check_containment(path, dossiers_dir)
        dossier = load_dossier(path)
    except DossierLoadError as e:
        return [], str(e)
    return run_checks(dossier, {"file": os.path.basename(path)}), None


def main():
    parser = argparse.ArgumentParser(description="Lint Loop Readiness Dossier JSON")
    parser.add_argument("paths", nargs="*", help="dossier .json paths")
    parser.add_argument("--dossiers-dir", default=DOSSIERS_DIR)
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args()

    paths = args.paths
    if not paths and os.path.isdir(args.dossiers_dir):
        paths = sorted(
            os.path.join(args.dossiers_dir, n)
            for n in os.listdir(args.dossiers_dir) if n.endswith(".json"))

    exit_code = 0
    report = []
    for path in paths:
        findings, err = _lint_one(path, args.dossiers_dir)
        if err is not None:
            exit_code = max(exit_code, 2)
            report.append({"file": path, "error": err, "findings": []})
            if not args.json:
                print(f"[{path}] precondition-error: {err}")
            continue
        if has_errors(findings):
            exit_code = max(exit_code, 1)
        report.append({"file": path, "error": None, "findings": findings})
        if not args.json:
            for f in findings:
                print(f"[{f['file']}] {f['rule']} ({f['severity']}) "
                      f"{f['locator']}: {f['message']}")
    if args.json:
        print(json.dumps({"exit_code": exit_code, "report": report},
                         indent=2, ensure_ascii=False))
    elif exit_code == 0:
        print("✓ dossier lint: 全チェック合格")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
