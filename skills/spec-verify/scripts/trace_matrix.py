#!/usr/bin/env python3
"""spec-verify: clause <-> test traceability matrix (evidence manifest v1).

The vocabulary source of truth is references/evidence-manifest.md; the
constants below mirror its tables and are kept in sync by test_trace_matrix.
Assurance-level derivation rules live in references/clause-schema.md (保証
レベル節) — this script implements them, it does not redefine them.

Reused from spec_lint (not reimplemented): SpecLintError, the fail-closed
JSON loader, validate_toplevel, check_containment, make_finding /
finalize_findings (field-aware secret masking + stable sort), sanitize_line,
and the exit-code contract (exit_code).

Exit codes (contract table in clause-schema.md):
  0 = run succeeded (report-only default: even with findings; zero targets too)
  1 = findings present, --strict only (warnings never affect the exit code)
  2 = input corruption / usage error. Diagnostics-only output marked
      valid: false — assurance derivation, matrix publication and --output
      writes are all suppressed (partial results are never published).
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_lint as sl  # noqa: E402

# ---------------------------------------------------------------------------
# Schema constants (single source: references/evidence-manifest.md)
# ---------------------------------------------------------------------------

MANIFEST_SCHEMA_VERSION = 1

MANIFEST_TOPLEVEL_FIELDS = {
    "schema_version": ("integer", True),
    "bindings": ("array[object]", True),
    "observations": ("array[object]", True),
}

BINDING_FIELDS = {
    "clause_id": ("string", True),
    "clause_revision": ("integer", True),
    "test_id": ("string", True),
}

OBSERVATION_FIELDS = {
    "clause_id": ("string", True),
    "test_id": ("string", True),
    "evidence_kind": ("string", True),
    "command": ("string", True),
    "exit_status": ("integer", True),
    "cases_valid": ("integer", True),
    "failures": ("integer", True),
    "payload_digest": ("string", True),
    "recorded_at": ("string", True),
    "cases_discarded": ("integer", False),
    "skipped": ("boolean", False),
    "xfail": ("boolean", False),
}

EVIDENCE_KINDS = ("example", "property")

# 先頭は英数に限定する: 先頭 `-` の識別子はランナー呼び出し時にオプションと
# 誤解釈され得る（呼び出し側の `--` セパレータ規約と二重の防御）。
TEST_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:\[\]/=,-]{0,499}$"
DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"

_TEST_ID_RE = re.compile(TEST_ID_PATTERN)
_DIGEST_RE = re.compile(DIGEST_PATTERN)
_CLAUSE_ID_RE = re.compile(sl.ID_PATTERN)

# 非負が必須の整数フィールド（exit_status は負値もランナー実態としてあり得る
# ため対象外 — シグナル死は負の status で表現される）。
_NON_NEGATIVE_FIELDS = ("cases_valid", "failures", "cases_discarded")

FINDING_CHECKS = (
    "unverified-clause",
    "dangling-clause-reference",
    "stale-evidence",
    "missing-required",
    "invalid-type",
    "unknown-key",
    "invalid-test-id",
    "invalid-clause-ref",
    "invalid-digest",
    "invalid-value",
)
WARNING_CHECKS = (
    "binding-revision-mismatch",
    "unknown-evidence-kind",
    "observation-without-binding",
    "undigestable-clause",
    "duplicate-clause-id",
)

DRAFTS_RELDIR = os.path.join(".agents", "artifacts", "spec-verify", "drafts")

# v1 の信頼境界（evidence-manifest.md）。レポートに常に出力する。
TRUST_NOTES = (
    "observation は手続き信頼（v1）: 実行記録の真正性は機械検証していない",
    "drift 検知の保証範囲は条項側の変更のみ（test drift は検知しない）",
)


# ---------------------------------------------------------------------------
# Clause payload digest (rules: evidence-manifest.md 識別子・digest の形式規則)
# ---------------------------------------------------------------------------

def _reject_floats(node):
    stack = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, float):
            # float の処理系依存表記を digest 入力に許すと、同一条項の digest
            # が環境で割れる。v1 スキーマの payload に数値型はないため禁止で足りる。
            raise ValueError("digest 正規化は float を禁止する")
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


def clause_digest(clause):
    """SHA-256 over the canonical JSON of id + revision + kind + payload only
    (statement 等の文言修正で証拠が stale 化しないための算出対象の限定)。"""
    subset = {"id": clause["id"], "revision": clause["revision"],
              "kind": clause["kind"], "payload": clause["payload"]}
    _reject_floats(subset)
    canonical = json.dumps(subset, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Manifest validation (structure-only; cross-checks happen in trace())
# ---------------------------------------------------------------------------

def _check_entry(findings, where, entry, fields, label):
    """Validate one binding/observation entry. Return the entry when it is
    structurally sound, else None (broken entries never join the matrix —
    半端なエントリを保証算出に混ぜると壊れた証拠が昇格し得るため除外する)。"""
    if not isinstance(entry, dict):
        findings.append(sl.make_finding(
            where, "invalid-type",
            f"{label} エントリが object でない（{type(entry).__name__}）",
            "エントリは evidence-manifest.md の表のキーを持つ object",
            f"{label} エントリを object にする"))
        return None
    ok = True
    for key in sorted(set(entry) - set(fields)):
        findings.append(sl.make_finding(
            where, "unknown-key",
            f"{label} エントリに未知キー {key!r}",
            "未知キーは fail-closed（typo がサイレントに無視される事故防止）",
            f"キーを削除するか {'/'.join(fields)} に修正する"))
        ok = False
    for field, (token, required) in fields.items():
        if field not in entry:
            if required:
                findings.append(sl.make_finding(
                    where, "missing-required",
                    f"{label} エントリに必須キー {field} が欠落",
                    "必須キーが揃わないエントリは証拠として評価できない",
                    f"{field} を追加する"))
                ok = False
            continue
        value = entry[field]
        if token == "string":
            if not isinstance(value, str):
                findings.append(sl.make_finding(
                    where, "invalid-type",
                    f"{field} が string でない（{type(value).__name__}）",
                    "型が契約と異なるエントリは評価対象外",
                    f"{field} を非空の string にする"))
                ok = False
            elif not value:
                findings.append(sl.make_finding(
                    where, "invalid-value", f"{field} が空文字列",
                    "必須 string の空文字列は欠落と同じ違反",
                    f"{field} に内容を書く"))
                ok = False
        elif token == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                findings.append(sl.make_finding(
                    where, "invalid-type",
                    f"{field} が integer でない（{type(value).__name__}）",
                    "型が契約と異なるエントリは評価対象外",
                    f"{field} を整数にする"))
                ok = False
            elif field == "clause_revision" and value < 1:
                findings.append(sl.make_finding(
                    where, "invalid-value",
                    f"clause_revision が 1 未満: {value}",
                    "revision は 1 以上の単調増加カウンタ",
                    "binding 時点の条項 revision（1 以上）を記録する"))
                ok = False
            elif field in _NON_NEGATIVE_FIELDS and value < 0:
                findings.append(sl.make_finding(
                    where, "invalid-value",
                    f"{field} が負: {value}",
                    "ケース数・失敗数は 0 以上の観測値",
                    f"{field} に実際の観測値（0 以上）を記録する"))
                ok = False
        elif token == "boolean":
            if not isinstance(value, bool):
                findings.append(sl.make_finding(
                    where, "invalid-type",
                    f"{field} が boolean でない（{type(value).__name__}）",
                    "型が契約と異なるエントリは評価対象外",
                    f"{field} を true / false にする"))
                ok = False
    cid = entry.get("clause_id")
    if isinstance(cid, str) and cid and not _CLAUSE_ID_RE.fullmatch(cid):
        findings.append(sl.make_finding(
            where, "invalid-clause-ref",
            f"clause_id が条項 ID パターンに合わない: {cid!r}",
            "条項参照は clause-schema.md の ID パターンに固定されている",
            "clause_id を実在する条項 ID（例: LIB-INV-001）にする"))
        ok = False
    tid = entry.get("test_id")
    if isinstance(tid, str) and tid and not _TEST_ID_RE.fullmatch(tid):
        findings.append(sl.make_finding(
            where, "invalid-test-id",
            "test_id が文字集合規則に合わない",
            "空白・シェルメタ文字・制御文字は識別子として構造的に禁止",
            "test_id を evidence-manifest.md のパターンに従う識別子にする"))
        ok = False
    digest = entry.get("payload_digest")
    if isinstance(digest, str) and digest and not _DIGEST_RE.fullmatch(digest):
        findings.append(sl.make_finding(
            where, "invalid-digest",
            "payload_digest が形式規則（sha256: + 64 hex）に合わない",
            "digest 形式が違うと stale 判定が成立しない",
            "drift-check 手順で現行 payload digest を記録し直す"))
        ok = False
    return entry if ok else None


def validate_manifest(data, name):
    """Validate manifest structure. Raise SpecLintError for file-level
    corruption (exit-2 class); entry-level violations become findings and the
    broken entries are excluded. Returns (bindings, observations, findings)."""
    if not isinstance(data, dict):
        raise sl.SpecLintError("not-an-object",
                               "マニフェストのトップレベルが object でない")
    missing = [k for k, (_t, req) in MANIFEST_TOPLEVEL_FIELDS.items()
               if req and k not in data]
    if missing:
        raise sl.SpecLintError(
            "missing-toplevel-key",
            f"マニフェストの必須キーが欠落: {', '.join(missing)}")
    version = data["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) \
            or version != MANIFEST_SCHEMA_VERSION:
        raise sl.SpecLintError(
            "unknown-schema-version",
            f"schema_version が未知（v1 は {MANIFEST_SCHEMA_VERSION} 固定）")
    for key in ("bindings", "observations"):
        if not isinstance(data[key], list):
            raise sl.SpecLintError(
                "manifest-key-not-array", f"{key} が配列でない")

    findings = []
    for key in sorted(set(data) - set(MANIFEST_TOPLEVEL_FIELDS)):
        findings.append(sl.make_finding(
            f"{name}#(file)", "unknown-key",
            f"マニフェストのトップレベルに未知キー {key!r}",
            "未知キーは fail-closed（typo がサイレントに無視される事故防止）",
            f"キーを削除するか {'/'.join(MANIFEST_TOPLEVEL_FIELDS)} に修正する"))
    bindings = []
    for i, entry in enumerate(data["bindings"]):
        checked = _check_entry(findings, f"{name}#bindings[{i}]", entry,
                               BINDING_FIELDS, "binding")
        if checked is not None:
            bindings.append(checked)
    observations = []
    for i, entry in enumerate(data["observations"]):
        checked = _check_entry(findings, f"{name}#observations[{i}]", entry,
                               OBSERVATION_FIELDS, "observation")
        if checked is not None:
            observations.append(checked)
    return bindings, observations, findings


# ---------------------------------------------------------------------------
# Clause index (digest inputs only — full schema validation is spec_lint's job)
# ---------------------------------------------------------------------------

def _collect_clauses(named_files, warnings, diagnostics):
    index = {}
    for name, data in named_files:
        try:
            clauses, _top_findings = sl.validate_toplevel(data, name)
        except sl.SpecLintError as e:
            diagnostics.append({"file": name, "category": e.category,
                                "message": e.message})
            continue
        for i, clause in enumerate(clauses):
            cid = clause.get("id") if isinstance(clause, dict) else None
            cid_valid = isinstance(cid, str) and bool(cid) \
                and _CLAUSE_ID_RE.fullmatch(cid) is not None
            # 不正 id は where ラベルに使わない（spec_lint と同じ理由:
            # where は mask 対象外なので credential 形の生値が露出し得る）。
            where = f"{name}#{cid if cid_valid else f'clauses[{i}]'}"
            broken = (
                not isinstance(clause, dict) or not cid_valid
                or isinstance(clause.get("revision"), bool)
                or not isinstance(clause.get("revision"), int)
                or clause["revision"] < 1
                or not isinstance(clause.get("kind"), str)
                or not clause["kind"]
                or not isinstance(clause.get("payload"), dict))
            digest = None
            if not broken:
                try:
                    digest = clause_digest(clause)
                except ValueError:
                    broken = True
            if broken:
                warnings.append(sl.make_finding(
                    where, "undigestable-clause",
                    "digest 算出に必要な envelope（id/revision/kind/payload）が壊れている",
                    "digest が算出できない条項は突合・stale 判定に参加できない",
                    "spec_lint を実行して条項を schema v1 に修正する"))
                # 索引から外さない: 外すと実在条項への binding / observation が
                # dangling-clause-reference（error）に化ける。undigestable は
                # 「存在するが digest 判定に参加できない」条項として索引に置き、
                # 保証レベル判定のみスキップする（evidence-manifest.md 検出項目）。
                if cid_valid and cid not in index:
                    index[cid] = {
                        "file": name,
                        "revision": None,
                        "digest": None,
                        "tombstone": isinstance(clause, dict)
                        and "superseded_by" in clause,
                        "predicates": False,
                        "undigestable": True,
                    }
                continue
            if cid in index:
                warnings.append(sl.make_finding(
                    where, "duplicate-clause-id",
                    f"条項 ID が重複定義されている: {cid}",
                    "突合索引は先に読んだ定義を採用する（どちらが正か機械決定できない）",
                    "片方の条項に新しい ID を採番する"))
                continue
            index[cid] = {
                "file": name,
                "revision": clause["revision"],
                "digest": digest,
                "tombstone": "superseded_by" in clause,
                "predicates": bool(clause.get("predicates")),
                "undigestable": False,
            }
    return index


# ---------------------------------------------------------------------------
# Core trace (dict-indexed many-to-many join)
# ---------------------------------------------------------------------------

def _corrupt_result(diagnostics, notes, clause_files):
    return {
        "corrupt": True,
        "diagnostics": diagnostics,
        "findings": [],
        "warnings": [],
        "matrix": [],
        "findings_present": False,
        "notes": list(notes),
        "summary": {
            "clause_files": clause_files,
            "corrupt_files": len(diagnostics),
            "clauses_active": 0,
            "tombstones": 0,
            "draft_files": 0,
            "bindings": 0,
            "observations": 0,
            "levels": {"property": 0, "example_only": 0, "unverified": 0},
            "escape_hatch": {"used": 0, "active": 0, "rate_percent": None},
            "findings": 0,
            "warnings": 0,
            "by_check": {},
            "truncated": False,
        },
    }


def trace(named_clause_files, manifest_data, manifest_name="manifest.json",
          draft_files=0):
    """Join clause files with the evidence manifest. Publish nothing on input
    corruption (diagnostics-only result, exit-2 class)."""
    notes = list(TRUST_NOTES)
    findings = []
    warnings = []
    diagnostics = []

    index = _collect_clauses(named_clause_files, warnings, diagnostics)

    bindings, observations = [], []
    if manifest_data is None:
        notes.append(
            "証拠マニフェストが見つからない（specs/evidence/manifest.json）: "
            "証拠ゼロとして全現役条項を unverified 扱いにする")
    else:
        try:
            bindings, observations, manifest_findings = validate_manifest(
                manifest_data, manifest_name)
            findings.extend(manifest_findings)
        except sl.SpecLintError as e:
            diagnostics.append({"file": manifest_name, "category": e.category,
                                "message": e.message})

    if diagnostics:
        return _corrupt_result(diagnostics, notes, len(named_clause_files))

    if not named_clause_files:
        notes.append("対象 0 件: 条項ファイルが見つからない（specs/clauses/*.json）")

    # undigestable 条項は active にも tombstone 件数にも入れない
    # （実在はするが保証レベル判定をスキップする — 索引には参照解決用に残る）。
    active = {cid: info for cid, info in index.items()
              if not info["tombstone"] and not info["undigestable"]}
    tombstone_count = sum(1 for info in index.values()
                          if info["tombstone"] and not info["undigestable"])

    bound_tests = {}
    pairs = set()
    for entry in bindings:
        cid = entry["clause_id"]
        where = f"{manifest_name}#{cid}"
        if cid not in index:
            findings.append(sl.make_finding(
                where, "dangling-clause-reference",
                f"binding が存在しない条項 ID を参照: {cid}",
                "実在しない条項への binding はドリフト（条項の削除・改名）の兆候",
                "条項を復元するか binding を実在 ID に付け替える"))
            continue
        if index[cid]["tombstone"] or index[cid]["undigestable"]:
            continue
        pairs.add((cid, entry["test_id"]))
        bound_tests.setdefault(cid, set()).add(entry["test_id"])
        if entry["clause_revision"] != index[cid]["revision"]:
            warnings.append(sl.make_finding(
                where, "binding-revision-mismatch",
                f"binding の clause_revision ({entry['clause_revision']}) が"
                f"現行 revision ({index[cid]['revision']}) と不一致",
                "revision は補助情報であり stale 判定は digest が行う（警告に留める）",
                "binding の clause_revision を現行値に更新する"))

    effective = {}
    for entry in observations:
        cid = entry["clause_id"]
        where = f"{manifest_name}#{cid}"
        if cid not in index:
            findings.append(sl.make_finding(
                where, "dangling-clause-reference",
                f"observation が存在しない条項 ID を参照: {cid}",
                "実在しない条項への観測記録はドリフトの兆候",
                "条項を復元するか observation を除去する"))
            continue
        info = index[cid]
        if info["tombstone"] or info["undigestable"]:
            continue
        if (cid, entry["test_id"]) not in pairs:
            warnings.append(sl.make_finding(
                where, "observation-without-binding",
                "binding 未宣言のペアに対する observation（証拠に数えない）",
                "binding は人間レビューを経た宣言であり、未宣言ペアの観測は"
                "保証算出に参加させない",
                "bind ワークフローで binding を宣言してから observation を記録する"))
            continue
        kind = entry["evidence_kind"]
        if kind not in EVIDENCE_KINDS:
            warnings.append(sl.make_finding(
                where, "unknown-evidence-kind",
                f"evidence_kind が未知: {kind!r}",
                "前方互換規則: 未知・未対応の証拠種別は warning + unverified 扱い"
                "（エラーにしない）",
                f"v1 で算出可能な種別（{'/'.join(EVIDENCE_KINDS)}）で記録し直す"))
            continue
        if entry["payload_digest"] != info["digest"]:
            findings.append(sl.make_finding(
                where, "stale-evidence",
                f"observation の payload digest が現行条項と不一致"
                f"（test: {entry['test_id']}）",
                "条項 payload の意味変更後に再検証されていない（文言修正では"
                "stale 化しない）",
                "テストを条項の現行 payload に追随させ、drift-check で"
                "observation を記録し直す"))
            continue
        if entry["exit_status"] != 0 or entry["failures"] != 0 \
                or entry["cases_valid"] < 1:
            continue
        if entry.get("skipped") or entry.get("xfail"):
            continue
        effective.setdefault(cid, []).append(entry)

    matrix = []
    levels = {"property": 0, "example_only": 0, "unverified": 0}
    for cid in sorted(active):
        info = active[cid]
        entries = effective.get(cid, [])
        kinds = [e["evidence_kind"] for e in entries]
        if "property" in kinds:
            level = "property"
        elif "example" in kinds:
            level = "example_only"
        else:
            level = "unverified"
            findings.append(sl.make_finding(
                f"{info['file']}#{cid}", "unverified-clause",
                "有効な証拠がゼロ（unverified）",
                "「問題なし」ではなく「見ていない」— binding の宣言だけでは昇格しない",
                "bind ワークフローでテストを束縛し、drift-check で observation を"
                "記録する"))
        levels[level] += 1
        matrix.append({
            "clause": cid,
            "revision": info["revision"],
            "level": level,
            "tests": sorted(bound_tests.get(cid, ())),
            "effective_observations": len(entries),
            "cases_valid_total": sum(e["cases_valid"] for e in entries),
            # recorded_at は表示専用の自由文であり、辞書順 max は ISO 8601
            # UTC 前提の表示値にすぎない（stale 判定には使わない）。
            "last_recorded_at": max(
                (e["recorded_at"] for e in entries), default=None),
            "digest": info["digest"],
        })

    findings = sl.finalize_findings(findings)
    warnings = sl.finalize_findings(warnings)
    hatch_used = sum(1 for info in active.values() if info["predicates"])
    by_check = {}
    for f in findings + warnings:
        by_check[f["check"]] = by_check.get(f["check"], 0) + 1
    return {
        "corrupt": False,
        "diagnostics": [],
        "findings": findings,
        "warnings": warnings,
        "matrix": matrix,
        "findings_present": bool(findings),
        "notes": notes,
        "summary": {
            "clause_files": len(named_clause_files),
            "corrupt_files": 0,
            "clauses_active": len(active),
            "tombstones": tombstone_count,
            "draft_files": draft_files,
            "bindings": len(bindings),
            "observations": len(observations),
            "levels": levels,
            "escape_hatch": {
                "used": hatch_used,
                "active": len(active),
                "rate_percent": (round(100.0 * hatch_used / len(active), 1)
                                 if active else None),
            },
            "findings": len(findings),
            "warnings": len(warnings),
            "by_check": by_check,
            "truncated": False,
        },
    }


# ---------------------------------------------------------------------------
# Baseline diff (new detections only; fail-open to the full report)
# ---------------------------------------------------------------------------

def apply_baseline(result, baseline_data):
    known = set()
    if isinstance(baseline_data, dict):
        for f in baseline_data.get("findings", ()):
            if isinstance(f, dict):
                known.add((f.get("where"), f.get("check"), f.get("what")))
    new = [f for f in result["findings"]
           if (f["where"], f["check"], f["what"]) not in known]
    suppressed = len(result["findings"]) - len(new)
    result["findings"] = new
    result["findings_present"] = bool(new)
    result["summary"]["findings"] = len(new)
    result["summary"]["baseline_suppressed"] = suppressed
    # by_check も抑制後に再計算する: 抑制前の全件を数えたままだと
    # summary.findings と矛盾し、by_check で判定する機械消費者が誤読する。
    # 抑制件数は baseline_suppressed が持つ。
    by_check = {}
    for f in result["findings"] + result["warnings"]:
        by_check[f["check"]] = by_check.get(f["check"], 0) + 1
    result["summary"]["by_check"] = by_check
    result["notes"].append(
        f"baseline diff: 既知 {suppressed} 件を抑制し、新規検出のみ表示")
    return result


# ---------------------------------------------------------------------------
# Rendering (summary-first, deterministic; no generation timestamp)
# ---------------------------------------------------------------------------

def _cell(value):
    return sl.sanitize_line(str(value)).replace("\\", "\\\\") \
        .replace("|", "\\|")


def render_markdown(result):
    s = result["summary"]
    lines = ["# trace matrix（条項 ⇔ テスト突合）", "", "## Summary", ""]
    lines.append(
        f"- 条項ファイル: {s['clause_files']}（破損 {s['corrupt_files']}）/ "
        f"現役条項: {s['clauses_active']} / "
        f"tombstone: {s['tombstones']}（集計対象外・別掲）/ "
        f"draft: {s['draft_files']}（探索対象外・件数のみ）")
    lines.append(f"- binding: {s['bindings']} / observation: {s['observations']}")
    levels = s["levels"]
    lines.append(
        f"- 保証レベル: property={levels['property']} "
        f"example_only={levels['example_only']} "
        f"unverified={levels['unverified']}")
    lines.append(f"- 検出: findings={s['findings']} / warnings={s['warnings']}"
                 + ("（表示は --max-errors で打ち切り）" if s["truncated"] else ""))
    hatch = s["escape_hatch"]
    rate = "n/a" if hatch["rate_percent"] is None \
        else f"{hatch['rate_percent']}%"
    lines.append(
        f"- escape hatch（predicates 参照）: {hatch['used']}/{hatch['active']}"
        f"（{rate}）")
    lines.append("- 注記:")
    for note in result["notes"]:
        lines.append(f"  - {_cell(note)}")
    if result["diagnostics"]:
        lines.append("")
        lines.append("## 入力破損（診断のみ・マトリクスは publish しない）")
        lines.append("")
        for d in result["diagnostics"]:
            lines.append(f"- [{_cell(d['file'])}] "
                         f"input-corruption({d['category']}): "
                         f"{_cell(d['message'])}")
        return "\n".join(lines) + "\n"
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    if result["matrix"]:
        lines.append("| 条項 | revision | 保証レベル | tests | 有効 observation |")
        lines.append("|------|----------|-----------|-------|-------------------|")
        for row in result["matrix"]:
            tests = ", ".join(_cell(t) for t in row["tests"]) or "（なし）"
            lines.append(
                f"| {_cell(row['clause'])} | {row['revision']} | "
                f"{row['level']} | {tests} | "
                f"{row['effective_observations']} |")
    else:
        lines.append("（現役条項なし）")
    for title, key in (("Findings", "findings"), ("Warnings", "warnings")):
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        if result[key]:
            for f in result[key]:
                lines.append(
                    f"- [{_cell(f['where'])}] {f['check']}: {_cell(f['what'])}"
                    f" — why: {_cell(f['why'])} — fix: {_cell(f['how'])}")
        else:
            lines.append("（なし）")
    return "\n".join(lines) + "\n"


def render_json(result):
    return json.dumps({
        "valid": not result["corrupt"],
        "findings_present": result["findings_present"],
        "summary": result["summary"],
        "notes": result["notes"],
        "matrix": result["matrix"],
        "findings": result["findings"],
        "warnings": result["warnings"],
        "diagnostics": result["diagnostics"],
    }, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# --output guard (containment + .git/specs rejection + explicit overwrite)
# ---------------------------------------------------------------------------

def check_output_path(path, root, force):
    resolved = sl.check_containment(path, root)
    rel = os.path.relpath(resolved, os.path.realpath(os.path.abspath(root)))
    top = rel.split(os.sep)[0]
    if top in (".git", "specs"):
        raise sl.SpecLintError(
            "output-rejected",
            f"--output は {top}/ 配下に書けない（正本ツリー・VCS 内部の保護）")
    if os.path.exists(resolved) and not force:
        raise sl.SpecLintError(
            "output-rejected",
            "--output 先が既に存在する（上書きは --force を明示する）")
    return resolved


def _write_atomic(path, text):
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                                    prefix=".trace_matrix.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="spec-verify 条項⇔テストのトレーサビリティマトリクス生成")
    parser.add_argument("paths", nargs="*",
                        help="条項ファイル（省略時は <root>/specs/clauses/*.json）")
    parser.add_argument("--root", required=True,
                        help="対象プロジェクトルート（containment 境界）")
    parser.add_argument("--manifest",
                        help="証拠マニフェスト（省略時は "
                             "<root>/specs/evidence/manifest.json）")
    parser.add_argument("--strict", action="store_true",
                        help="検出ありを exit 1 にする（既定は report-only）")
    parser.add_argument("--json", action="store_true", help="JSON で出力する")
    parser.add_argument("--baseline",
                        help="前回の JSON 出力。新規検出のみ表示"
                             "（読めない場合は全件レポートにフォールバック）")
    parser.add_argument("--output",
                        help="レポートの書き込み先（root 内のみ。"
                             ".git/・specs/ 配下は拒否）")
    parser.add_argument("--force", action="store_true",
                        help="--output の既存ファイル上書きを許可する")
    parser.add_argument("--max-errors", type=int, default=200,
                        help="findings の表示上限（サマリーは全件を数える）")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"usage-error: root がディレクトリでない: {args.root}",
              file=sys.stderr)
        return 2

    output_path = None
    if args.output:
        try:
            output_path = check_output_path(args.output, root, args.force)
        except sl.SpecLintError as e:
            print(f"usage-error({e.category}): {e.message}", file=sys.stderr)
            return 2

    clause_paths = args.paths or sorted(
        glob.glob(os.path.join(root, "specs", "clauses", "*.json")))
    diagnostics = []
    named_files = []
    for path in clause_paths:
        try:
            resolved = sl.check_containment(path, root)
            name = os.path.relpath(resolved, root)
            named_files.append((name, sl.load_clause_file(resolved)))
        except sl.SpecLintError as e:
            # mask しない: containment/load 診断の message はパス・型名のみで、
            # マスク（home_path 等）はパス情報を破壊し原因特定を不能にする。
            diagnostics.append({"file": path, "category": e.category,
                                "message": e.message})

    manifest_path = args.manifest or os.path.join(
        root, "specs", "evidence", "manifest.json")
    manifest_name = "specs/evidence/manifest.json"
    manifest_data = None
    try:
        resolved = sl.check_containment(manifest_path, root)
        manifest_name = os.path.relpath(resolved, root)
        if os.path.exists(resolved):
            manifest_data = sl.load_clause_file(resolved)
        elif args.manifest:
            # 明示指定の不存在は「証拠ゼロ続行」にしない: typo したパスが
            # 黙って全件 unverified に化けるのを防ぐ。既定パス（暗黙）の
            # 不存在のみ証拠ゼロとして続行する。
            print("usage-error(manifest-not-found): --manifest 指定の"
                  f"ファイルが存在しない: {args.manifest}", file=sys.stderr)
            return 2
    except sl.SpecLintError as e:
        diagnostics.append({"file": manifest_path, "category": e.category,
                            "message": e.message})

    draft_files = len(glob.glob(
        os.path.join(root, DRAFTS_RELDIR, "*.json")))

    result = trace(named_files, manifest_data, manifest_name=manifest_name,
                   draft_files=draft_files)
    if diagnostics:
        merged = diagnostics + result["diagnostics"]
        result = _corrupt_result(merged, result["notes"], len(clause_paths))

    if args.baseline and not result["corrupt"]:
        try:
            with open(args.baseline, encoding="utf-8") as f:
                baseline_data = json.load(f)
            result = apply_baseline(result, baseline_data)
        except (OSError, ValueError):
            result["notes"].append(
                "baseline が読めないため全件レポートにフォールバック")

    if args.max_errors >= 0 and len(result["findings"]) > args.max_errors:
        result["findings"] = result["findings"][:args.max_errors]
        result["summary"]["truncated"] = True

    rendered = render_json(result) if args.json else render_markdown(result)
    print(rendered, end="" if rendered.endswith("\n") else "\n")

    if output_path and not result["corrupt"]:
        try:
            _write_atomic(output_path, rendered)
        except OSError as e:
            print(f"usage-error(output-unwritable): {type(e).__name__}",
                  file=sys.stderr)
            return 2

    return sl.exit_code(result, args.strict)


if __name__ == "__main__":
    sys.exit(main())
