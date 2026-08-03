#!/bin/sh
# CI (.github/workflows/validate.yml) と pre-push hook (githooks/pre-push) の
# 両方から呼ばれる検証の正本。チェックを追加・変更するときはこのファイルだけを編集する。
#
# STRICT_GATES=1 で呼ぶと、skip / no-op が 1 つでもあれば非 0 で落ちる。
# 証跡 (machine_verified) を書く前提の実行で使う。
set -eu

# --- 集約用カウンタ ---
_ran=0
_skipped=""

_mark_ran()    { _ran=$((_ran + 1)); }
_mark_skipped(){ _skipped="${_skipped:+$_skipped, }$1"; }

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
_mark_ran

echo "=== OpenCode plugin (static)"
node scripts/test_opencode_plugin.mjs
_mark_ran

echo "=== OpenCode plugin (runtime JSON path escaping)"
OPENCODE_RUNTIME_TEST_JSON_ESCAPE=1 sh scripts/test_opencode_runtime.sh
_mark_ran

# The static import check above cannot prove that OpenCode itself discovers the
# plugin and exposes bundled skills. CI installs OpenCode; developer machines
# without it retain the rest of the canonical checks and report this explicitly.
echo "=== OpenCode plugin (runtime)"
if command -v opencode >/dev/null 2>&1; then
  sh scripts/test_opencode_runtime.sh
  _mark_ran
else
  _mark_skipped "opencode-runtime (opencode unavailable)"
fi

echo "=== Repo consistency checks"
python3 scripts/validate_repo.py
_mark_ran

echo "=== Regression ledger check"
python3 skills/skill-regression/scripts/ledger.py --check .
_mark_ran

# 翻訳による構造劣化（sensor:translation-damage）。fixture を持たないスキルでは
# これが唯一の劣化検出手段なので、翻訳を含む push / PR では必ず通す。
# 日本語が減ったファイルだけを見るため、通常の編集では対象 0 件の no-op になる。
# baseline は $TRANSLATION_PARITY_BASELINE → origin/$GITHUB_BASE_REF → origin/main →
# main の順に解決し、どれも無い checkout では skip を明示出力して pass する
# （CI の checkout は fetch-depth: 0 が必要 — .github/workflows/validate.yml 参照）。
# pre-push hook は push ネゴシエーションで得た remote sha を環境変数で渡す。fetch
# していない作業ディレクトリの古い remote-tracking ref で偽 BLOCK を出さないため。
echo "=== Translation parity"
# 人間向けテキスト出力（従来どおり）
tp_text=$(python3 scripts/check_translation_parity.py 2>&1) || {
  echo "$tp_text"
  exit 1
}
echo "$tp_text"
# 構造化出力で実行状態を判定。skip 時は JSON が出ない（baseline 解決前に return）
tp_json=$(python3 scripts/check_translation_parity.py --json 2>/dev/null) || true
tp_checked=$(echo "$tp_json" | python3 -c "
import sys, json
raw = sys.stdin.read().strip()
if raw:
    try:
        print(json.loads(raw).get('checked', -1))
    except (json.JSONDecodeError, AttributeError):
        print(-1)
else:
    print(-1)
" 2>/dev/null) || tp_checked=-1
# 判定: skip テキスト → checked=0 (completed no-op) → checked>0 (ran) → それ以外 (unavailable)
# -1 やパース失敗を ran に倒すと fail-closed が破れるので、0 または正の整数だけを ran とする
case "$tp_text" in
  *"skip"*) _mark_skipped "translation-parity (skip: baseline unresolved or stale)" ;;
  *)
    if [ "$tp_checked" = "0" ]; then
      # baseline 解決済みの空集合は全対象を検査した結果ゼロ件の検査完了。
      # baseline 未解決や環境欠損による skip とは区別し、STRICT_GATES でも ran とする。
      _mark_ran
    elif echo "$tp_checked" | grep -qE '^[1-9][0-9]*$'; then
      _mark_ran
    else
      _mark_skipped "translation-parity (status unavailable: could not determine checked count)"
    fi
    ;;
esac

# アンカー参照の飛び先。validate_repo.py のリンク検証はパス部分しか見ず `#` 以降を
# 捨てるため、見出しを改名して参照を取りこぼしても緑のままリンクだけ壊れる。
echo "=== Anchor references"
python3 scripts/check_anchors.py
_mark_ran

# --- 最終サマリー ---
if [ -n "$_skipped" ]; then
  echo "=== ${_ran} checks passed, but some were skipped: ${_skipped}"
  if [ "${STRICT_GATES:-0}" = "1" ]; then
    echo "STRICT_GATES=1: skip/no-op is not allowed for evidence production"
    exit 1
  fi
else
  echo "=== All ${_ran} checks passed"
fi
