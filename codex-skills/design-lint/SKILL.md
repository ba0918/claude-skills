---
name: design-lint
description: プロジェクトのコードベースを .design/tokens.json に基づいて lint し、デザイントークン違反（直書きカラー・フォント・spacing等）を機械的に検出するスキル。CI にも組み込み可能。「デザインリント」「design lint」「トークン検証」で起動。
---

# Design Lint (Codex Edition)

プロジェクトのコードベースを `.design/tokens.json` に基づいて lint し、デザイントークン違反を機械的に検出する。

**共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md) を参照。
**lint ルール仕様:** [references/lint-contract.md](references/lint-contract.md) を参照。

## Codex CLI ツールの使い分け

- **shell** — lint エンジン `design_lint.py` の実行と結果解釈。`.design/tokens.json` 等の前提ファイルの存在確認（`ls` / `cat`）、`python3 "$SKILL_DIR/scripts/design_lint.py"` の呼び出し、終了コード `0`（PASS）/ `1`（FAIL）/ `2`（tokens.json 不在）の判定、JSON レポート（`.design/lint-report.json`）の読み取り。lint はファイルを読むだけで、ルール適用ロジックはすべてスクリプトが担う（エージェントは再現しない）
- **apply_patch** — lint 違反を修正する場合のみ（直書き値 → CSS 変数 `var(--*)` への置換など）。lint 自体は書き込みを行わない（下記「絶対的な制約」参照）ため、修正はユーザ依頼を受けてから別作業として行う

冒頭で `$SKILL_DIR`（この SKILL.md のある絶対ディレクトリ。例: `/abs/.../codex-skills/design-lint`）を確定させ、以降の `design_lint.py` 呼び出しで使う。

## 前提条件

1. `.design/tokens.json` が存在すること
   - なければ「tokens.json が見つかりません。`$design-scaffold` で生成してください」と表示して終了
2. `.design/lint-config.json` が存在すること（省略時はデフォルト設定を使用）

## Workflow

lint 本体は実行スクリプト `scripts/design_lint.py` に実装されている。エージェントは
スクリプトを実行して結果を解釈するだけで、ルール適用ロジックを自分で再現しない
（再現すると lint-contract とのドリフトが生じる）。

### Step 1: 前提確認

1. `.design/tokens.json` の存在を shell（`ls` / `cat`）で確認（なければ design-scaffold を案内して終了）
2. `.design/lint-config.json` は任意（なければスクリプトがデフォルト設定を使用）

### Step 2: スクリプト実行

shell でこのスキルの `scripts/design_lint.py` を実行する:

```bash
python3 "$SKILL_DIR/scripts/design_lint.py" \
  --root {project_root} \
  --output .design/lint-report.json --json
```

- `$SKILL_DIR` はこのスキルのベースディレクトリ（冒頭で確定させた絶対パス）
- 終了コード: `0` = PASS / `1` = FAIL（error あり）/ `2` = tokens.json 不在
- ルールの適用範囲はスクリプトが自動判定する:
  - DL001-006 は常時（tokens.json のみで有効）
  - DL101-103 は `.design/component-catalog.json` 存在時
  - DL201-203 は `.design/pages/` 存在時、DL204 は `.design/layout-rules.json` 存在時

### Step 3: 結果報告

JSON 出力の `summary` と `violations` を解釈して報告する。

**全 PASS の場合:**
```
✅ Design Lint: PASS
全ファイルがデザイントークンに準拠しています！
```

**FAIL の場合:**
```
❌ Design Lint: FAIL
{errors} 件のエラーが検出されました。

📄 詳細レポート: .design/lint-report.json

修正が必要な箇所:
{上位5件の違反を表示}

直書き値を CSS 変数 (var(--*)) に置き換えてください。
```

- violations が 20 件以下ならファイル名・行番号・値・修正提案まで表示する
- 20 件超ならルール別サマリーのみ表示し、`.design/lint-report.json` を案内する
- 違反ごとの `suggestion`（最も近いトークン: カラーは RGB 距離、spacing/radius は
  数値差で算出）があれば修正提案として提示する

### CI への組み込み

スクリプトは自己完結（標準ライブラリのみ・依存なし）なので、そのまま CI に載せられる:

```yaml
- name: Design lint
  run: python3 path/to/design_lint.py --root . && echo PASS
```

## 絶対的な制約

- lint はファイルを **読むだけ**。修正は行わない（スクリプトは書き込みを
  `--output` のレポート保存以外行わない）
- 検出は正規表現ベースで行い、AST パーサは使用しない（言語非依存性を確保）
- ルールの判定ロジックをエージェントが暗算で再現しない。必ずスクリプトを実行する
- コメント内の値は無視する（スクリプトが処理）
- `node_modules/` は常に除外
- `.design/` 自体は lint 対象外

## References

- **lint ルール仕様:** [references/lint-contract.md](references/lint-contract.md)
- **共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
