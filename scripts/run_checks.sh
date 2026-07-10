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

echo "=== All checks passed"
