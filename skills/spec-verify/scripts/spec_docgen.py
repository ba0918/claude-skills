#!/usr/bin/env python3
"""spec-verify: deterministic read-only Markdown view of the clause corpus.

docgen renders specs/clauses/*.json（正本）+ specs/evidence/manifest.json を
人間可読の仕様ビューへ決定論的に変換する（LLM 不使用・標準ライブラリのみ）。
生成物は VIEW であって第二の正本ではない — 先頭のマーカー行と読み取り専用
ヘッダがそれを宣言し、--output の上書きゲートもマーカーで判定する。

Assurance levels and evidence totals are taken from trace_matrix.trace()
rows (evidence-manifest.md マトリクス行スキーマ) — docgen re-derives nothing.

Free text (statement / rationale / examples / recorded_at) is DATA: it is
embedded with raw-HTML / link-injection neutralizing escapes plus the same
field-aware secret masking as trace_matrix (ids / test_ids / digests are
charset-constrained and rendered verbatim in code spans).

Exit codes: 0 = view generated (docgen is not a gate — unverified clauses do
not fail the run; there is no --strict). 2 = input corruption / usage error;
nothing is written.
"""

import argparse
import glob
import html
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "shared", "scripts"))
import secret_detect  # noqa: E402
import spec_lint as sl  # noqa: E402
import trace_matrix as tm  # noqa: E402

# 上書きゲートは先頭行のこの接頭辞で判定する（マーカーなし = docgen 生成物で
# ない = 人間の文書かもしれない → --force なしでは上書きしない）。
MARKER_PREFIX = "<!-- spec-verify docgen:"
MARKER = (MARKER_PREFIX + " 自動生成ファイル — 編集禁止。"
          "正本は specs/clauses/（契約）と specs/evidence/manifest.json（証拠） -->")

SUMMARY_STATEMENT_LIMIT = 40

_ID_RE = re.compile(sl.ID_PATTERN)


# ---------------------------------------------------------------------------
# Free-text embedding (自由文はデータ — マスク + エスケープしてから埋め込む)
# ---------------------------------------------------------------------------

def _esc(text):
    text = str(text).replace("\r", " ").replace("\n", " ")
    text = sl.sanitize_line(secret_detect.mask_secrets(text))
    text = html.escape(text, quote=False)
    text = text.replace("\\", "\\\\")
    for ch in ("|", "`", "[", "]"):
        text = text.replace(ch, "\\" + ch)
    return text


def _summarize(statement):
    if not isinstance(statement, str) or not statement:
        return "（statement なし）"
    text = statement.replace("\r", " ").replace("\n", " ")
    if len(text) > SUMMARY_STATEMENT_LIMIT:
        text = text[:SUMMARY_STATEMENT_LIMIT] + "…"
    return _esc(text)


# ---------------------------------------------------------------------------
# Clause lookup for the view (matrix rows carry no statement/rationale)
# ---------------------------------------------------------------------------

def _clause_view_index(named_files):
    """Return (by_id, tombstones). First occurrence wins, matching the
    duplicate-id rule of trace_matrix's index."""
    by_id = {}
    tombstones = []
    seen_tombstones = set()
    for name, data in named_files:
        try:
            clauses, _findings = sl.validate_toplevel(data, name)
        except sl.SpecLintError:
            continue  # 破損ファイルは trace() 側で corrupt 扱い済み
        for clause in clauses:
            if not isinstance(clause, dict):
                continue
            cid = clause.get("id")
            if not isinstance(cid, str) or not _ID_RE.fullmatch(cid or ""):
                continue
            if "superseded_by" in clause:
                if cid not in seen_tombstones:
                    seen_tombstones.add(cid)
                    successors = clause.get("superseded_by")
                    tombstones.append(
                        (cid, successors if isinstance(successors, list)
                         else []))
            elif cid not in by_id:
                by_id[cid] = clause
    return by_id, tombstones


# ---------------------------------------------------------------------------
# Rendering (deterministic; no generation timestamp)
# ---------------------------------------------------------------------------

def _summary_lines(result):
    s = result["summary"]
    levels = s["levels"]
    lines = ["## サマリー", ""]
    lines.append(
        f"- 現役条項: {s['clauses_active']} / "
        f"tombstone: {s['tombstones']}（集計対象外・別掲）/ "
        f"draft: {s['draft_files']}（対象外・件数のみ）")
    lines.append(
        f"- 保証レベル: property={levels['property']} / "
        f"example_only={levels['example_only']} / "
        f"unverified={levels['unverified']}")
    lines.append(
        f"- drift 検出: findings={s['findings']} / warnings={s['warnings']}"
        "（詳細は drift-check を実行する）")
    lines.append("- 注記:")
    for note in result["notes"]:
        lines.append(f"  - {_esc(note)}")
    return lines


def _table_lines(result, by_id):
    lines = ["## 条項一覧", ""]
    if not result["matrix"]:
        lines.append("（現役条項なし）")
        return lines
    lines.append("| 条項 | rev | kind | 保証レベル | valid ケース | "
                 "最終検証（表示専用） | statement 要約 |")
    lines.append("|------|-----|------|-----------|--------------|"
                 "----------------------|----------------|")
    for row in result["matrix"]:
        clause = by_id.get(row["clause"], {})
        kind = clause.get("kind")
        last = _esc(row["last_recorded_at"]) if row["last_recorded_at"] \
            else "—"
        lines.append(
            f"| `{row['clause']}` | {row['revision']} | "
            f"{_esc(kind) if isinstance(kind, str) and kind else '?'} | "
            f"{row['level']} | {row['cases_valid_total']} | {last} | "
            f"{_summarize(clause.get('statement'))} |")
    return lines


def _detail_lines(result, by_id):
    lines = ["## 条項詳細", ""]
    if not result["matrix"]:
        lines.append("（なし）")
        return lines
    for row in result["matrix"]:
        clause = by_id.get(row["clause"], {})
        kind = clause.get("kind")
        statement = clause.get("statement")
        lines.append(f"### `{row['clause']}` — {row['level']}")
        lines.append("")
        lines.append(
            f"- kind: {_esc(kind) if isinstance(kind, str) and kind else '?'}"
            f" / revision: {row['revision']}")
        lines.append(
            "- statement: "
            + (_esc(statement) if isinstance(statement, str) and statement
               else "（statement なし — spec_lint で修正する）"))
        rationale = clause.get("rationale")
        if isinstance(rationale, str) and rationale:
            lines.append(f"- rationale: {_esc(rationale)}")
        for field in ("examples", "counterexamples"):
            value = clause.get(field)
            items = [v for v in value if isinstance(v, str) and v] \
                if isinstance(value, list) else []
            if items:
                lines.append(f"- {field}:")
                for item in items:
                    lines.append(f"  - {_esc(item)}")
        if row["tests"]:
            lines.append("- tests:")
            for tid in row["tests"]:
                lines.append(f"  - `{tid}`")
        else:
            lines.append("- tests: （binding なし）")
        lines.append(
            f"- 有効 observation: {row['effective_observations']}"
            f"（valid ケース合計 {row['cases_valid_total']} / "
            f"最終検証 {row['last_recorded_at'] or '—'}）")
        lines.append("")
    return lines[:-1] if lines[-1] == "" else lines


def _tombstone_lines(tombstones):
    lines = ["## tombstone（集計対象外・別掲）", ""]
    if not tombstones:
        lines.append("（なし）")
        return lines
    lines.append(f"- 件数: {len(tombstones)}")
    for cid, successors in tombstones:
        valid = [x for x in successors
                 if isinstance(x, str) and _ID_RE.fullmatch(x)]
        invalid = len(successors) - len(valid)
        succ = ", ".join(f"`{x}`" for x in valid) if valid \
            else "なし（後継なしの廃止）"
        if invalid:
            succ += f"（ID パターン外 {invalid} 件）"
        lines.append(f"- `{cid}` → 後継: {succ}")
    return lines


def render_view(named_clause_files, result):
    by_id, tombstones = _clause_view_index(named_clause_files)
    lines = [
        MARKER,
        "",
        "# 仕様ビュー（spec-verify docgen）",
        "",
        "> **自動生成・編集禁止**。このファイルは読み取り専用ビューであり、"
        "第二の正本ではない。",
        "> 契約の正本は `specs/clauses/*.json`、"
        "証拠の正本は `specs/evidence/manifest.json`。",
        "> 変更は正本を編集し、docgen で再生成する。",
        "",
    ]
    lines.extend(_summary_lines(result))
    lines.append("")
    lines.extend(_table_lines(result, by_id))
    lines.append("")
    lines.extend(_detail_lines(result, by_id))
    lines.append("")
    lines.extend(_tombstone_lines(tombstones))
    return "\n".join(lines) + "\n"


def generate(named_clause_files, manifest_data,
             manifest_name="specs/evidence/manifest.json", draft_files=0):
    """Trace + render. Returns (view, trace_result); view is None when the
    input is corrupt (exit-2 class — nothing may be published)."""
    result = tm.trace(named_clause_files, manifest_data,
                      manifest_name=manifest_name, draft_files=draft_files)
    if result["corrupt"]:
        return None, result
    return render_view(named_clause_files, result), result


# ---------------------------------------------------------------------------
# --output guard (containment + 正本ツリー保護 + marker-gated overwrite)
# ---------------------------------------------------------------------------

def _has_marker(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readline().startswith(MARKER_PREFIX)
    except OSError:
        return False


def check_output_path(path, root, force):
    """trace_matrix の check_output_path と異なり specs/ 直下は許す（ビューの
    既定置き場 specs/SPEC.md のため）。正本ツリー（specs/clauses/ ·
    specs/evidence/）と .git/ は拒否のまま。"""
    resolved = sl.check_containment(path, root)
    rel = os.path.relpath(resolved, os.path.realpath(os.path.abspath(root)))
    parts = rel.split(os.sep)
    if parts[0] == ".git":
        raise sl.SpecLintError(
            "output-rejected", "--output は .git/ 配下に書けない（VCS 内部の保護）")
    if parts[0] == "specs" and len(parts) > 1 \
            and parts[1] in ("clauses", "evidence"):
        raise sl.SpecLintError(
            "output-rejected",
            f"--output は specs/{parts[1]}/ 配下に書けない（正本ツリーの保護）")
    if os.path.exists(resolved) and not force and not _has_marker(resolved):
        raise sl.SpecLintError(
            "output-rejected",
            "--output 先が docgen 生成物でない既存ファイル"
            "（上書きは --force を明示する）")
    return resolved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="spec-verify 条項正本からの読み取り専用 Markdown ビュー生成"
                    "（決定論的・LLM 不使用）")
    parser.add_argument("paths", nargs="*",
                        help="条項ファイル（省略時は <root>/specs/clauses/*.json）")
    parser.add_argument("--root", required=True,
                        help="対象プロジェクトルート（containment 境界）")
    parser.add_argument("--manifest",
                        help="証拠マニフェスト（省略時は "
                             "<root>/specs/evidence/manifest.json）")
    parser.add_argument("--output",
                        help="ビューの書き込み先（root 内のみ。省略時は stdout "
                             "のみ。.git/・specs/clauses/・specs/evidence/ 配下"
                             "は拒否。既存ファイルは docgen マーカー付きのみ"
                             "上書き可）")
    parser.add_argument("--force", action="store_true",
                        help="--output の docgen マーカーなし既存ファイルの"
                             "上書きを許可する")
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
            print("usage-error(manifest-not-found): --manifest 指定の"
                  f"ファイルが存在しない: {args.manifest}", file=sys.stderr)
            return 2
    except sl.SpecLintError as e:
        diagnostics.append({"file": manifest_path, "category": e.category,
                            "message": e.message})

    draft_files = len(glob.glob(
        os.path.join(root, tm.DRAFTS_RELDIR, "*.json")))

    view, result = generate(named_files, manifest_data,
                            manifest_name=manifest_name,
                            draft_files=draft_files)
    if diagnostics or view is None:
        for d in diagnostics + result["diagnostics"]:
            print(f"input-corruption({d['category']}): [{d['file']}] "
                  f"{d['message']}", file=sys.stderr)
        return 2

    print(view, end="")
    if output_path:
        try:
            tm._write_atomic(output_path, view)
        except OSError as e:
            print(f"usage-error(output-unwritable): {type(e).__name__}",
                  file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
