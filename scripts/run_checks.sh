#!/bin/sh
# CI (.github/workflows/validate.yml) と pre-push hook (githooks/pre-push) の
# 両方から呼ばれる検証の正本。チェックを追加・変更するときはこのファイルだけを編集する。
set -eu

echo "=== Unit tests (all script dirs)"
# test_*.py を含む全 scripts ディレクトリを自動発見して実行する。
# ディレクトリをハードコードすると新スキルのテストが黙って CI から漏れる
# （実際に context-audit の 96 テストが漏れていた）ため、列挙はしない。
found=0
for dir in scripts skills/*/scripts; do
  if ls "$dir"/test_*.py >/dev/null 2>&1; then
    echo "--- $dir"
    python3 -m unittest discover -s "$dir" -t "$dir" -p 'test_*.py'
    found=1
  fi
done
test "$found" -eq 1  # 1 件も見つからないのは発見ロジック側の壊れ

echo "=== Repo consistency checks"
python3 scripts/validate_repo.py

echo "=== Regression ledger check"
python3 skills/skill-regression/scripts/ledger.py --check .

# 翻訳による構造劣化（sensor:translation-damage）。fixture を持たないスキルでは
# これが唯一の劣化検出手段なので、翻訳を含む push / PR では必ず通す。
# 日本語が減ったファイルだけを見るため、通常の編集では対象 0 件の no-op になる。
# baseline は $TRANSLATION_PARITY_BASELINE → origin/$GITHUB_BASE_REF → origin/main →
# main の順に解決し、どれも無い checkout では skip を明示出力して pass する
# （CI の checkout は fetch-depth: 0 が必要 — .github/workflows/validate.yml 参照）。
# pre-push hook は push ネゴシエーションで得た remote sha を環境変数で渡す。fetch
# していない作業ディレクトリの古い remote-tracking ref で偽 BLOCK を出さないため。
echo "=== Translation parity"
python3 scripts/check_translation_parity.py

# アンカー参照の飛び先。validate_repo.py のリンク検証はパス部分しか見ず `#` 以降を
# 捨てるため、見出しを改名して参照を取りこぼしても緑のままリンクだけ壊れる。
echo "=== Anchor references"
python3 scripts/check_anchors.py

echo "=== All checks passed"
