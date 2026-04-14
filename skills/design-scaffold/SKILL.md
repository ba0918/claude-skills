---
name: design-scaffold
description: DESIGN.md から machine-readable なデザインシステム（tokens.json + tokens.css + component-catalog + lint 設定）を scaffold 生成するスキル。design-guide で作った DESIGN.md を機械的検証可能な形に変換する。「デザインスキャフォールド」「scaffold」「トークン生成」で起動。
---

# Design Scaffold

DESIGN.md から machine-readable なデザインシステムファイル群を生成するスキル。
design-guide が生成した「人間可読な値の辞書」を、**機械的に検証可能な schema ベースのシステム** に変換する。

**共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md) を参照。

## 前提条件

1. プロジェクトルートに `DESIGN.md` が存在すること
   - なければ「DESIGN.md が見つかりません。`/claude-skills:design-guide` で作成してください」と表示して終了
2. DESIGN.md を Read で読み込み、全セクションの構造を把握

## Workflow

### Step 1: DESIGN.md パース

DESIGN.md を Read し、各セクションを内部データ構造にマッピングする。

**パースルール（テーブル → JSON マッピング）:**

| DESIGN.md セクション | テーブルカラム | tokens.json パス |
|---------------------|-------------|-----------------|
| Color Palette | Role, Value | `colors.{camelCase(role)}` |
| Dark Mode Overrides | Role, Value | `colorsDark.{camelCase(role)}` |
| Typography | Level, Font Family, Size, Weight, Line Height, Letter Spacing | `typography.scale.{camelCase(level)}` |
| Component Stylings > Buttons | Variant, Background, Text, Border, Border Radius, Padding | `components.buttons` |
| Component Stylings > Cards | (key-value pairs) | `components.cards` |
| Component Stylings > Inputs | (key-value pairs) | `components.inputs` |
| Component Stylings > Navigation | (key-value pairs) | `components.navigation` |
| Layout Principles | (key-value pairs) | `spacing.*` |
| Depth & Elevation | Level, Name, Usage, Shadow | `depth.{name}` |
| Responsive Behavior | Breakpoint, Name, Min Width, Behavior | `responsive.breakpoints.{breakpoint}` |

**テーブルパース手順:**
1. `|` で区切られた行を検出
2. ヘッダー行とセパレータ行 (`|---|`) を識別
3. データ行を各カラムに分割し、前後の空白をトリム
4. カラム名と値を対応づけ

**Font Family パース:**
- Typography テーブルの Font Family カラムからフォント名を抽出
- `- **Heading font:**` 等のプレーンテキスト行からもフォールバック込みのスタックを抽出
- 両方が存在する場合はプレーンテキスト行を優先（フォールバック情報が含まれるため）

### Step 2: tokens.json 生成

パースしたデータを [references/tokens-schema.json](references/tokens-schema.json) に準拠する JSON に変換。

1. `version` は `"1.0.0"` で初期化
2. 全カラー値を hex 6桁に正規化（`#FFF` → `#FFFFFF`）
3. Typography scale の各レベルに `fontKey` を設定（Heading フォント使用 → `"headingFont"`, Body → `"bodyFont"`, Code → `"codeFont"`）
4. spacing scale をソート済み配列として構築
5. `.design/` ディレクトリを作成（`mkdir -p .design`）
6. `.design/tokens.json` に Write

**生成後の自己検証:**
- 生成した tokens.json を Read し、schema の required フィールドが全て存在することを確認
- カラー値が全て `#[0-9a-fA-F]{6}` パターンに一致することを確認
- spacing.scale が昇順ソートされていることを確認

### Step 3: tokens.css 生成

tokens.json → CSS custom properties への変換。
design-system-contract の **CSS Custom Properties 命名規則** に厳密に従う。

**変換プロセス:**
1. tokens.json を Read
2. 全トークンを CSS custom properties に変換
3. セクションごとにコメントで区切り
4. `.design/tokens.css` に Write

**生成テンプレート:**

```css
/* =================================================================
 * Design Tokens — Auto-generated from tokens.json
 * DO NOT EDIT MANUALLY. Run design-scaffold to regenerate.
 * ================================================================= */

:root {
  /* ── Colors ── */
  --color-primary: {colors.primary};
  --color-primary-hover: {colors.primaryHover};
  --color-secondary: {colors.secondary};
  --color-accent: {colors.accent};
  --color-background: {colors.background};
  --color-surface: {colors.surface};
  --color-surface-alt: {colors.surfaceAlt};
  --color-error: {colors.error};
  --color-warning: {colors.warning};
  --color-success: {colors.success};
  --color-text-primary: {colors.textPrimary};
  --color-text-secondary: {colors.textSecondary};
  --color-text-disabled: {colors.textDisabled};
  --color-border: {colors.border};
  --color-focus-ring: {colors.focusRing};

  /* ── Typography ── */
  --font-heading: {typography.headingFont};
  --font-body: {typography.bodyFont};
  --font-code: {typography.codeFont};

  --font-size-display: {typography.scale.display.size}px;
  --font-weight-display: {typography.scale.display.weight};
  --line-height-display: {typography.scale.display.lineHeight};
  /* ... 全レベルについて size, weight, lineHeight, letterSpacing を出力 ... */

  /* ── Spacing ── */
  --spacing-base: {spacing.baseUnit}px;
  /* spacing.scale の各値を --spacing-0, --spacing-1, ... として出力 */

  /* ── Component Radii ── */
  --radius-button: {components.buttons.borderRadius}px;
  --radius-card: {components.cards.borderRadius}px;
  --radius-input: {components.inputs.borderRadius}px;

  /* ── Depth ── */
  --shadow-raised: {depth.raised.shadow};
  --shadow-overlay: {depth.overlay.shadow};
  --shadow-modal: {depth.modal.shadow};
  --shadow-toast: {depth.toast.shadow};
}
```

**ダークモード:**
`colorsDark` が存在する場合、`@media (prefers-color-scheme: dark)` ブロックも出力:
```css
@media (prefers-color-scheme: dark) {
  :root {
    --color-background: {colorsDark.background};
    --color-surface: {colorsDark.surface};
    /* ... */
  }
}
```

### Step 4: React/Preact Theme 生成（フレームワーク検出時）

プロジェクトが React/Preact を使用している場合（`package.json` に `react` or `preact` が存在）、TypeScript theme object を生成する。

1. `components/{framework}/` ディレクトリを作成
2. `components/{framework}/theme.ts` に Write

**生成テンプレート:**
```typescript
// Auto-generated from .design/tokens.json
// DO NOT EDIT MANUALLY. Run design-scaffold to regenerate.

export const theme = {
  colors: {
    primary: '{colors.primary}',
    primaryHover: '{colors.primaryHover}',
    // ... 全カラートークン
  },
  typography: {
    headingFont: "{typography.headingFont}",
    bodyFont: "{typography.bodyFont}",
    codeFont: "{typography.codeFont}",
    scale: {
      display: { size: {size}, weight: {weight}, lineHeight: {lh} },
      // ... 全レベル
    },
  },
  spacing: {
    base: {spacing.baseUnit},
    scale: [{spacing.scale join ', '}],
  },
  components: {
    buttons: { borderRadius: {r}, paddingY: {py}, paddingX: {px} },
    cards: { borderRadius: {r}, padding: {p} },
    inputs: { borderRadius: {r}, paddingY: {py}, paddingX: {px} },
  },
  depth: {
    flat: '{depth.flat.shadow}',
    raised: '{depth.raised.shadow}',
    overlay: '{depth.overlay.shadow}',
    modal: '{depth.modal.shadow}',
    toast: '{depth.toast.shadow}',
  },
} as const;

export type Theme = typeof theme;
```

### Step 5: lint-config.json 生成

デフォルトの lint 設定を `.design/lint-config.json` に生成。

**デフォルト値:**
```json
{
  "include": ["src/**/*.{tsx,jsx,ts,css}"],
  "exclude": ["node_modules/**", ".design/**", "**/*.test.*", "**/*.spec.*", "**/*.stories.*"],
  "rules": {
    "DL001": "error",
    "DL002": "error",
    "DL003": "warn",
    "DL004": "warn",
    "DL005": "warn",
    "DL006": "error"
  },
  "allowRawValues": {
    "colors": ["transparent", "inherit", "currentColor", "white", "black"],
    "spacing": [0, "auto"],
    "borderRadius": [0, "50%", "9999px"]
  }
}
```

**フレームワーク検出による調整:**
- React/Preact: `include` に `"**/*.tsx"`, `"**/*.jsx"` を追加
- Flutter: lint は非対応（将来の adapter で対応）→ `lint-config.json` は生成しない
- VanillaJS: `include` に `"**/*.js"`, `"**/*.css"` を設定

### Step 6: 完了レポート

```
✅ Design scaffold を生成しました！

📁 生成ファイル:
  .design/tokens.json      — デザイントークン定義
  .design/tokens.css       — CSS custom properties
  .design/lint-config.json — lint 設定
  components/react/theme.ts — React theme object (検出時のみ)

📊 トークン数:
  Colors: {n} tokens
  Typography: {n} levels
  Spacing: {n} scale values
  Components: {n} definitions
  Depth: {n} elevation levels
  Breakpoints: {n} defined

次のステップ:
  1. `/claude-skills:design-lint` でコードベースの準拠状況を確認
  2. Phase 2 で component-catalog を追加
```

## 既存 .design/ の上書き確認

`.design/tokens.json` が既に存在する場合:

1. 既存の `version` を読み取り
2. AskUserQuestion で確認:
   - "上書きする（version をインクリメント）"
   - "キャンセル"
3. 上書き時は `version` のパッチバージョンをインクリメント

## 絶対的な制約

- DESIGN.md に定義されていない値を tokens.json に **追加してはならない**
- tokens.json は schema に 100% 準拠すること（schema 違反は即修正）
- CSS custom property 名は design-system-contract の命名規則に **厳密に** 従うこと
- 生成ファイルの先頭に「Auto-generated, DO NOT EDIT MANUALLY」コメントを必ず含めること

## References

- **Token Schema:** [references/tokens-schema.json](references/tokens-schema.json)
- **共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
