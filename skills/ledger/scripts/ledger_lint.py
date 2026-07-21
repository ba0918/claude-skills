#!/usr/bin/env python3
"""ledger: hand-rolled structural linter for agreement-ledger files (schema v1).

The vocabulary source of truth is
skills/shared/references/agreement-ledger.md; the constants below mirror its
tables and are kept in sync by test_ledger_lint (md tables <-> these
constants). JSON is the canonical machine-verified format (agreement-ledger.md
why-not): the runtime has no stdlib YAML parser and the ledger is LLM-facing,
so spec_lint's proven fail-closed loader is reused rather than adding PyYAML.

Finding schema (every finding): {where, what, why, how, check}
  where = "<file>#<row id>" / what = violation / why = rationale /
  how = fix instruction / check = machine slug.

Exit codes (contract table in agreement-ledger.md):
  0 = run succeeded (report-only default: even with findings; zero targets too)
  1 = findings present, --strict only
  2 = input corruption / usage error (mode-independent; diagnostics-only
      output marked valid: false — partial results are never authoritative)
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "shared", "scripts"))
import secret_detect  # noqa: E402

# ---------------------------------------------------------------------------
# Schema constants (single source: shared/references/agreement-ledger.md)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
MAX_SIZE = 1_000_000   # bytes; real ledger files are a few KB
MAX_ROWS = 10_000      # per file; expected real scale is dozens to hundreds
MAX_DEPTH = 16         # valid schema depth is small; anything deeper is hostile

ID_PATTERN = r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-[0-9]{3,}$"
_ID_RE = re.compile(ID_PATTERN)

STATES = ("AGREED", "DELEGATED", "PROVISIONAL", "UNDECIDED", "REJECTED")
ACTOR_KINDS = ("human",)

# {field: (type token, required)} — tokens fixed by the md parse contract.
ROW_FIELDS = {
    "id": ("string", True),
    "revision": ("integer", True),
    "state": ("string", True),
    "claim": ("string", True),
    "term_refs": ("array[string]", False),
    "observations": ("array[string]", False),
    "assumptions": ("array[string]", False),
    "evidence_refs": ("array[string]", False),
    "approval": ("object", False),
    "delegation": ("object", False),
    "reeval_condition": ("string", False),
}

APPROVAL_FIELDS = {
    "row_id": ("string", True),
    "revision": ("integer", True),
    "digest": ("string", True),
    "session_id": ("string", True),
    "actor_kind": ("string", True),
    "prior_state": ("string", True),
}

DELEGATION_FIELDS = {
    "subject": ("string", True),
    "operation": ("string", True),
    "scope": ("string", True),
    "expiry": ("string", True),
    "revocation": ("string", True),
}

# The single attachment each state permits. UNDECIDED / REJECTED permit none.
STATE_ATTACHMENT = {
    "AGREED": "approval",
    "DELEGATED": "delegation",
    "PROVISIONAL": "reeval_condition",
}
ATTACHMENTS = ("approval", "delegation", "reeval_condition")
_MISSING_SLUG = {
    "approval": "approval-missing",
    "delegation": "delegation-missing",
    "reeval_condition": "reeval-condition-missing",
}

TOPLEVEL_FIELDS = {
    "schema_version": ("integer", True),
    "rows": ("array[object]", True),
}

# Free-text fields under the 機密情報の規約 (synthetic/anonymous data only).
_SECRET_SCAN_STRINGS = ("claim",)
_SECRET_SCAN_ARRAYS = ("observations", "assumptions")

_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class LedgerLintError(Exception):
    """Input corruption / usage error (maps to exit 2)."""

    def __init__(self, category, message):
        super().__init__(message)
        self.category = category
        self.message = message


# ---------------------------------------------------------------------------
# Approval digest (agreement-ledger.md 主張 digest の算出規則)
# ---------------------------------------------------------------------------

def compute_digest(row):
    """Deterministic digest over the meaning-bearing claim body. If claim or
    term_refs change after approval, this digest changes and the recorded
    approval no longer matches — the machine-checkable core of "LLM cannot be
    the approver".

    Total by construction: malformed rows (non-string claim, non-list or
    non-string term_refs) get their own invalid-type findings elsewhere, so
    here they are coerced to the empty/valid case rather than raising — a lint
    over untrusted input must never crash instead of fail-closing. For a
    well-formed row (claim: string, term_refs: string array) this coercion is
    a no-op, so the documented algorithm still holds."""
    claim = row.get("claim", "")
    if not isinstance(claim, str):
        claim = ""
    refs = row.get("term_refs")
    if not isinstance(refs, list):
        refs = []
    core = {
        "claim": claim,
        "term_refs": sorted(r for r in refs if isinstance(r, str)),
    }
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Fail-closed loading
# ---------------------------------------------------------------------------

class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateKeyError(f"重複 JSON key: {key}")
        seen[key] = value
    return seen


def _check_depth(data):
    stack = [(data, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise LedgerLintError(
                "too-deep", f"ネスト深さが上限 {MAX_DEPTH} を超過")
        if isinstance(node, dict):
            stack.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            stack.extend((v, depth + 1) for v in node)


def load_ledger_file(path):
    """Parse one ledger file fail-closed. Raise LedgerLintError on corruption
    (size / broken JSON / duplicate key / nesting depth); no traceback leaks."""
    try:
        if os.stat(path).st_size > MAX_SIZE:
            raise LedgerLintError(
                "file-too-large", f"ファイルサイズが上限 {MAX_SIZE}B を超過")
    except OSError as e:
        raise LedgerLintError("unreadable", f"読み取り不能 ({type(e).__name__})")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read(),
                              object_pairs_hook=_reject_duplicate_keys)
    except _DuplicateKeyError as e:
        raise LedgerLintError("duplicate-json-key", str(e))
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError,
            ValueError, OSError) as e:
        raise LedgerLintError(
            "invalid-json", f"JSON として parse できない ({type(e).__name__})")
    _check_depth(data)
    return data


def validate_toplevel(data, name):
    """Return (rows, toplevel findings). Raise LedgerLintError for file
    structure corruption (exit 2 class)."""
    if not isinstance(data, dict):
        raise LedgerLintError("not-an-object", "トップレベルが object でない")
    missing = [k for k, (_t, req) in TOPLEVEL_FIELDS.items()
               if req and k not in data]
    if missing:
        raise LedgerLintError(
            "missing-toplevel-key",
            f"トップレベル必須キーが欠落: {', '.join(missing)}")
    version = data["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) \
            or version != SCHEMA_VERSION:
        raise LedgerLintError(
            "unknown-schema-version",
            f"schema_version が未知（v1 は {SCHEMA_VERSION} 固定）")
    rows = data["rows"]
    if not isinstance(rows, list):
        raise LedgerLintError("rows-not-array", "rows が配列でない")
    if len(rows) > MAX_ROWS:
        raise LedgerLintError("too-many-rows", f"行数が上限 {MAX_ROWS} を超過")
    findings = []
    for key in sorted(set(data) - set(TOPLEVEL_FIELDS)):
        findings.append(make_finding(
            f"{name}#(file)", "unknown-key",
            f"トップレベルに未知キー {key!r}",
            "未知キーは fail-closed（typo がサイレントに無視される事故防止）",
            "キーを削除するか、schema_version / rows に修正する"))
    return rows, findings


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def make_finding(where, check, what, why, how):
    return {"where": where, "check": check, "what": what, "why": why,
            "how": how}


def finalize_findings(findings):
    """Mask secrets in free-text diagnostic fields (never in where — it holds
    file paths and row IDs that masking would destroy), strip control
    characters everywhere, and sort deterministically."""
    out = []
    for f in findings:
        g = dict(f)
        for key in ("what", "why", "how"):
            g[key] = secret_detect.mask_secrets(g[key])
        for key in ("where", "what", "why", "how"):
            g[key] = _CTRL_RE.sub("", g[key])
        out.append(g)
    out.sort(key=lambda f: (f["where"], f["check"], f["what"]))
    return out


# ---------------------------------------------------------------------------
# Value validators
# ---------------------------------------------------------------------------

def _check_string(findings, where, field, value, required):
    if not isinstance(value, str):
        findings.append(make_finding(
            where, "invalid-type",
            f"{field} が string でない（{type(value).__name__}）",
            "型が契約と異なると digest 算出と機械検証が壊れる",
            f"{field} を非空の string にする"))
        return
    if not value:
        check = "empty-required-string" if required else "empty-string"
        findings.append(make_finding(
            where, check, f"{field} が空文字列",
            "「値なし」は空文字列でなくキー省略で表現する規則（任意フィールドのみ可）",
            f"{field} に内容を書くか、任意フィールドならキーごと削除する"))


def _check_string_array(findings, where, field, value):
    if not isinstance(value, list):
        findings.append(make_finding(
            where, "invalid-type",
            f"{field} が配列でない（{type(value).__name__}）",
            "型が契約と異なると機械検証が成立しない",
            f"{field} を string の配列にする"))
        return
    for i, item in enumerate(value):
        if not isinstance(item, str):
            findings.append(make_finding(
                where, "invalid-type",
                f"{field}[{i}] が string でない（{type(item).__name__}）",
                "array[string] の要素は非空 string のみ",
                f"{field}[{i}] を string にする"))
        elif not item:
            findings.append(make_finding(
                where, "empty-string", f"{field}[{i}] が空文字列",
                "array[string] の要素は非空が必須（検証の共通規則）",
                f"{field}[{i}] に内容を書くか要素を削除する"))


def _check_revision(findings, where, field, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        findings.append(make_finding(
            where, "invalid-revision",
            f"{field} が正整数でない: {value!r}",
            "revision は 1 以上の単調増加カウンタ（主張の意味変更ごとに +1）",
            f"{field} を 1 以上の整数にする"))


def _check_object_fields(findings, where, prefix, obj, spec):
    """Validate a nested object (approval / delegation) against a field spec:
    unknown keys, missing required, string/integer types."""
    for key in sorted(set(obj) - set(spec)):
        findings.append(make_finding(
            where, "unknown-key",
            f"{prefix} に未知キー {key!r}",
            "未知キーは fail-closed（書いたつもりの契約が消える事故防止）",
            f"{prefix} のキーを {'/'.join(spec)} に限定する"))
    for field, (token, required) in spec.items():
        if field not in obj:
            if required:
                findings.append(make_finding(
                    where, "missing-required",
                    f"{prefix} に必須キー {field} が欠落",
                    f"{prefix} は必須フィールドが揃って初めて検証可能になる",
                    f"{prefix} に {field} を追加する"))
            continue
        value = obj[field]
        if token == "integer":
            _check_revision(findings, where, f"{prefix}.{field}", value)
        else:
            _check_string(findings, where, f"{prefix}.{field}", value, required)


def _check_approval_authenticity(findings, where, row, approval):
    """Enforce the approval真正性 rules once approval's own fields are valid:
    row_id / revision / digest / actor_kind / prior_state consistency."""
    row_id = approval.get("row_id")
    if isinstance(row_id, str) and row_id and row_id != row.get("id"):
        findings.append(make_finding(
            where, "approval-row-id-mismatch",
            f"approval.row_id が行 ID と不一致: {row_id!r}",
            "承認イベントは所属する行を指していなければ真正でない",
            "approval.row_id を所属行の id に一致させる"))
    a_rev = approval.get("revision")
    row_rev = row.get("revision")
    # Compare only when both revisions are valid positive ints — a malformed
    # row.revision already gets its own invalid-revision finding, and comparing
    # against it would double-report noise, not a real mismatch.
    if isinstance(a_rev, int) and not isinstance(a_rev, bool) \
            and isinstance(row_rev, int) and not isinstance(row_rev, bool) \
            and row_rev >= 1 and a_rev != row_rev:
        findings.append(make_finding(
            where, "approval-revision-mismatch",
            f"approval.revision が行 revision と不一致（{a_rev} != {row_rev}）",
            "主張が承認後に改訂された（提示 revision と現 revision がずれた）= 再裁定必須",
            "主張を再提示して裁定し直し、承認を取り直す（承認を手で書き換えない）"))
    digest = approval.get("digest")
    if isinstance(digest, str) and digest and digest != compute_digest(row):
        findings.append(make_finding(
            where, "approval-digest-mismatch",
            "approval.digest が主張本文から再算出した digest と不一致",
            "主張本文（claim / term_refs）が承認後に変わった = 承認は失効、再裁定必須",
            "主張を再提示して裁定し直し、承認を取り直す（LLM は承認記録を自作できない）"))
    actor = approval.get("actor_kind")
    if isinstance(actor, str) and actor and actor not in ACTOR_KINDS:
        findings.append(make_finding(
            where, "approval-actor-not-human",
            f"approval.actor_kind が human でない: {actor!r}",
            "AGREED の承認者は人間のみ（LLM は提案者になれるが承認者になれない）",
            "actor_kind を human にする。人間の承認がないなら AGREED にしない"))
    prior = approval.get("prior_state")
    if isinstance(prior, str) and prior and prior not in STATES:
        findings.append(make_finding(
            where, "invalid-prior-state",
            f"approval.prior_state が状態 enum 外: {prior!r}",
            f"prior_state は {'/'.join(STATES)} のいずれか",
            f"prior_state を {'/'.join(STATES)} のいずれかにする"))


def _scan_secrets(findings, where, row):
    hits = []
    for field in _SECRET_SCAN_STRINGS:
        value = row.get(field)
        if isinstance(value, str) and secret_detect.detect_secrets(value):
            hits.append(field)
    for field in _SECRET_SCAN_ARRAYS:
        value = row.get(field)
        if isinstance(value, list) and any(
                isinstance(v, str) and secret_detect.detect_secrets(v)
                for v in value):
            hits.append(field)
    for field in hits:
        findings.append(make_finding(
            where, "secret-in-free-text",
            f"{field} に credential らしき文字列を検出",
            "自由文フィールドは合成・匿名データ限定（機密情報の規約）",
            f"{field} から実在の credential・個人情報を除去し合成データに差し替える"))


def _check_row(findings, name, index, row, context_terms):
    """Validate one ledger row. Return (id, state); id is None unless it
    matches ID_PATTERN (invalid ids never become where labels or known ids)."""
    if not isinstance(row, dict):
        findings.append(make_finding(
            f"{name}#rows[{index}]", "invalid-type",
            f"行が object でない（{type(row).__name__}）",
            "行は envelope フィールドを持つ object",
            "行を id/revision/state/claim を持つ object にする"))
        return None, None
    cid = row.get("id")
    cid_valid = isinstance(cid, str) and bool(cid) \
        and _ID_RE.fullmatch(cid) is not None
    label = cid if cid_valid else f"rows[{index}]"
    where = f"{name}#{label}"

    for key in sorted(set(row) - set(ROW_FIELDS)):
        findings.append(make_finding(
            where, "unknown-key",
            f"envelope に未知キー {key!r}",
            "未知キーは fail-closed（typo がサイレントに無視される事故防止）",
            f"キーを削除するか envelope のフィールド名（{'/'.join(ROW_FIELDS)}）に修正する"))

    for field, (token, required) in ROW_FIELDS.items():
        if field not in row:
            if required:
                findings.append(make_finding(
                    where, "missing-required",
                    f"必須フィールド {field} が欠落",
                    "envelope 必須フィールドが揃わない行は合意として不完全",
                    f"{field} を追加する"))
            continue
        value = row[field]
        if field == "revision":
            _check_revision(findings, where, "revision", value)
        elif token == "string":
            _check_string(findings, where, field, value, required)
        elif token == "array[string]":
            _check_string_array(findings, where, field, value)
        elif token == "object":
            if not isinstance(value, dict):
                findings.append(make_finding(
                    where, "invalid-type",
                    f"{field} が object でない（{type(value).__name__}）",
                    f"{field} は必須キーを持つ object",
                    f"{field} を object にする"))

    if isinstance(cid, str) and cid and not cid_valid:
        findings.append(make_finding(
            where, "invalid-id",
            f"id がパターン {ID_PATTERN} に合わない: {cid!r}",
            "ID は namespace 付き ASCII 識別子（例: NAV-001）に固定されている",
            "id を大文字英数セグメント + 3 桁以上の連番の形式にする"))

    state = row.get("state")
    if isinstance(state, str) and state and state not in STATES:
        findings.append(make_finding(
            where, "unknown-state",
            f"state が enum 外: {state!r}",
            f"合意状態は {'/'.join(STATES)} の 5 値のみ",
            f"state を {'/'.join(STATES)} のいずれかにする"))

    _check_attachments(findings, where, state, row)
    _check_epistemic_separation(findings, where, row)
    _check_term_refs(findings, where, row, context_terms)
    _scan_secrets(findings, where, row)
    return (cid if cid_valid else None), state


def _check_attachments(findings, where, state, row):
    permitted = STATE_ATTACHMENT.get(state) if isinstance(state, str) else None
    for att in ATTACHMENTS:
        if att in row and att != permitted:
            findings.append(make_finding(
                where, "attachment-not-allowed",
                f"state={state!r} の行に {att} は付与できない",
                "各状態が許す随伴フィールドは 1 つだけ（未裁定・却下は随伴物を持てない）",
                f"{att} を削除するか、state を {att} が必須の状態に修正する"))
    if permitted and permitted not in row:
        findings.append(make_finding(
            where, _MISSING_SLUG[permitted],
            f"state={state} の行に必須の {permitted} がない",
            "この状態は随伴フィールドが揃って初めて実装の根拠にできる",
            f"{permitted} を追加するか、未裁定なら state を UNDECIDED にする"))
    # deep-validate the attachment that matches the state
    if state == "AGREED" and isinstance(row.get("approval"), dict):
        approval = row["approval"]
        _check_object_fields(findings, where, "approval", approval,
                             APPROVAL_FIELDS)
        _check_approval_authenticity(findings, where, row, approval)
    if state == "DELEGATED" and isinstance(row.get("delegation"), dict):
        _check_object_fields(findings, where, "delegation", row["delegation"],
                             DELEGATION_FIELDS)


def _check_epistemic_separation(findings, where, row):
    obs = row.get("observations")
    asm = row.get("assumptions")
    if isinstance(obs, list) and isinstance(asm, list):
        shared = {x for x in obs if isinstance(x, str)} & \
                 {x for x in asm if isinstance(x, str)}
        if shared:
            findings.append(make_finding(
                where, "observation-assumption-conflation",
                "observations と assumptions が同一要素を共有",
                "観測（事実）と仮説（前提）を混ぜると裁定の質が崩れる（3 分離の破れ）",
                "同一項目をどちらか一方に振り分け、観測と仮説を分離する"))


def _check_term_refs(findings, where, row, context_terms):
    if context_terms is None:
        return
    refs = row.get("term_refs")
    if not isinstance(refs, list):
        return
    for t in refs:
        if isinstance(t, str) and t and t not in context_terms:
            findings.append(make_finding(
                where, "undefined-term",
                f"term_refs が CONTEXT 未定義の語彙を参照: {t}",
                "未定義語への参照は意味の揺れを台帳に持ち込む（語彙層のドリフト）",
                f"CONTEXT.md に {t} を定義するか、term_refs を実在 ID に直す"))


# ---------------------------------------------------------------------------
# Core lint
# ---------------------------------------------------------------------------

def lint_data(named_files, context_terms=None, baseline_undecided_ids=None):
    """Lint parsed ledger files [(name, data), ...]. Never raises: file
    structure corruption becomes a diagnostic (exit-2 class), row-level
    violations become findings (exit-1 class under --strict)."""
    findings = []
    diagnostics = []
    row_total = 0
    present_ids = set()
    per_file_ids = []

    for name, data in named_files:
        try:
            rows, top_findings = validate_toplevel(data, name)
        except LedgerLintError as e:
            diagnostics.append({"file": name, "category": e.category,
                                "message": secret_detect.mask_secrets(e.message)})
            continue
        findings.extend(top_findings)
        row_total += len(rows)
        ids_here = {}
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                rid = row.get("id")
                if isinstance(rid, str) and rid:
                    present_ids.add(rid)
            try:
                cid, _state = _check_row(findings, name, index, row,
                                         context_terms)
            except Exception:
                # fail-closed safety net: a lint over untrusted input must never
                # crash. Any unforeseen row-processing error becomes an exit-2
                # diagnostic (internal-error), never a leaked traceback.
                diagnostics.append({
                    "file": name, "category": "internal-error",
                    "message": f"行 {index} の処理中に予期しない例外"})
                continue
            if cid is None:
                continue
            ids_here[cid] = ids_here.get(cid, 0) + 1
        per_file_ids.append((name, ids_here))

    for name, ids_here in per_file_ids:
        for cid, count in sorted(ids_here.items()):
            if count > 1:
                findings.append(make_finding(
                    f"{name}#{cid}", "duplicate-id",
                    f"id がファイル内で重複（{count} 回出現）",
                    "同一ファイル内の ID 重複は禁止（どちらが正か決定できない）",
                    "片方の行に新しい ID を採番する（既存 ID の再利用は禁止）"))

    if baseline_undecided_ids:
        for missing in sorted(set(baseline_undecided_ids) - present_ids):
            findings.append(make_finding(
                f"(baseline)#{missing}", "undecided-vanished",
                f"前版の UNDECIDED 行 {missing} が現版から無断消滅",
                "未裁定の合意が承認・却下の記録なく消えるのは黙って上書き（diff 不変条件違反）",
                f"{missing} を現版に残すか、状態遷移（AGREED/REJECTED 等）として明示する"))

    findings = finalize_findings(findings)
    by_check = {}
    for f in findings:
        by_check[f["check"]] = by_check.get(f["check"], 0) + 1
    return {
        "findings": findings,
        "diagnostics": diagnostics,
        "corrupt": bool(diagnostics),
        "findings_present": bool(findings),
        "summary": {
            "files": len(named_files),
            "corrupt_files": len(diagnostics),
            "rows": row_total,
            "findings": len(findings),
            "by_check": by_check,
            "truncated": False,
        },
    }


def _merge_diagnostics(result, extra_diagnostics, total_files):
    result["diagnostics"] = extra_diagnostics + result["diagnostics"]
    result["corrupt"] = bool(result["diagnostics"])
    result["summary"]["files"] = total_files
    result["summary"]["corrupt_files"] = len(result["diagnostics"])
    return result


def lint_paths(paths, names=None, context_terms=None,
               baseline_undecided_ids=None):
    """Load + lint ledger files. Load failures join the diagnostics (the run
    still collects findings from healthy files, but exits 2 overall)."""
    display = list(names) if names is not None else list(paths)
    entries = []
    load_diagnostics = []
    for path, name in zip(paths, display):
        try:
            entries.append((name, load_ledger_file(path)))
        except LedgerLintError as e:
            load_diagnostics.append({
                "file": name, "category": e.category,
                "message": secret_detect.mask_secrets(e.message)})
    return _merge_diagnostics(
        lint_data(entries, context_terms=context_terms,
                  baseline_undecided_ids=baseline_undecided_ids),
        load_diagnostics, len(display))


# ---------------------------------------------------------------------------
# CONTEXT vocabulary + baseline loading
# ---------------------------------------------------------------------------

def load_context_terms(path):
    """Return the set of term IDs defined in a CONTEXT vocabulary file
    (context-vocabulary.md 機械可読形式). Fail-closed on corruption — a broken
    vocabulary must not silently disable term checks. schema_version is
    validated for consistency with the main loader (unknown version rejected)."""
    data = load_ledger_file(path)  # reuses the fail-closed JSON loader
    if not isinstance(data, dict):
        raise LedgerLintError(
            "not-an-object", "CONTEXT 語彙ファイルのトップレベルが object でない")
    version = data.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) \
            or version != SCHEMA_VERSION:
        raise LedgerLintError(
            "unknown-schema-version",
            f"CONTEXT schema_version が未知（v1 は {SCHEMA_VERSION} 固定）")
    if not isinstance(data.get("terms"), list):
        raise LedgerLintError("not-an-object", "CONTEXT terms が配列でない")
    terms = set()
    for item in data["terms"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str) \
                and item["id"]:
            terms.add(item["id"])
    return terms


def load_baseline_undecided_ids(path):
    """Return the set of row IDs that were UNDECIDED in a baseline ledger.
    Fail-closed: structural corruption raises (validate_toplevel) so the CLI
    exits 2 rather than silently no-op'ing the diff invariant — symmetric with
    the main ledger loader."""
    data = load_ledger_file(path)
    rows, _findings = validate_toplevel(data, path)
    ids = set()
    for row in rows:
        if isinstance(row, dict) and row.get("state") == "UNDECIDED" \
                and isinstance(row.get("id"), str) and row["id"]:
            ids.add(row["id"])
    return ids


# ---------------------------------------------------------------------------
# Path containment
# ---------------------------------------------------------------------------

def check_containment(path, root):
    """Reject any target outside root. Symlinks are checked on every existing
    component BEFORE canonicalization, then realpath() + commonpath() confirms
    canonical containment."""
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(path)
    try:
        rel = os.path.relpath(path_abs, root_abs)
    except ValueError:
        raise LedgerLintError("path-escape", f"対象が root 外: {path}")
    if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
        raise LedgerLintError("path-escape", f"対象が root 外: {path}")
    current = root_abs
    for part in rel.split(os.sep):
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise LedgerLintError(
                "path-escape", f"symlink を含むパスは拒否: {path}")
    resolved = os.path.realpath(path_abs)
    root_resolved = os.path.realpath(root_abs)
    if os.path.commonpath([resolved, root_resolved]) != root_resolved:
        raise LedgerLintError("path-escape", f"対象が root 外に解決される: {path}")
    return resolved


# ---------------------------------------------------------------------------
# Output (summary-first, stable order)
# ---------------------------------------------------------------------------

def sanitize_line(line):
    return _CTRL_RE.sub("", line)


def render_text(result):
    s = result["summary"]
    lines = [
        f"ledger_lint summary: files={s['files']} corrupt={s['corrupt_files']} "
        f"rows={s['rows']} findings={s['findings']}"
        + (" (表示は --max-errors で打ち切り)" if s["truncated"] else "")]
    if s["files"] == 0:
        lines.append("対象 0 件: 台帳ファイルが見つからない")
    for d in result["diagnostics"]:
        lines.append(f"[{d['file']}] input-corruption({d['category']}): "
                     f"{d['message']}")
    for f in result["findings"]:
        lines.append(f"[{f['where']}] {f['check']}: {f['what']} | "
                     f"why: {f['why']} | fix: {f['how']}")
    if not result["diagnostics"] and not result["findings"] and s["files"]:
        lines.append("違反なし: 全台帳ファイルが schema v1 に適合")
    return "\n".join(sanitize_line(line) for line in lines)


def render_json(result):
    return json.dumps({
        "valid": not result["corrupt"],
        "findings_present": result["findings_present"],
        "summary": result["summary"],
        "diagnostics": result["diagnostics"],
        "findings": result["findings"],
    }, indent=2, ensure_ascii=False)


def exit_code(result, strict):
    if result["corrupt"]:
        return 2
    if strict and result["findings_present"]:
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="合意台帳ファイルの構造 lint（schema v1）")
    parser.add_argument("paths", nargs="*",
                        help="台帳ファイル（省略時は <root>/ledger/*.json）")
    parser.add_argument("--root", required=True,
                        help="対象プロジェクトルート（containment 境界）")
    parser.add_argument("--context",
                        help="CONTEXT 語彙ファイル（指定時のみ term_refs を検証）")
    parser.add_argument("--baseline",
                        help="前版台帳（指定時のみ UNDECIDED 無断消滅を検証）")
    parser.add_argument("--strict", action="store_true",
                        help="検出ありを exit 1 にする（既定は report-only）")
    parser.add_argument("--json", action="store_true", help="JSON で出力する")
    parser.add_argument("--max-errors", type=int, default=200,
                        help="findings の表示上限（サマリーは全件を数える）")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"usage-error: root がディレクトリでない: {args.root}",
              file=sys.stderr)
        return 2

    context_terms = None
    if args.context:
        try:
            context_terms = load_context_terms(
                check_containment(args.context, root))
        except LedgerLintError as e:
            print(f"usage-error: CONTEXT 語彙ファイルが不正 ({e.category})",
                  file=sys.stderr)
            return 2

    baseline_ids = None
    if args.baseline:
        try:
            baseline_ids = load_baseline_undecided_ids(
                check_containment(args.baseline, root))
        except LedgerLintError as e:
            print(f"usage-error: baseline 台帳が不正 ({e.category})",
                  file=sys.stderr)
            return 2

    paths = args.paths or sorted(
        glob.glob(os.path.join(root, "ledger", "*.json")))

    contained = []
    containment_diagnostics = []
    for path in paths:
        try:
            resolved = check_containment(path, root)
        except LedgerLintError as e:
            containment_diagnostics.append({
                "file": path, "category": e.category, "message": e.message})
            continue
        contained.append((resolved, os.path.relpath(resolved, root)))

    result = lint_paths([p for p, _n in contained],
                        names=[n for _p, n in contained],
                        context_terms=context_terms,
                        baseline_undecided_ids=baseline_ids)
    result = _merge_diagnostics(result, containment_diagnostics, len(paths))

    if args.max_errors >= 0 and len(result["findings"]) > args.max_errors:
        result["findings"] = result["findings"][:args.max_errors]
        result["summary"]["truncated"] = True

    print(render_json(result) if args.json else render_text(result))
    return exit_code(result, args.strict)


if __name__ == "__main__":
    sys.exit(main())
