---
name: design-scaffold
description: DESIGN.md から machine-readable なデザインシステム（tokens.json + tokens.css + component-catalog + lint 設定）を scaffold 生成するスキル。design-guide で作った DESIGN.md を機械的検証可能な形に変換する。「デザインスキャフォールド」「scaffold」「トークン生成」で起動。
---

# Design Scaffold (Codex Edition)

DESIGN.md から machine-readable なデザインシステムファイル群を生成するスキル。
design-guide が生成した「人間可読な値の辞書」を、**機械的に検証可能な schema ベースのシステム** に変換する。

**共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md) を参照。

## Codex CLI ツールの使い分け

- **apply_patch** — 生成ファイルの書き込み。tokens.json / tokens.css / lint-config.json / React・Preact theme / component-catalog.json / layout-rules.json / ページ定義 / コンポーネント実装（.tsx / .css / index.ts）の生成はすべて apply_patch で行う（shell リダイレクトでのファイル書き込みは禁止）
- **shell**（読み取り・検証用途） — DESIGN.md の読取（`cat`）、`package.json` 等のフレームワーク検出（`cat` / `rg`）、生成ファイルの自己検証（`cat` で読み戻して schema required フィールド・カラー値パターン・ソート順を確認）、ディレクトリ作成（`mkdir -p .design` / `mkdir -p components/{framework}`）
- **会話ターンでの確認** — 主要ページの選択・既存 `.design/` の上書き確認など、ユーザ確認を伴う分岐は会話ターンで平文の質問（選択肢は列挙して番号/短文で回答を促す）として尋ねる。**Codex の `request_user_input` は Plan mode 限定（default/exec 不可）のため使わない。** 確認が取れない headless 文脈では確認を求めず安全側に降格する（各 Step に降格ルールを明記）

## 前提条件

1. プロジェクトルートに `DESIGN.md` が存在すること
   - なければ「DESIGN.md が見つかりません。`$design-guide` で作成してください」と表示して終了
2. DESIGN.md を shell（`cat`）で読み込み、全セクションの構造を把握

## Workflow

### Step 1: DESIGN.md パース

DESIGN.md を shell（`cat`）で読み、各セクションを内部データ構造にマッピングする。

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
5. `.design/` ディレクトリを作成（shell で `mkdir -p .design`）
6. `.design/tokens.json` を apply_patch で書き込み

**生成後の自己検証:**
- 生成した tokens.json を shell（`cat`）で読み戻し、schema の required フィールドが全て存在することを確認
- カラー値が全て `#[0-9a-fA-F]{6}` パターンに一致することを確認
- spacing.scale が昇順ソートされていることを確認

### Step 3: tokens.css 生成

tokens.json → CSS custom properties への変換。
design-system-contract の **CSS Custom Properties 命名規則** に厳密に従う。

**変換プロセス:**
1. tokens.json を shell（`cat`）で読む
2. 全トークンを CSS custom properties に変換
3. セクションごとにコメントで区切り
4. `.design/tokens.css` を apply_patch で書き込み

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

プロジェクトが React/Preact を使用している場合（`package.json` に `react` or `preact` が存在。shell の `cat package.json` / `rg` で検出）、TypeScript theme object を生成する。

1. `components/{framework}/` ディレクトリを作成（shell で `mkdir -p`）
2. `components/{framework}/theme.ts` を apply_patch で書き込み

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

デフォルトの lint 設定を `.design/lint-config.json` に apply_patch で生成。

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
  1. `$design-lint` でコードベースの準拠状況を確認
```

### Step 7: Component Catalog 生成

DESIGN.md の Component Stylings セクションから、[references/catalog-schema.json](references/catalog-schema.json) に準拠する `component-catalog.json` を生成する。

#### 7-1. DESIGN.md からのコンポーネント抽出

Component Stylings セクションの各サブセクションをコンポーネント定義にマッピング:

| DESIGN.md サブセクション | コンポーネント名 | カテゴリ |
|------------------------|---------------|---------|
| Buttons | `Button` | `action` |
| Cards | `Card` | `container` |
| Inputs | `Input` | `input` |
| Navigation | `Nav` | `navigation` |

#### 7-2. Button コンポーネント生成例

DESIGN.md の Buttons テーブル:
```
| Variant | Background | Text | Border | Border Radius | Padding |
```

→ catalog.json:
```json
{
  "name": "Button",
  "category": "action",
  "description": "インタラクティブなアクションボタン",
  "variants": [
    {
      "name": "primary",
      "styles": {
        "background": "$tokens.colors.primary",
        "color": "$tokens.components.buttons.variants.primary.color",
        "border": "none",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    },
    {
      "name": "secondary",
      "styles": {
        "background": "transparent",
        "color": "$tokens.colors.primary",
        "border": "$tokens.components.buttons.variants.secondary.border",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    },
    {
      "name": "ghost",
      "styles": {
        "background": "transparent",
        "color": "$tokens.colors.textPrimary",
        "border": "none",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    },
    {
      "name": "destructive",
      "styles": {
        "background": "$tokens.colors.error",
        "color": "#FFFFFF",
        "border": "none",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    }
  ],
  "states": [
    {
      "name": "hover",
      "trigger": ":hover",
      "styles": { "background": "$tokens.colors.primaryHover" }
    },
    {
      "name": "focus",
      "trigger": ":focus-visible",
      "styles": { "shadow": "0 0 0 2px $tokens.colors.focusRing" }
    },
    {
      "name": "active",
      "trigger": ":active",
      "styles": { "opacity": 0.9 }
    },
    {
      "name": "disabled",
      "trigger": ":disabled",
      "styles": { "opacity": 0.5, "cursor": "not-allowed" }
    }
  ],
  "props": [
    { "name": "variant", "type": "\"primary\" | \"secondary\" | \"ghost\" | \"destructive\"", "required": false, "default": "primary" },
    { "name": "size", "type": "\"sm\" | \"md\" | \"lg\"", "required": false, "default": "md" },
    { "name": "disabled", "type": "boolean", "required": false, "default": false },
    { "name": "onClick", "type": "() => void", "required": false },
    { "name": "children", "type": "ReactNode", "required": true }
  ],
  "tokens": [
    "$tokens.colors.primary",
    "$tokens.colors.primaryHover",
    "$tokens.colors.error",
    "$tokens.colors.textPrimary",
    "$tokens.colors.focusRing",
    "$tokens.components.buttons.borderRadius",
    "$tokens.components.buttons.paddingY",
    "$tokens.components.buttons.paddingX"
  ],
  "a11y": {
    "role": "button",
    "ariaAttributes": [
      { "name": "aria-disabled", "boundToProp": "disabled" }
    ],
    "keyboardNav": [
      { "key": "Enter", "action": "activate" },
      { "key": "Space", "action": "activate" }
    ],
    "minContrastRatio": 4.5
  }
}
```

#### 7-3. 同様に Card, Input, Nav も生成

各コンポーネントの DESIGN.md 定義から同じ手順で catalog エントリを生成。
全スタイル値は `$tokens.*` 参照で表現し、直書き値は CSS キーワード（`none`, `transparent`, `inherit`）のみ許可。

#### 7-4. catalog.json の自己検証

生成後:
1. 全 `$tokens.*` 参照が tokens.json に存在することを確認
2. 各コンポーネントの variants が DESIGN.md の定義と 1:1 対応することを確認
3. props の型が TypeScript として妥当であることを確認

#### 7-5. `.design/component-catalog.json` を apply_patch で書き込み

### Step 8: React/Preact コンポーネント生成

フレームワークが React/Preact の場合、catalog.json からコンポーネント実装を自動生成する。

#### 生成ルール

1. **CSS は tokens.css の custom properties 経由でのみスタイリング**
   - `$tokens.colors.primary` → `var(--color-primary)`
   - `$tokens.components.buttons.borderRadius` → `var(--radius-button)`
2. **Props は catalog.json の props 定義に完全準拠**
   - TypeScript 型を自動生成
   - default 値を設定
3. **Variants は catalog.json の variants のみ**
   - variant prop で切り替え、CSS クラスで実装
4. **States は catalog.json の states のみ**
   - CSS pseudo-class + JS event handler
5. **a11y 要件を HTML 属性として自動付与**
   - role, aria-*, keyboard navigation

#### 生成テンプレート（Button の例）

```typescript
// components/react/Button.tsx — Auto-generated from .design/component-catalog.json
// DO NOT EDIT MANUALLY. Run design-scaffold to regenerate.

import React from 'react';
import './Button.css';

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  disabled = false,
  onClick,
  children,
}) => {
  return (
    <button
      className={`btn btn--${variant} btn--${size}`}
      disabled={disabled}
      onClick={onClick}
      aria-disabled={disabled}
    >
      {children}
    </button>
  );
};
```

```css
/* components/react/Button.css — Auto-generated from .design/component-catalog.json */

.btn {
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: var(--font-body);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
  border-radius: var(--radius-button);
}

.btn--primary {
  background: var(--color-primary);
  color: /* tokens.components.buttons.variants.primary.color */;
  padding: var(--spacing-/* paddingY */) var(--spacing-/* paddingX */);
}

/* ... 各 variant, state, size のスタイル ... */

.btn:hover:not(:disabled) { /* hover styles */ }
.btn:focus-visible { box-shadow: 0 0 0 2px var(--color-focus-ring); outline: none; }
.btn:active:not(:disabled) { opacity: 0.9; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
```

#### index.ts 生成

```typescript
// components/react/index.ts — Auto-generated
export { Button } from './Button';
export type { ButtonProps } from './Button';
export { Card } from './Card';
export type { CardProps } from './Card';
export { Input } from './Input';
export type { InputProps } from './Input';
export { Nav } from './Nav';
export type { NavProps } from './Nav';
```

### Step 9: 完了レポート（拡張）

Step 6 の完了レポートに catalog 情報を追加:

```
📊 コンポーネント:
  Components: {n} defined (Button, Card, Input, Nav)
  Variants: {n} total
  Props: {n} total
  Framework: {framework}

📁 追加生成ファイル:
  .design/component-catalog.json — コンポーネント仕様定義
  components/{framework}/Button.tsx + Button.css
  components/{framework}/Card.tsx + Card.css
  components/{framework}/Input.tsx + Input.css
  components/{framework}/Nav.tsx + Nav.css
  components/{framework}/index.ts
```

### Step 10: Layout Rules 生成

DESIGN.md の Layout Principles + Do's/Don'ts セクションから、[references/layout-schema.json](references/layout-schema.json) に準拠する `layout-rules.json` を生成する。

#### 10-1. Layout Principles → grid / spacing

| DESIGN.md フィールド | layout-rules.json パス |
|---------------------|----------------------|
| Grid: {columns} columns, {gap}px gap | `grid.columns`, `grid.gap` |
| Max content width: {width}px | `grid.maxWidth` |
| Base unit: {unit}px | (spacing.baseUnit は tokens.json 側) |
| Section spacing: {spacing}px | `spacing.sectionGap` |
| White space philosophy: {description} | constraints に変換 |

#### 10-2. Do's/Don'ts → constraints 変換

DESIGN.md の Do / Don't リストを [references/layout-schema.json](references/layout-schema.json) の `constraintDef` 形式に変換する。

**変換ルール:**
1. 各 Do / Don't を読み取り
2. 機械検証可能な条件に翻訳（自然言語 → 正規表現 or 数値範囲）
3. enforcement を判定:
   - CSS プロパティの値に関するルール → `lint`
   - 視覚的な配置・バランスに関するルール → `visual`
   - 全体的な印象・統一感に関するルール → `rubric`
4. ID を `LC001` から連番で付与

#### 10-3. `.design/layout-rules.json` を apply_patch で書き込み

### Step 11: ページ定義のテンプレート生成

会話ターンでプロジェクトの主要ページを平文で質問する（選択肢を列挙し、番号または短文で回答を促す。複数選択可）:

```
主要ページ: このプロジェクトの主要なページは何ですか？（複数選択可）
  1. ランディングページ
  2. ダッシュボード
  3. 一覧ページ
  4. フォームページ
```

**headless 降格**: 確認が取れない headless 文脈（`$design-guide` からの連鎖・自動化パイプライン等）では質問せず、ページ定義テンプレートの生成をスキップする（推測でページ定義を量産せず、安全側に倒す）。スキップした旨を完了レポートに明記する。

選択されたページに対して:
1. layout-rules.json の `patterns` から推奨レイアウトパターンを取得
2. catalog.json のコンポーネントから各セクションの推奨配置を構築
3. [references/page-schema.json](references/page-schema.json) に準拠するページ定義を生成
4. `.design/pages/{page-name}.json` を apply_patch で書き込み

### Step 12: 最終完了レポート

```
📊 レイアウト:
  Layout Rules: {n} constraints defined
  Page Definitions: {n} pages

📁 追加生成ファイル:
  .design/layout-rules.json — レイアウト制約
  .design/pages/{page-name}.json × {n}

次のステップ:
  1. `$design-generate` でページを生成
  2. Base Design の承認フローへ進む
```

## 既存 .design/ の上書き確認

`.design/tokens.json` が既に存在する場合:

1. 既存の `version` を読み取り
2. 会話ターンで平文確認する（選択肢を列挙し番号/短文で回答を促す）:
   - 1. 上書きする（version をインクリメント）
   - 2. キャンセル
3. 上書き時は `version` のパッチバージョンをインクリメント

**headless 降格**: 確認が取れない headless 文脈では上書きせずキャンセルする（既存の `.design/` を安全側で保護する）。キャンセルした旨を報告する。

## 絶対的な制約

- DESIGN.md に定義されていない値を tokens.json に **追加してはならない**
- tokens.json は schema に 100% 準拠すること（schema 違反は即修正）
- CSS custom property 名は design-system-contract の命名規則に **厳密に** 従うこと
- 生成ファイルの先頭に「Auto-generated, DO NOT EDIT MANUALLY」コメントを必ず含めること

## References

- **Token Schema:** [references/tokens-schema.json](references/tokens-schema.json)
- **Catalog Schema:** [references/catalog-schema.json](references/catalog-schema.json)
- **Page Schema:** [references/page-schema.json](references/page-schema.json)
- **Layout Schema:** [references/layout-schema.json](references/layout-schema.json)
- **Rubric Schema:** [references/rubric-schema.json](references/rubric-schema.json)
- **共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
