---
name: design-lint
description: プロジェクトのコードベースを .design/tokens.json に基づいて lint し、デザイントークン違反（直書きカラー・フォント・spacing等）を機械的に検出するスキル。CI にも組み込み可能。「デザインリント」「design lint」「トークン検証」で起動。
---

# Design Lint

プロジェクトのコードベースを `.design/tokens.json` に基づいて lint し、デザイントークン違反を機械的に検出する。

**共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md) を参照。
**lint ルール仕様:** [references/lint-contract.md](references/lint-contract.md) を参照。

## 前提条件

1. `.design/tokens.json` が存在すること
   - なければ「tokens.json が見つかりません。`/claude-skills:design-scaffold` で生成してください」と表示して終了
2. `.design/lint-config.json` が存在すること（省略時はデフォルト設定を使用）

## Workflow

### Step 1: 設定読み込み

1. `.design/tokens.json` を Read → 許可値リストを構築
2. `.design/lint-config.json` を Read（なければデフォルト値を使用）
3. ルール別の severity を確認（`error` / `warn` / `off`）

### Step 2: 許可値リストの構築

tokens.json から以下の許可値リストを構築:

#### カラー許可リスト (DL001)
```
tokens.colors の全値 + colorsDark の全値 + allowRawValues.colors
→ ["#2563EB", "#1D4ED8", ..., "transparent", "inherit", "currentColor", "white", "black"]
```

#### フォント許可リスト (DL002)
```
tokens.typography の headingFont, bodyFont, codeFont からフォント名を抽出
+ system fonts: ["-apple-system", "BlinkMacSystemFont", "system-ui", "Segoe UI"]
+ generic: ["sans-serif", "serif", "monospace", "cursive", "fantasy"]
```

#### spacing 許可リスト (DL003)
```
tokens.spacing.scale の全値 + allowRawValues.spacing
→ [0, 4, 8, 12, 16, 24, 32, 48, "auto"]
```

#### border-radius 許可リスト (DL004)
```
tokens.components の全 borderRadius 値 + allowRawValues.borderRadius
→ [0, 8, 12, 16, "50%", "9999px"]
```

#### shadow 許可リスト (DL005)
```
tokens.depth の全 shadow 値 + ["none"]
```

#### CSS 変数マッピング (DL006)
```
tokens の全値 → 対応する CSS custom property 名
design-system-contract の命名規則に従い構築
```

### Step 3: ファイルスキャン

1. Glob で `include` パターンに一致するファイル一覧を取得
2. `exclude` パターンに一致するファイルを除外
3. 各ファイルを Read

### Step 4: ルール適用

各ファイルの内容に対して、有効な全ルールを順番に適用。

#### DL001: 直書きカラーコード

**検出パターン（正規表現）:**
```
CSS/JSX 内:
  /#[0-9a-fA-F]{3,8}\b/
  /rgba?\(\s*\d+/
  /hsla?\(\s*\d+/

除外:
  コメント行（// or /* */ 内）
  var(--color-*) 経由の使用
  文字列リテラル内の URL（url(#...)）
```

**判定:** 抽出した値がカラー許可リストにない → 違反

#### DL002: 直書きフォント

**検出パターン:**
```
/font-family\s*:\s*([^;]+)/
/fontFamily\s*:\s*['"]([^'"]+)['"]/  (CSS-in-JS)
/fontFamily\s*:\s*`([^`]+)`/         (template literal)
```

**判定:** フォント名がフォント許可リストにない → 違反

#### DL003: 直書き spacing

**検出パターン:**
```
/(padding|margin|gap|top|right|bottom|left)\s*:\s*(\d+)px/
ショートハンド: /(padding|margin)\s*:\s*([\d]+px[\s\d+px]*)/
```

**判定:** 各 px 値が spacing 許可リストにない → 違反

#### DL004: 直書き border-radius

**検出パターン:**
```
/border-radius\s*:\s*(\d+)px/
/borderRadius\s*:\s*(\d+)/  (CSS-in-JS)
```

**判定:** 値が border-radius 許可リストにない → 違反

#### DL005: 直書き shadow

**検出パターン:**
```
/box-shadow\s*:\s*([^;]+)/
/boxShadow\s*:\s*['"]([^'"]+)['"]/
```

**判定:** 値が shadow 許可リストにない → 違反

#### DL006: CSS 変数未使用

**検出方法:**
1. ファイル内で tokens の値と一致する直書き値を検出
2. その値が `var(--*)` 経由ではなく使用されている → 違反
3. DL001-005 で既に検出された違反には追加しない（重複回避）

### Step 5: レポート生成

全ファイルのスキャン完了後、結果を集約してレポート出力。

**サマリー表示:**
```
🔍 Design Lint Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files scanned: {total_files}
Violations: {total} ({errors} errors, {warnings} warnings)

{ルール別の違反数を表示}

Result: {PASS / PASS (with warnings) / FAIL}
```

**詳細表示（violations が 20 件以下の場合）:**
各違反のファイル名、行番号、ルール、値、メッセージ、修正提案を表示。

**詳細表示（violations が 20 件超の場合）:**
ルール別のサマリーのみ表示し、「詳細は .design/lint-report.json を確認してください」と案内。

### Step 6: レポート保存

違反が 1 件以上ある場合、`.design/lint-report.json` に JSON 形式で保存:

```json
{
  "timestamp": "2026-04-14T19:00:00Z",
  "filesScanned": 24,
  "totalViolations": 7,
  "errors": 5,
  "warnings": 2,
  "result": "FAIL",
  "violations": [
    {
      "rule": "DL001",
      "severity": "error",
      "file": "src/components/Header.tsx",
      "line": 42,
      "column": 15,
      "value": "#FF6B6B",
      "message": "直書きカラーコード '#FF6B6B' を検出。var(--color-*) を使用してください。",
      "suggestion": "最も近いトークン: --color-error (#DC2626)"
    }
  ]
}
```

### Step 7: 完了メッセージ

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

## 最も近いトークンの提案

違反検出時、tokens.json の許可値から「最も近い値」を提案する:

- **カラー:** RGB 色空間でのユークリッド距離が最小のトークン
- **spacing:** 数値差が最小のスケール値
- **border-radius:** 数値差が最小の値

## 絶対的な制約

- lint はファイルを **読むだけ**。修正は行わない（Read + Grep + Glob のみ使用）
- 検出は正規表現ベースで行い、AST パーサは使用しない（言語非依存性を確保）
- コメント内の値は無視する
- `node_modules/` は常に除外
- `.design/` 自体は lint 対象外

## References

- **lint ルール仕様:** [references/lint-contract.md](references/lint-contract.md)
- **共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
