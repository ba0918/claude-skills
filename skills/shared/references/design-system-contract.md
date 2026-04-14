# Design System Contract

複数のデザインシステムスキル（design-scaffold, design-generate, design-validate, design-lint）が共有する契約。

## 核心原則: Human-in-the-Loop Once

人間の主観判断は **base design の1回承認** に集約する。承認後は全て機械的検証で品質を保証する。

## ファイル構造契約

デザインシステムスキルが操作するターゲットプロジェクトのファイル構造:

```
target-project/
├── DESIGN.md                          # 人間可読なデザインシステム定義
├── .design/                           # machine-readable デザインシステム
│   ├── tokens.json                    # デザイントークン（色・フォント・spacing）
│   ├── tokens.css                     # CSS custom properties（tokens.json から生成）
│   ├── component-catalog.json         # コンポーネント仕様定義
│   ├── layout-rules.json              # レイアウト制約
│   ├── pages/                         # ページ構成定義
│   │   └── {page-name}.json
│   ├── rubric.json                    # 評価基準
│   ├── lint-config.json               # lint 設定
│   └── baseline/                      # 承認済み baseline
│       ├── approval.json              # 承認メタデータ
│       └── screenshots/              # 承認時スクリーンショット
├── components/{framework}/            # 生成済みコンポーネント
└── mockups/base/                      # 承認用 base mockup
```

## Token 参照契約

### tokens.json 内の参照

コンポーネントや layout-rules で tokens の値を参照する場合、`$tokens.{path}` 形式を使用する:

```
$tokens.colors.primary      → tokens.json の colors.primary の値
$tokens.depth.raised         → tokens.json の depth.raised の値
$tokens.spacing.scale[2]     → tokens.json の spacing.scale[2] の値
```

### CSS Custom Properties 命名規則

tokens.json のキーパスを CSS custom property 名に変換する規則:

| tokens.json パス | CSS custom property |
|-----------------|---------------------|
| `colors.primary` | `--color-primary` |
| `colors.primaryHover` | `--color-primary-hover` |
| `colors.textPrimary` | `--color-text-primary` |
| `typography.headingFont` | `--font-heading` |
| `typography.bodyFont` | `--font-body` |
| `typography.scale.h1.size` | `--font-size-h1` |
| `typography.scale.h1.weight` | `--font-weight-h1` |
| `typography.scale.h1.lineHeight` | `--line-height-h1` |
| `spacing.baseUnit` | `--spacing-base` |
| `spacing.scale[N]` | `--spacing-{N}` (0-indexed) |
| `components.buttons.borderRadius` | `--radius-button` |
| `components.cards.borderRadius` | `--radius-card` |
| `components.inputs.borderRadius` | `--radius-input` |
| `depth.raised.shadow` | `--shadow-raised` |
| `depth.overlay.shadow` | `--shadow-overlay` |
| `depth.modal.shadow` | `--shadow-modal` |
| `depth.toast.shadow` | `--shadow-toast` |

**camelCase → kebab-case 変換規則:** 大文字の前にハイフンを挿入し小文字化。
例: `primaryHover` → `primary-hover`, `textPrimary` → `text-primary`

## 検証階層契約

検証は以下の順序で実行する。上位で失敗した場合、下位は実行しない:

```
Level 1: Static Lint (AST 解析)
  ├── DL001-006: Token 直書き検出
  ├── DL101-103: コンポーネント違反検出
  └── DL201-204: ページ構成違反検出

Level 2: Schema Validation
  └── tokens.json / catalog.json / pages/*.json が各 schema に準拠

Level 3: Visual Regression Test
  └── 承認済み baseline スクリーンショットとの差分比較

Level 4: Rubric Judge (LLM)
  └── 機械検証不能な「統一感」「体験の自然さ」の評価
```

**Weight 配分:** mechanical (60%) > visual (22%) > llm-judge (18%)

## Lint ルール ID 体系

| 範囲 | カテゴリ | 説明 |
|------|---------|------|
| DL001-099 | Token Compliance | トークン直書き検出 |
| DL100-199 | Component Compliance | コンポーネント違反検出 |
| DL200-299 | Page/Layout Compliance | ページ構成違反検出 |
| DL300-399 | (将来拡張) | |

## Baseline 再承認トリガー

以下の条件で baseline の再承認が必要:

1. `tokens.json` のハッシュが `approval.json` の `tokensHash` と不一致
2. `component-catalog.json` のハッシュが `approval.json` の `catalogHash` と不一致
3. `approval.json` が存在しない

再承認なしでの baseline 更新は **禁止**。

## フレームワーク Adapter 契約

各フレームワーク adapter は以下を提供する:

| 成果物 | React/Preact | Flutter | VanillaJS | PostCSS |
|--------|-------------|---------|-----------|---------|
| Theme object | `theme.ts` | `theme.dart` | — | — |
| CSS variables | `tokens.css` | — | `tokens.css` | `tokens.css` |
| Components | `{Name}.tsx` | `{name}.dart` | `{name}.js` | — |
| Storybook | `.stories.tsx` | — | `.stories.js` | — |

**共通:** tokens.css（CSS custom properties）は全 Web フレームワークで共有。
