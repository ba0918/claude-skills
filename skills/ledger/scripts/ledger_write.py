#!/usr/bin/env python3
"""ledger_write: write-side CLI for agreement-ledger files (schema v1).

ledger_lint is read-only; this is its write-side companion. It records
adjudications a human has already confirmed — add-row / approve / reject /
batch-approve — and mechanizes the error-prone parts: the approval digest, the
batch manifest, and the self-check that the result still lints clean.

It is NOT an approver. A state transition is recorded, not decided: approve and
batch-approve consume a session artifact that records the human's own 4-choice
answer (agreement-ledger.md 中心命題), so a bare id can never manufacture an
approval and actor_kind is fixed to "human" internally rather than exposed as a
flag. The CLI does not make approval non-forgeable on its own — that is left to
workflow + git (agreement-ledger.md 中心命題); it only keeps that guarantee
from being weakened by refusing to write an approval without a recorded answer.

Every write goes through a verify-before-swap gate: the new ledger dict is
built in memory, linted in-process with ledger_lint.lint_data, and only when
there are no hard findings is it written to a tempfile and os.replace()'d over
the target. A rejected write never touches the file — no partial write, no
momentary persistence of invalid content (why-not: a write-then-rollback scheme
would expose all three).

digest computation and structural validation are reused from ledger_lint
(compute_digest / compute_batch_digest / lint_data); no ledger rule is
re-implemented here so the read and write sides cannot drift.

Exit codes (mirrors ledger_lint's 0/1/2 contract):
  0 = success
  1 = validation / business-rule rejection (revision mismatch, re-approve,
      high-risk row in a batch, a self-check finding, a detected secret,
      an unknown / disallowed target row, a missing human answer)
  2 = usage error / input corruption (bad arguments, root not a directory,
      a corrupt ledger or session artifact, a containment violation)
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "shared", "scripts"))
import secret_detect  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger_lint as ll  # noqa: E402

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_USAGE = 2

# The one risk band barred from batches (agreement-ledger.md batch 承認). Pinned
# to ledger_lint's enum so dropping it there fails loudly instead of silently
# diverging — no bare literal scattered across the write path.
HIGH_RISK = "high"
if HIGH_RISK not in ll.RISK_LEVELS:  # drift guard against ledger_lint
    raise RuntimeError("HIGH_RISK は ledger_lint.RISK_LEVELS の要素である必要がある")

# approve / reject apply to a claim still open for decision. An already-decided
# row (AGREED / REJECTED) must be reopened before it can transition again;
# DELEGATED is out of this CLI's scope (pilot-first).
ALLOWED_PRIOR = ("UNDECIDED", "PROVISIONAL")

ANSWER_APPROVE = "OK"
ANSWER_REJECT = "違う"

# New free-text row fields scanned for secrets before any write (mirrors
# ledger_lint._SECRET_SCAN_* — synthetic / anonymous data only).
_SECRET_SCAN_STRINGS = ("claim",)
_SECRET_SCAN_ARRAYS = ("observations", "assumptions")

# Canonical serialization: non-ASCII stays readable, 2-space indent, insertion
# order preserved (no sort_keys) so a single append does not churn unrelated
# rows. "Leaves other rows unchanged" is defined by meaning, not bytes.
_DUMP_KW = {"ensure_ascii": False, "indent": 2}


class WriteRejected(Exception):
    """Validation / business-rule rejection (maps to exit 1). Carries
    ledger_lint-style findings for stderr."""

    def __init__(self, findings):
        super().__init__("write rejected")
        self.findings = findings


def _finding(where, check, what, why, how):
    return ll.make_finding(where, check, what, why, how)


# ---------------------------------------------------------------------------
# Session artifact (records the human's 4-choice answers)
# ---------------------------------------------------------------------------

def load_session_artifact(path):
    """Parse + structurally validate a session artifact fail-closed. Raise
    LedgerLintError (exit-2 class) on corruption. approve / reject consume this
    so a recorded approval is always traceable to a real human answer — the CLI
    never authorizes a transition from a bare id."""
    data = ll.load_ledger_file(path)  # reuse the fail-closed JSON loader
    if not isinstance(data, dict):
        raise ll.LedgerLintError("not-an-object", "session 成果物が object でない")
    version = data.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) \
            or version != ll.SCHEMA_VERSION:
        raise ll.LedgerLintError(
            "unknown-schema-version", "session schema_version が未知")
    if not isinstance(data.get("session_id"), str) or not data["session_id"]:
        raise ll.LedgerLintError(
            "not-an-object", "session_id が非空 string でない")
    if not isinstance(data.get("responses"), list):
        raise ll.LedgerLintError("not-an-object", "responses が配列でない")
    return data


def _find_response(session, row_id):
    for r in session["responses"]:
        if isinstance(r, dict) and r.get("row_id") == row_id:
            return r
    return None


# ---------------------------------------------------------------------------
# Secret pre-flight
# ---------------------------------------------------------------------------

def _preflight_secrets(row):
    """Reject (exit 1) new free text that looks like a real credential before
    it can reach disk. Reuses the shared secret detector; the value is never
    echoed back (finding text is masked at output)."""
    findings = []
    for field in _SECRET_SCAN_STRINGS:
        v = row.get(field)
        if isinstance(v, str) and secret_detect.detect_secrets(v):
            findings.append(_secret_finding(row, field))
    for field in _SECRET_SCAN_ARRAYS:
        v = row.get(field)
        if isinstance(v, list) and any(
                isinstance(x, str) and secret_detect.detect_secrets(x)
                for x in v):
            findings.append(_secret_finding(row, field))
    if findings:
        raise WriteRejected(findings)


def _secret_finding(row, field):
    return _finding(
        f"(input)#{row.get('id', '')}", "secret-in-free-text",
        f"{field} に credential らしき文字列を検出",
        "自由文フィールドは合成・匿名データ限定（機密情報の規約）",
        f"{field} から実在の credential を除去し合成データに差し替える")


# ---------------------------------------------------------------------------
# Ledger loading (fail-closed) + verify-before-swap write
# ---------------------------------------------------------------------------

def _load_ledger(resolved):
    """Return the existing ledger data (fail-closed via ledger_lint) or a fresh
    empty ledger when the file does not exist yet (add-row bootstrapping)."""
    if not os.path.exists(resolved):
        return {"schema_version": ll.SCHEMA_VERSION, "rows": []}
    data = ll.load_ledger_file(resolved)
    ll.validate_toplevel(data, os.path.basename(resolved))  # raises on corruption
    return data


def _undecided_ids(rows):
    return {row["id"] for row in rows
            if isinstance(row, dict) and row.get("state") == "UNDECIDED"
            and isinstance(row.get("id"), str) and row["id"]}


def _verify_and_write(data, resolved, name, baseline_undecided_ids, dry_run):
    """The verify-before-swap gate. Lint the in-memory ledger; only when there
    are no hard findings write it to a tempfile and os.replace() over the
    target. On findings, touch nothing and raise WriteRejected. The baseline is
    the pre-change UNDECIDED id set — a defense-in-depth guard that a write
    never silently drops an undecided row (diff invariant)."""
    result = ll.lint_data([(name, data)],
                          baseline_undecided_ids=baseline_undecided_ids)
    if result["findings_present"]:
        raise WriteRejected(result["findings"])
    if dry_run:
        return
    blob = json.dumps(data, **_DUMP_KW) + "\n"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(resolved),
                               prefix=".ledger_write.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(blob)
        os.replace(tmp, resolved)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Row / approval construction
# ---------------------------------------------------------------------------

def _build_row(args):
    """Assemble a new UNDECIDED row in canonical field order. Argument names
    match the schema field names (no schema-external 'rationale' etc.)."""
    row = {
        "id": args.id,
        "revision": args.revision,
        "state": "UNDECIDED",
        "claim": args.claim,
    }
    if args.term_refs:
        row["term_refs"] = list(args.term_refs)
    if args.observations:
        row["observations"] = list(args.observations)
    if args.assumptions:
        row["assumptions"] = list(args.assumptions)
    if args.evidence_refs:
        row["evidence_refs"] = list(args.evidence_refs)
    if args.risk:
        row["risk"] = args.risk
    return row


def _find_row(rows, row_id):
    for row in rows:
        if isinstance(row, dict) and row.get("id") == row_id:
            return row
    return None


def _build_approval(row, session_id, prior_state):
    """Build an approval object. actor_kind is fixed to human (never a flag);
    the digest is recomputed from the current claim + term_refs so the CLI can
    never record an approval that lint would find stale."""
    return {
        "row_id": row["id"],
        "revision": row["revision"],
        "digest": ll.compute_digest(row),
        "session_id": session_id,
        "actor_kind": "human",
        "prior_state": prior_state,
    }


def _require_transitionable(row, row_id, session, want_answer):
    """Enforce that a recorded human response authorizes the requested
    transition: the target row exists, the session records an answer of the
    expected kind, the row is still open for decision, and the revision the
    human was shown still matches the current row."""
    if row is None:
        raise WriteRejected([_finding(
            f"(ledger)#{row_id}", "row-not-found",
            f"対象行 {row_id} が台帳に存在しない",
            "存在しない行は状態遷移できない",
            "対象の行 ID を確認する（未起票なら add-row で先に起こす）")])
    response = _find_response(session, row_id)
    if response is None or response.get("answer") != want_answer:
        raise WriteRejected([_finding(
            f"(session)#{row_id}", "no-human-answer",
            f"session 成果物に {row_id} の「{want_answer}」回答がない",
            "承認・却下は人間の明示回答からのみ記録できる（standalone 承認は不可）",
            "裁定セッションで当該行へ明示回答してから記録する")])
    prior = row.get("state")
    if prior not in ALLOWED_PRIOR:
        raise WriteRejected([_finding(
            f"(ledger)#{row_id}", "prior-state-not-allowed",
            f"状態 {prior!r} の行は遷移できない（許容: {'/'.join(ALLOWED_PRIOR)}）",
            "確定済み（AGREED / REJECTED）の行は再オープンしてからでないと遷移できない",
            "対象行の現状態を確認する")])
    shown_rev = response.get("revision")
    if shown_rev != row.get("revision"):
        raise WriteRejected([_finding(
            f"(ledger)#{row_id}", "revision-mismatch",
            f"提示 revision {shown_rev!r} が現行 revision "
            f"{row.get('revision')!r} と不一致",
            "主張が承認後に改訂された = 再裁定必須（digest 失効を CLI が起こさない）",
            "主張を再提示して裁定し直す")])
    return response, prior


def _summary_digest(text):
    """Digest of the human-displayed batch summary. ledger_lint treats
    summary_digest as opaque (it only recomputes batch_digest from it); the
    write side defines how the displayed text becomes that digest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def _load_contained_session(args, root):
    return load_session_artifact(ll.check_containment(args.session, root))


def _cmd_add_row(args, root, resolved, name):
    data = _load_ledger(resolved)
    rows = data["rows"]
    if _find_row(rows, args.id) is not None:
        raise WriteRejected([_finding(
            f"(ledger)#{args.id}", "duplicate-id",
            f"id {args.id} が既に台帳に存在する",
            "同一 ID の再利用は禁止（どちらが正か決定できない）",
            "新しい ID を採番する")])
    row = _build_row(args)
    _preflight_secrets(row)
    baseline = _undecided_ids(rows)
    rows.append(row)
    _verify_and_write(data, resolved, name, baseline, args.dry_run)
    return _report(args, {"id": row["id"], "revision": row["revision"],
                          "state": "UNDECIDED"},
                   f"add-row: {row['id']} を UNDECIDED で追加")


def _cmd_approve(args, root, resolved, name):
    session = _load_contained_session(args, root)
    data = _load_ledger(resolved)
    rows = data["rows"]
    row = _find_row(rows, args.row_id)
    _response, prior = _require_transitionable(
        row, args.row_id, session, ANSWER_APPROVE)
    baseline = _undecided_ids(rows)
    row["state"] = "AGREED"
    # AGREED permits only the approval attachment; drop a prior state's
    # attachment (e.g. PROVISIONAL's reeval_condition) so the transition does
    # not leave a now-illegal field behind.
    row.pop("delegation", None)
    row.pop("reeval_condition", None)
    row["approval"] = _build_approval(row, session["session_id"], prior)
    _verify_and_write(data, resolved, name, baseline, args.dry_run)
    return _report(args, {"row_id": row["id"], "revision": row["revision"],
                          "digest": row["approval"]["digest"]},
                   f"approve: {row['id']} を AGREED に記録")


def _cmd_reject(args, root, resolved, name):
    session = _load_contained_session(args, root)
    data = _load_ledger(resolved)
    rows = data["rows"]
    row = _find_row(rows, args.row_id)
    response, _prior = _require_transitionable(
        row, args.row_id, session, ANSWER_REJECT)
    baseline = _undecided_ids(rows)
    row["state"] = "REJECTED"
    # REJECTED carries no attachment; the reason (if any) goes to the existing
    # free-text observations, never to an approval-like field.
    for att in ("approval", "delegation", "reeval_condition"):
        row.pop(att, None)
    reason = response.get("reason")
    if isinstance(reason, str) and reason:
        obs = row.get("observations")
        if not isinstance(obs, list):
            obs = []
            row["observations"] = obs
        obs.append(reason)
    _verify_and_write(data, resolved, name, baseline, args.dry_run)
    return _report(args, {"row_id": row["id"], "state": "REJECTED"},
                   f"reject: {row['id']} を REJECTED に記録")


def _cmd_batch_approve(args, root, resolved, name):
    session = _load_contained_session(args, root)
    data = _load_ledger(resolved)
    rows = data["rows"]
    summary = session.get("batch_summary")
    if not isinstance(summary, str) or not summary:
        raise WriteRejected([_finding(
            "(session)#batch", "batch-summary-missing",
            "session 成果物に batch_summary（人間へ表示した要約）がない",
            "batch の真正性は表示要約の digest に依存する",
            "batch 要約を提示・記録してから一括承認する")])
    approvals = [r for r in session["responses"]
                 if isinstance(r, dict) and r.get("answer") == ANSWER_APPROVE]
    if not approvals:
        raise WriteRejected([_finding(
            "(session)#batch", "no-human-answer",
            "session 成果物に OK 回答が 1 件もない",
            "一括承認は人間の明示 OK 回答からのみ記録できる",
            "裁定セッションで承認する行へ OK 回答する")])
    baseline = _undecided_ids(rows)
    row_digests = []
    for response in approvals:
        row_id = response.get("row_id")
        row = _find_row(rows, row_id)
        _r, prior = _require_transitionable(
            row, row_id, session, ANSWER_APPROVE)
        if row.get("risk") == HIGH_RISK:
            raise WriteRejected([_finding(
                f"(ledger)#{row_id}", "high-risk-in-batch",
                "高リスク行を一括承認に含めることはできない",
                "高リスク・異論行は同調圧力・埋没効果を避けるため 1 行ずつ明示裁定する規約",
                "該当行を batch から外し単独で明示裁定する")])
        row["state"] = "AGREED"
        row["approval"] = _build_approval(row, session["session_id"], prior)
        row_digests.append(row["approval"]["digest"])
    summary_digest = _summary_digest(summary)
    manifest = {
        "batch_digest": ll.compute_batch_digest(row_digests, summary_digest),
        "row_digests": row_digests,
        "summary_digest": summary_digest,
    }
    manifests = data.get("batch_manifests", [])
    if not isinstance(manifests, list):
        raise ll.LedgerLintError(
            "not-an-object", "既存 batch_manifests が配列でない")
    data["batch_manifests"] = manifests + [manifest]
    _verify_and_write(data, resolved, name, baseline, args.dry_run)
    return _report(args, {"batch_digest": manifest["batch_digest"],
                          "row_digests": row_digests,
                          "summary_digest": summary_digest},
                   f"batch-approve: {len(row_digests)} 行を AGREED に記録")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _report(args, payload, human_msg):
    note = "（dry-run: 書き込みなし）" if args.dry_run else ""
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(human_msg + note)
    return EXIT_OK


def _print_findings(findings):
    # finalize masks secrets and strips control chars; idempotent on the
    # already-finalized findings that lint_data returns.
    for f in ll.finalize_findings(findings):
        print(f"[{f['where']}] {f['check']}: {f['what']} | "
              f"why: {f['why']} | fix: {f['how']}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_common(sub):
    sub.add_argument("--root", required=True,
                     help="対象プロジェクトルート（containment 境界）")
    sub.add_argument("--ledger", required=True, help="対象台帳ファイル（--root 内）")
    sub.add_argument("--json", action="store_true", help="機械可読出力")
    sub.add_argument("--dry-run", action="store_true", help="書き込まず検証のみ")


def _parser():
    parser = argparse.ArgumentParser(
        description="合意台帳ファイルの書き込み CLI（schema v1・記録の道具）")
    subs = parser.add_subparsers(dest="command", required=True)

    p_add = subs.add_parser("add-row", help="新規行を UNDECIDED で追加する")
    _add_common(p_add)
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--claim", required=True)
    p_add.add_argument("--revision", type=int, default=1)
    p_add.add_argument("--term-refs", nargs="*", default=[])
    p_add.add_argument("--observations", nargs="*", default=[])
    p_add.add_argument("--assumptions", nargs="*", default=[])
    p_add.add_argument("--evidence-refs", nargs="*", default=[])
    p_add.add_argument("--risk", choices=ll.RISK_LEVELS)

    p_app = subs.add_parser("approve", help="人間の OK 回答を AGREED として記録する")
    _add_common(p_app)
    p_app.add_argument("--row-id", required=True)
    p_app.add_argument("--session", required=True,
                       help="人間回答を記録した session 成果物（--root 内）")

    p_rej = subs.add_parser("reject",
                            help="人間の『違う』回答を REJECTED として記録する")
    _add_common(p_rej)
    p_rej.add_argument("--row-id", required=True)
    p_rej.add_argument("--session", required=True,
                       help="人間回答を記録した session 成果物（--root 内）")

    p_bat = subs.add_parser("batch-approve",
                            help="複数行を一括承認し manifest を記録する")
    _add_common(p_bat)
    p_bat.add_argument("--session", required=True,
                       help="人間回答を記録した session 成果物（--root 内）")
    return parser


_HANDLERS = {
    "add-row": _cmd_add_row,
    "approve": _cmd_approve,
    "reject": _cmd_reject,
    "batch-approve": _cmd_batch_approve,
}


def main(argv=None):
    args = _parser().parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"usage-error: root がディレクトリでない: {args.root}",
              file=sys.stderr)
        return EXIT_USAGE

    try:
        resolved = ll.check_containment(args.ledger, root)
    except ll.LedgerLintError as e:
        print(f"usage-error: 台帳パスが不正 ({e.category}): {e.message}",
              file=sys.stderr)
        return EXIT_USAGE

    try:
        return _HANDLERS[args.command](args, root, resolved,
                                       os.path.basename(resolved))
    except WriteRejected as e:
        _print_findings(e.findings)
        return EXIT_REJECTED
    except ll.LedgerLintError as e:
        print(f"input-corruption({e.category}): {e.message}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
