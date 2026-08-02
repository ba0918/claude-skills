#!/usr/bin/env python3
"""skill-reviewer の出力が診断器の契約を満たすかを検証する（純関数 + 薄い CLI）。

skill-reviewer は診断器であってマージゲートではない。その性質は「診断器です」という
宣言では守られず、出力の型で守る。この検証器が拒否するのは次の 5 つで、いずれも
「診断が制御判断へ昇格する経路」を塞ぐためにある。

  1. 非証拠宣言 3 フィールドの欠落・改竄（品質ゲート証拠との誤認経路）
  2. dynamic_sensors_executed が空でない出力（実走センサーを回さない契約の破れ）
  3. qualification_reason を欠く BLOCK（既存の機械的証拠を指せない停止要求）
  4. diagnostics チャネルの BLOCK / AUTO_FIX（cycle の状態遷移への流入）
  5. 評価範囲（coverage）の申告なしに findings だけを述べる出力

契約の正本は references/output-contract.md、証拠 5 状態の意味論は
references/evidence-and-coverage.md にある。

CLI:
  python3 validate_review_output.py FILE   # FILE が `-` なら標準入力
  exit 0 = 適合 / 1 = 契約違反 / 2 = 読み取り・パース不能
"""

import json
import sys

ASSURANCE_ROLE = "diagnostic_only"

CONTROL_VERDICTS = ("BLOCK", "WARN")
DIAGNOSTIC_VERDICTS = ("WARN", "OPPORTUNITY", "INFO")
FIX_ACTIONS = ("AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY")
COVERAGE_VALUES = ("reviewed", "skipped", "unsupported", "inconclusive")
EVIDENCE_STATES = ("current_pass", "accepted_without_run", "stale", "uncovered", "invalid")

# 状態 → (実走が行われた記録か, その記録が現在の挙動面に適用可能か, 表示ラベル)。
# accepted_without_run と current_pass のラベルが同一になると「実走証拠あり」の
# 誤表示がここから生まれるため、両者は必ず別ラベルにする。
_EVIDENCE_SEMANTICS = {
    "current_pass": (True, True, "run-verified (applies to the current surface)"),
    "stale": (True, False, "run-verified but stale (the surface changed since)"),
    "accepted_without_run": (False, False, "accepted without a run (no run evidence)"),
    "uncovered": (False, False, "no fixture (uncovered)"),
    "invalid": (False, False, "record unusable (invalid)"),
}

_TOP_KEYS = {
    "assurance_role", "quality_gate_evidence", "dynamic_sensors_executed",
    "coverage", "evidence", "control_candidates", "diagnostics", "summary", "target",
}
_FINDING_KEYS = {
    "id", "verdict", "target", "summary", "qualification_reason", "fix_action", "detail",
}
_COVERAGE_KEYS = {"target", "value", "reason"}
_EVIDENCE_KEYS = {"skill", "state", "reason", "run_evidence", "surface_sha256"}


def classify_evidence(entry):
    """証拠エントリを 5 状態の意味論へ展開する。

    Raises: ValueError — state が 5 状態のいずれでもないとき。
    """
    state = entry.get("state")
    if state not in _EVIDENCE_SEMANTICS:
        raise ValueError(
            f"unknown evidence state: {state!r} (expected one of {list(EVIDENCE_STATES)})"
        )
    run_evidence, current, label = _EVIDENCE_SEMANTICS[state]
    return {
        "skill": entry.get("skill"),
        "state": state,
        "run_evidence": run_evidence,
        "current": current,
        "label": label,
    }


def _unknown_keys(mapping, allowed, where, errors):
    for key in sorted(set(mapping) - allowed):
        errors.append(f"[{where}] 未知のキー: {key}")


def _is_filled(value):
    return isinstance(value, str) and value.strip() != ""


def _check_declaration(document, errors):
    if "assurance_role" not in document:
        errors.append("[declaration] assurance_role がない（非証拠宣言は必須）")
    elif document["assurance_role"] != ASSURANCE_ROLE:
        errors.append(
            f"[declaration] assurance_role は {ASSURANCE_ROLE!r} 固定"
            f"（検出: {document['assurance_role']!r}）"
        )

    if "quality_gate_evidence" not in document:
        errors.append("[declaration] quality_gate_evidence がない（非証拠宣言は必須）")
    elif document["quality_gate_evidence"] is not False:
        errors.append(
            "[declaration] quality_gate_evidence は false 固定"
            "（診断器の出力は品質ゲート証拠ではない）"
        )

    if "dynamic_sensors_executed" not in document:
        errors.append("[declaration] dynamic_sensors_executed がない（非証拠宣言は必須）")
    elif not isinstance(document["dynamic_sensors_executed"], list):
        errors.append("[declaration] dynamic_sensors_executed は配列で申告する")
    elif document["dynamic_sensors_executed"]:
        errors.append(
            "[declaration] dynamic_sensors_executed が空でない: "
            f"{document['dynamic_sensors_executed']}"
            "（skill-reviewer は LLM 実走センサーを起動しない）"
        )


def _check_finding(finding, channel, index, seen_ids, errors):
    where = f"{channel}[{index}]"
    if not isinstance(finding, dict):
        errors.append(f"[{where}] finding はオブジェクトで書く")
        return
    _unknown_keys(finding, _FINDING_KEYS, where, errors)

    for key in ("id", "target", "summary"):
        if not _is_filled(finding.get(key)):
            errors.append(f"[{where}] {key} が空")
    finding_id = finding.get("id")
    if _is_filled(finding_id):
        if finding_id in seen_ids:
            errors.append(f"[{where}] id が重複している: {finding_id}")
        seen_ids.add(finding_id)

    allowed = CONTROL_VERDICTS if channel == "control_candidates" else DIAGNOSTIC_VERDICTS
    verdict = finding.get("verdict")
    if verdict not in allowed:
        errors.append(
            f"[{where}] {channel} に置ける verdict は {list(allowed)}"
            f"（検出: {verdict!r}）"
        )

    fix_action = finding.get("fix_action")
    if fix_action is not None and fix_action not in FIX_ACTIONS:
        errors.append(f"[{where}] fix_action は {list(FIX_ACTIONS)}（検出: {fix_action!r}）")

    if channel == "control_candidates":
        if verdict == "BLOCK" and not _is_filled(finding.get("qualification_reason")):
            errors.append(
                f"[{where}] BLOCK に qualification_reason がない"
                "（既存の機械的証拠を名指しできない指摘は BLOCK の資格がない）"
            )
        if not _is_filled(fix_action):
            errors.append(f"[{where}] fix_action が空（自動修正可否は明示する）")
    else:
        if fix_action == "AUTO_FIX":
            errors.append(
                f"[{where}] diagnostics に AUTO_FIX は置けない"
                "（診断チャネルは cycle の状態遷移に影響しない）"
            )
        if "qualification_reason" in finding:
            errors.append(
                f"[{where}] qualification_reason は control_candidates 専用"
                "（BLOCK 資格の申告であり診断には意味を持たない）"
            )


def _check_channel(document, channel, seen_ids, errors):
    findings = document.get(channel)
    if findings is None:
        errors.append(f"[{channel}] チャネルがない（空でも申告する）")
        return
    if not isinstance(findings, list):
        errors.append(f"[{channel}] チャネルは配列で書く")
        return
    for index, finding in enumerate(findings):
        _check_finding(finding, channel, index, seen_ids, errors)


def _check_coverage(document, errors):
    entries = document.get("coverage")
    if entries is None:
        errors.append("[coverage] coverage がない（評価範囲の申告は必須）")
        return
    if not isinstance(entries, list):
        errors.append("[coverage] coverage は配列で書く")
        return
    if not entries:
        errors.append(
            "[coverage] coverage が空"
            "（評価範囲を示せないなら findings の有無にかかわらず結論を述べられない）"
        )
        return
    for index, entry in enumerate(entries):
        where = f"coverage[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"[{where}] エントリはオブジェクトで書く")
            continue
        _unknown_keys(entry, _COVERAGE_KEYS, where, errors)
        if not _is_filled(entry.get("target")):
            errors.append(f"[{where}] target が空")
        value = entry.get("value")
        if value not in COVERAGE_VALUES:
            errors.append(f"[{where}] value は {list(COVERAGE_VALUES)}（検出: {value!r}）")
        if not _is_filled(entry.get("reason")):
            errors.append(f"[{where}] reason が空（理由なき評価範囲の申告は台帳として無効）")


def _check_evidence(document, errors):
    entries = document.get("evidence")
    if entries is None:
        errors.append("[evidence] evidence がない（参照した実走記録は空でも申告する）")
        return
    if not isinstance(entries, list):
        errors.append("[evidence] evidence は配列で書く")
        return
    for index, entry in enumerate(entries):
        where = f"evidence[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"[{where}] エントリはオブジェクトで書く")
            continue
        _unknown_keys(entry, _EVIDENCE_KEYS, where, errors)
        if not _is_filled(entry.get("skill")):
            errors.append(f"[{where}] skill が空")
        try:
            classified = classify_evidence(entry)
        except ValueError as exc:
            errors.append(f"[{where}] {exc}")
            continue
        declared = entry.get("run_evidence")
        if declared is not None and not isinstance(declared, bool):
            errors.append(f"[{where}] run_evidence は真偽値で書く（検出: {declared!r}）")
        elif declared is not None and declared != classified["run_evidence"]:
            errors.append(
                f"[{where}] run_evidence の申告が state と矛盾する: "
                f"state={classified['state']} は run_evidence={classified['run_evidence']}"
            )
        sha = entry.get("surface_sha256")
        if sha is not None and not isinstance(sha, str):
            errors.append(f"[{where}] surface_sha256 は文字列で書く（検出型: {type(sha).__name__}）")


def validate(document, source=None):
    """契約違反のメッセージ一覧を返す（空なら適合）。"""
    prefix = f"{source}: " if source else ""
    if not isinstance(document, dict):
        return [f"{prefix}[document] 出力はオブジェクトで書く"]
    errors = []
    _unknown_keys(document, _TOP_KEYS, "document", errors)
    _check_declaration(document, errors)
    _check_coverage(document, errors)
    _check_evidence(document, errors)
    seen_ids = set()
    _check_channel(document, "control_candidates", seen_ids, errors)
    _check_channel(document, "diagnostics", seen_ids, errors)
    return [prefix + message for message in errors]


def main(argv):
    if len(argv) != 1:
        print("usage: validate_review_output.py FILE|-", file=sys.stderr)
        return 2
    path = argv[0]
    try:
        raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"読み取れない: {exc}", file=sys.stderr)
        return 2
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"JSON として読めない: {exc}", file=sys.stderr)
        return 2
    errors = validate(document, source=None if path == "-" else path)
    if errors:
        for message in errors:
            print(message)
        return 1
    print("✓ skill-reviewer output contract: 適合")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
