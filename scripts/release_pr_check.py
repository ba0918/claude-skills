#!/usr/bin/env python3
"""release 品質ゲートの機械確認: Unreleased の各エントリ → PR → merged + 必須 check 済み。

release.yml の human attestation（semantic_reviewed checkbox）を廃止し（#308）、
「未リリース節の各エントリが参照する PR がマージ済みかつ必須チェック通過」を
`gh` で機械確認する方式へ置き換えた。このスクリプトはその内側の純粋なパース部分
を担う:

- `## Unreleased` 節を 1 つのみ検出し、`###` 見出しをエントリ単位として抽出する
- 各エントリが `(#NNN)` 形式で参照する PR 番号を収集する（検証対象）
- PR 参照を持たないエントリは、`none — 理由` 形式の明示免除表記を要求する。
  理由の無い `none` は免除ではなくエラー（黙ってスキップされる状態を作らない）

機械確認（merged + checks 通過）そのものは release.yml の `gh` ステップが行い、
このスクリプトはそこへ渡す検証対象 PR リストを組み立てる。パース規則は単体で
検証できるよう純関数にしている。
"""

import re
import sys

_UNRELEASED_HEADING_RE = re.compile(r"^## Unreleased[ \t]*$", re.MULTILINE)
_VERSION_HEADING_RE = re.compile(r"^## [0-9]+\.[0-9]+\.[0-9]+[ \t]*$", re.MULTILINE)
_ENTRY_HEADING_RE = re.compile(r"^### (.+?)[ \t]*$", re.MULTILINE)
_PR_REF_RE = re.compile(r"[（(]#([0-9]+)[)）]")
_EXEMPT_RE = re.compile(r"none[ \t]*—[ \t]*(.+)")
_NONE_MARKER_RE = re.compile(r"none[ \t]*—")


class ReleasePrCheckError(Exception):
    """Unreleased 節が機械確認の前提を満たさない。"""


def extract_unreleased(changelog):
    """Unreleased 節のエントリから検証対象 PR と免除を抽出する純関数。

    戻り値: (prs, errors, exempt)
    - prs: 検証対象の PR 番号（昇順・重複なし）
    - errors: 機械確認の前提を満たさないエントリの説明（無ければ空）
    - exempt: `none — 理由` で免除されたエントリ見出しのリスト
    """
    match = _UNRELEASED_HEADING_RE.search(changelog)
    if match is None:
        return [], ["Unreleased 節が存在しない"], []

    section_start = match.end()
    version_match = _VERSION_HEADING_RE.search(changelog, section_start)
    section_end = version_match.start() if version_match else len(changelog)
    section = changelog[section_start:section_end]

    entries = _split_entries(section)
    prs, errors, exempt = set(), [], []
    for heading, body in entries:
        entry_text = f"{heading}\n{body}"
        refs = sorted({int(pr) for pr in _PR_REF_RE.findall(entry_text)})
        if refs:
            prs.update(refs)
            continue
        if _EXEMPT_RE.search(entry_text):
            exempt.append(heading)
            continue
        if _NONE_MARKER_RE.search(entry_text):
            errors.append(
                f"エントリ「{heading}」は PR 参照がなく、`none — 理由` の免除も理由が空"
            )
            continue
        errors.append(
            f"エントリ「{heading}」は PR 参照（(#NNN)）がなく、"
            "`none — 理由` の免除表記もない"
        )
    return sorted(prs), errors, exempt


def _split_entries(section):
    """`###` 見出しでエントリを分割する。見出し無しの節はエントリ 0 件。"""
    matches = list(_ENTRY_HEADING_RE.finditer(section))
    entries = []
    for index, heading_match in enumerate(matches):
        start = heading_match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        entries.append((heading_match.group(1), section[start:end]))
    return entries


def checks_pass(rollup):
    """statusCheckRollup の配列を機械判定する純関数。

    merged な PR の必須 check が通ったかを判定する。実行待ち（status != COMPLETED）
    の check は「未完了」として扱う（保留 check のまま通したとは言えない）。
    conclusion が SUCCESS / NEUTRAL / SKIPPED の完了 check のみを通過とみなす。
    `status` を持たないエントリ（PullRequestReview など check でない行）は判定対象外。
    """
    if not isinstance(rollup, list):
        return False
    for item in rollup:
        if not isinstance(item, dict):
            return False
        if "status" not in item:
            continue
        if item.get("status") != "COMPLETED":
            return False
        if item.get("conclusion") not in (None, "SUCCESS", "NEUTRAL", "SKIPPED"):
            return False
    return True


def run(argv=None):
    """CLI: CHANGELOG パスを受け、検証対象 PR を 1 行 1 件で出力する。

    exit 0 = 検証対象 PR を出力（無ければ何も出ない）
    exit 1 = 前提違反（PR 参照も免除表記も無いエントリ、Unreleased 節欠落など）
    """
    args = argv or sys.argv[1:]
    if not args:
        print("usage: release_pr_check.py <CHANGELOG.md>", file=sys.stderr)
        return 2
    try:
        with open(args[0], encoding="utf-8") as handle:
            changelog = handle.read()
    except OSError as exc:
        print(f"release pr check: cannot read {args[0]}: {exc}", file=sys.stderr)
        return 1

    prs, errors, exempt = extract_unreleased(changelog)
    for error in errors:
        print(f"release pr check: {error}", file=sys.stderr)
    if errors:
        return 1
    for pr in prs:
        print(pr)
    for heading in exempt:
        print(f"# exempt: {heading}", file=sys.stderr)
    return 0


def main():
    try:
        sys.exit(run())
    except (ReleasePrCheckError, OSError) as exc:
        print(f"release pr check: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
