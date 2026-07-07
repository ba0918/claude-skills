"""機械センサー adapter — validate_repo.py / ledger.py --check / context-audit の出力を
Finding Schema へ正規化する。

契約: skills/shared/references/loop-engineering.md
  - §2 Finding Schema
  - §7 Sensor Adapter 契約

標準ライブラリのみ使用。パース関数（parse_validate_output / parse_ledger_check /
map_context_audit）は純関数（副作用なし・入力を変異しない）。subprocess 実行は main のみが行う
薄い I/O 層であり、テスト対象外。
"""

import argparse
import json
import os
import re
import subprocess
import sys

# validate_repo.py の違反行: "  [tag] メッセージ"
_VALIDATE_LINE_RE = re.compile(r"^\s*\[([a-z0-9-]+)\]\s+(.+)$")

# メッセージ中の「実在しそうなパス風トークン」の最初の一致
_PATH_TOKEN_RE = re.compile(r"[\w./-]+\.(?:md|py|json|yml|yaml|sh)")

# ledger.py --check の行: "[stale] skill: detail" / "[unverified] skill: detail"
_LEDGER_LINE_RE = re.compile(r"^\[(stale|unverified)\]\s+([^:]+):\s*(.*)$")


def parse_validate_output(text):
    """validate_repo.py の stdout/stderr 結合テキストから違反行を Finding のリストに変換する。

    「✓ 全チェック合格」（違反なし）の場合は空リストを返す。
    """
    findings = []
    for line in text.splitlines():
        match = _VALIDATE_LINE_RE.match(line)
        if not match:
            continue
        tag = match.group(1)
        message = match.group(2)
        path_match = _PATH_TOKEN_RE.search(message)
        path = path_match.group(0) if path_match else "."
        findings.append({
            "sensor": "validate-repo",
            "rule": tag,
            "severity": "BLOCK",
            "fix_action": "NEEDS_JUDGMENT",
            "where": {"path": path},
            "what": line.strip(),
            "suggested_title": f"validate: [{tag}] を解消する",
            "affected_paths": [path] if path != "." else [],
        })
    return findings


def parse_ledger_check(text):
    """ledger.py --check 出力の [stale] / [unverified] 行を Finding のリストに変換する。

    全スキル検証済み（stale/unverified 行なし）の場合は空リストを返す。
    """
    findings = []
    for line in text.splitlines():
        stripped = line.strip()
        match = _LEDGER_LINE_RE.match(stripped)
        if not match:
            continue
        rule = match.group(1)
        skill = match.group(2).strip()
        detail = match.group(3)
        if rule == "stale":
            affected_paths = [p.strip() for p in detail.split(",") if p.strip()]
        else:
            affected_paths = []
        findings.append({
            "sensor": "ledger-check",
            "rule": rule,
            "severity": "WARN",
            "fix_action": "NEEDS_JUDGMENT",
            "where": {"path": f"skills/{skill}/fixtures.json"},
            "what": stripped,
            "suggested_title": f"skill-regression: {skill} を再評価する",
            "affected_paths": affected_paths,
        })
    return findings


def _parse_where(where_str):
    """"path:line" または "path" を (path, line|None) に分解する。"""
    if ":" in where_str:
        path_part, _, line_part = where_str.rpartition(":")
        if line_part.isdigit():
            return path_part, int(line_part)
    return where_str, None


def map_context_audit(findings):
    """context-audit の finding のリストを Finding Schema へ写像する。

    severity が "PASS" の finding は問題なしのため出力に含めない。
    """
    result = []
    for finding in findings:
        if finding.get("severity") == "PASS":
            continue
        where_str = finding.get("where", "")
        path, line = _parse_where(where_str)
        where = {"path": path}
        if line is not None:
            where["line"] = line
        what = finding.get("what", "")
        rule_id = finding.get("id")
        mapped = {
            "sensor": "context-audit",
            "rule": rule_id,
            "severity": finding.get("severity"),
            "fix_action": finding.get("fix_action"),
            "where": where,
            "what": what,
            "suggested_title": f"context-audit: {rule_id} {what[:40]}",
            "affected_paths": [path],
        }
        # SKILL Step 5 の「概要 = what + why」用に why を落とさない（任意フィールド）
        if finding.get("why"):
            mapped["why"] = finding["why"]
        result.append(mapped)
    return result


def _run_capture(cmd, cwd):
    """cmd を実行し stdout+stderr 結合テキストを返す。失敗しても例外にせず空文字扱い。"""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False,
        )
    except OSError:
        return ""
    return (proc.stdout or "") + (proc.stderr or "")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="validate_repo.py / ledger.py --check を実行し Finding JSON を出力する",
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--context-audit", metavar="PATH", default=None,
        help="context-audit の findings JSON（リスト）。map_context_audit で写像して結合する",
    )
    args = parser.parse_args(argv)

    root = os.path.abspath(args.repo_root)
    validate_script = os.path.join(root, "scripts", "validate_repo.py")
    ledger_script = os.path.join(
        root, "skills", "skill-regression", "scripts", "ledger.py",
    )

    validate_text = _run_capture([sys.executable, validate_script, root], root)
    ledger_text = _run_capture([sys.executable, ledger_script, "--check", root], root)

    findings = parse_validate_output(validate_text) + parse_ledger_check(ledger_text)

    if args.context_audit:
        with open(args.context_audit, encoding="utf-8") as f:
            raw = json.load(f)
        findings += map_context_audit(raw)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(findings, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
