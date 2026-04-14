# design-guide v2: 機械的検証可能なデザインシステム基盤

**Cycle ID:** `20260414184459`
**Started:** 2026-04-14 18:44:59
**Status:** 🟡 Planning

---

## 📝 What & Why

現在の design-guide は DESIGN.md（値の辞書）を生成するだけで、LLM がUI実装するたびに毎回0からページを組み立てるため、再現性がなく品質が安定しない。人間の主観でしか品質判断ができず、ルール違反を機械的に検出する手段がない。

人間の主観判断を **「base design の1回承認」に集約** し、それ以降は全てを機械的に検証可能にするUIデザインシステム基盤を構築する。

## 🎯 Goals

- **Human-in-the-Loop Once**: 人間の主観判断を「base design の1回承認」に集約し、以降は全て機械的検証で品質を保証する
- DESIGN.md から **machine-readable な schema** を生成し、全デザイントークンを機械的に参照・検証可能にする
- **コンポーネントカタログ** を定義し、承認済みコンポーネントだけでページを構成する仕組みを確立する
- **ページ定義 + レイアウトルール** で「何をどこに配置するか」までを schema で制約する
- **Base Design Approval** で人間の承認を得た mockup のスクリーンショットを visual regression の baseline にする
- **Storybook + Playwright** で承認済み baseline に対する visual regression test を自動化する
- **Rubric Judge** で機械検証不能な残りを構造化評価する
- 全ゲート合格 → コード反映。反映後も **lint で継続検証**
- **フレームワーク非依存の Schema Layer** と **フレームワーク依存の Adapter Layer** を分離（初期ターゲット: React/Preact）

## 🏗️ Architecture

### 核心原則: Human-in-the-Loop Once

100% 主観を排除するのは不可能。「何が正しいデザインか」を最終判断できるのは人間だけ。
しかし、その判断を **毎回** 要求するのは仕組みの失敗。

解決策: **人間の主観判断を「base design の1回承認」に集約する**。

```
DESIGN.md → scaffold → base mockup 生成
                              ↓
                   ★ 人間の承認（唯一の主観判断ポイント）
                              ↓ OK
                       baseline 確定
          ┌───────────────────┴───────────────────┐
          │ 以降は全て機械的                        │
          │  新ページ → lint + visual diff          │
          │  コード変更 → lint                      │
          │  全て「承認済み baseline との差分」で判定  │
          └───────────────────────────────────────┘
```

承認された mockup のスクリーンショットが Visual Regression Test の **baseline そのもの** になる。
人間の承認と機械的検証が構造的に接続される。

### 設計原則: 4層分離

```
┌─────────────────────────────────────────────────┐
│  Schema Layer（フレームワーク非依存）              │
│  tokens.json / catalog.json / pages/*.json       │
│  layout-rules.json / rubric.json                 │
├─────────────────────────────────────────────────┤
│  Adapter Layer（フレームワーク依存）               │
│  react/ preact/ flutter/ vanilla/ postcss/       │
│  tokens → CSS vars / theme objects               │
│  catalog → Component implementations             │
├─────────────────────────────────────────────────┤
│  Approval Layer（人間の判断 — 1回のみ）           │
│  base mockup 生成 → 人間が承認 → baseline 確定    │
│  承認済みスクリーンショット = visual baseline      │
├─────────────────────────────────────────────────┤
│  Validation Layer（以降全て機械的）               │
│  L1: Static Lint (AST) → L2: Schema Validation   │
│  → L3: Visual Regression → L4: Rubric Judge      │
└─────────────────────────────────────────────────┘
```

### ターゲットプロジェクトに生成されるファイル構造

```
target-project/
├── DESIGN.md                          # 既存（design-guide が生成）
├── .design/                           # NEW: machine-readable design system
│   ├── tokens.json                    # デザイントークン（色・フォント・spacing...）
│   ├── tokens.css                     # CSS custom properties（tokens.json から生成）
│   ├── component-catalog.json         # コンポーネント定義
│   ├── layout-rules.json              # レイアウト制約
│   ├── pages/                         # ページ定義
│   │   ├── landing.json
│   │   └── dashboard.json
│   ├── rubric.json                    # 評価基準
│   ├── lint-config.json               # lint 設定
│   └── baseline/                      # 承認済み baseline（人間が OK した状態）
│       ├── approval.json              # 承認メタデータ（日時・承認者・バージョン）
│       └── screenshots/              # 承認時のスクリーンショット = visual test baseline
│           ├── button-primary.png
│           ├── card-default.png
│           └── landing-desktop.png
├── components/                        # 生成されたコンポーネント実装
│   └── {framework}/                   # react/ preact/ flutter/ etc.
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Input.tsx
│       └── index.ts
├── stories/                           # Storybook stories（Phase 4）
│   ├── Button.stories.tsx
│   └── Card.stories.tsx
└── tests/
    └── visual/
        └── __screenshots__/           # baseline スクリーンショット
```

### claude-skills リポジトリの変更

```
skills/
├── design-guide/                      # 既存 — 改修
│   ├── SKILL.md                       # Phase 6 で .design/ 生成を追加
│   └── references/
│       └── design-md-template.md      # tokens.json との対応マッピング追加
├── design-scaffold/                   # NEW — Phase 1-3
│   ├── SKILL.md                       # DESIGN.md → .design/ scaffold 生成
│   └── references/
│       ├── tokens-schema.json         # JSON Schema: tokens.json の検証用
│       ├── catalog-schema.json        # JSON Schema: component-catalog.json
│       ├── layout-schema.json         # JSON Schema: layout-rules.json
│       ├── page-schema.json           # JSON Schema: pages/*.json
│       ├── rubric-schema.json         # JSON Schema: rubric.json
│       └── adapter-contract.md        # フレームワーク adapter の仕様
├── design-generate/                   # NEW — Phase 3
│   ├── SKILL.md                       # page-def + catalog → 制約付きページ生成
│   └── references/
│       └── generation-constraints.md  # 生成時の制約ルール
├── design-validate/                   # NEW — Phase 4-5
│   ├── SKILL.md                       # lint + visual test + rubric の統合ゲート
│   └── references/
│       ├── validation-pipeline.md     # 検証パイプライン定義
│       └── lint-rules.md             # lint ルール仕様
├── design-lint/                       # NEW — Phase 1
│   ├── SKILL.md                       # CI 用 lint（単体実行可能）
│   └── references/
│       └── lint-contract.md           # lint 契約
└── shared/references/
    └── design-system-contract.md      # NEW: デザインシステム検証の共有契約

commands/
├── design-scaffold.md                 # NEW → skills/design-scaffold/
├── design-generate.md                 # NEW → skills/design-generate/
├── design-validate.md                 # NEW → skills/design-validate/
├── design-lint.md                     # NEW → skills/design-lint/
└── design-guide.md                    # 既存 — scaffold への導線追加
```

---

## 📐 Design

### Phase 1: Design Tokens Schema + Lint

**目的:** DESIGN.md の全値を machine-readable な JSON に変換し、直書き値の使用を AST レベルで検出する

#### 1-1. tokens-schema.json の設計

DESIGN.md の全セクションを JSON Schema で定義。DESIGN.md テンプレートの各フィールドと 1:1 対応。

```jsonc
// tokens-schema.json（概要）
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["colors", "typography", "spacing", "components", "depth", "responsive"],
  "properties": {
    "colors": {
      "type": "object",
      "required": ["primary", "secondary", "accent", "background", "surface", "error", "text"],
      "properties": {
        "primary":       { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "primaryHover":  { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "secondary":     { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "accent":        { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "background":    { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "surface":       { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "surfaceAlt":    { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "error":         { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "warning":       { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "success":       { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "textPrimary":   { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "textSecondary": { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "textDisabled":  { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "border":        { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "focusRing":     { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" }
      }
    },
    "colorsDark": { "type": "object", "description": "Dark mode overrides (optional)" },
    "typography": {
      "type": "object",
      "properties": {
        "headingFont": { "type": "string" },
        "bodyFont":    { "type": "string" },
        "codeFont":    { "type": "string" },
        "scale": {
          "type": "object",
          "description": "各レベル (display, h1, h2, h3, h4, body, bodySmall, caption, code) の size/weight/lineHeight/letterSpacing"
        }
      }
    },
    "spacing": {
      "type": "object",
      "properties": {
        "baseUnit":       { "type": "number" },
        "scale":          { "type": "array", "items": { "type": "number" } },
        "maxContentWidth": { "type": "number" },
        "gridColumns":    { "type": "number" },
        "gridGap":        { "type": "number" },
        "sectionSpacing": { "type": "number" }
      }
    },
    "components": {
      "type": "object",
      "description": "buttons, cards, inputs, navigation の border-radius, padding 等"
    },
    "depth": {
      "type": "object",
      "description": "elevation levels: flat, raised, overlay, modal, toast の shadow 定義"
    },
    "responsive": {
      "type": "object",
      "description": "breakpoints (sm, md, lg, xl), touch target size, approach"
    }
  }
}
```

#### 1-2. design-scaffold スキル: tokens.json 生成

DESIGN.md をパースし、tokens-schema.json に準拠する tokens.json を生成する。

**パース戦略:**
- DESIGN.md はマークダウンテーブルで構造化されている → テーブル行をパースして key-value マッピング
- Color Palette テーブル → `colors.*`
- Typography テーブル → `typography.scale.*`
- Component Stylings → `components.*`
- Layout Principles → `spacing.*`
- Depth & Elevation テーブル → `depth.*`
- Responsive Behavior テーブル → `responsive.*`

**生成後の検証:** 生成した tokens.json を tokens-schema.json で JSON Schema validation する（Bash で `ajv validate` または `npx ajv-cli validate`）

#### 1-3. tokens.css 生成（CSS custom properties adapter）

tokens.json → CSS custom properties への変換。全フレームワーク共通の基盤。

```css
/* .design/tokens.css — auto-generated from tokens.json */
:root {
  /* Colors */
  --color-primary: #2563EB;
  --color-primary-hover: #1D4ED8;
  --color-secondary: #64748B;
  /* ... all color tokens ... */

  /* Typography */
  --font-heading: 'Outfit', sans-serif;
  --font-body: 'Plus Jakarta Sans', sans-serif;
  --font-code: 'JetBrains Mono', monospace;
  --font-size-display: 48px;
  --font-size-h1: 36px;
  /* ... all typography tokens ... */

  /* Spacing */
  --spacing-base: 8px;
  --spacing-1: 4px;
  --spacing-2: 8px;
  --spacing-3: 12px;
  /* ... all spacing scale ... */

  /* Components */
  --radius-button: 12px;
  --radius-card: 16px;
  --radius-input: 8px;
  /* ... */

  /* Depth */
  --shadow-raised: 0 1px 3px rgba(0,0,0,0.12);
  --shadow-overlay: 0 4px 6px rgba(0,0,0,0.1);
  /* ... */
}
```

#### 1-4. React/Preact theme adapter

tokens.json → TypeScript theme object への変換。

```typescript
// components/react/theme.ts — auto-generated from tokens.json
export const theme = {
  colors: {
    primary: '#2563EB',
    primaryHover: '#1D4ED8',
    // ...
  },
  typography: {
    headingFont: "'Outfit', sans-serif",
    bodyFont: "'Plus Jakarta Sans', sans-serif",
    // ...
  },
  spacing: {
    base: 8,
    scale: [4, 8, 12, 16, 24, 32, 48],
    // ...
  },
} as const;

export type Theme = typeof theme;
```

#### 1-5. design-lint スキル: AST ベース lint

**検出ルール:**

| ルール ID | 検出対象 | 説明 |
|-----------|---------|------|
| `DL001` | 直書きカラーコード | CSS/JSX で `#XXXXXX` や `rgb()` が tokens にないカラーを使用 |
| `DL002` | 直書きフォント | `font-family` に tokens にないフォントを使用 |
| `DL003` | 直書き spacing | `padding`, `margin`, `gap` に tokens scale にない値を使用 |
| `DL004` | 直書き border-radius | `border-radius` に tokens にない値を使用 |
| `DL005` | 直書き shadow | `box-shadow` に tokens にない shadow を使用 |
| `DL006` | CSS 変数未使用 | `var(--color-*)` ではなく直書き値を使用 |

**lint 実行方式:**
- Bash で `grep -rn` ベースの簡易チェック（LLM スキル内で完結）
- 正規表現パターンマッチでカラーコード・px 値等を抽出
- tokens.json の許可値リストと照合
- 違反を `{ file, line, rule, value, expected }` 形式でレポート

**CI 対応:** design-lint スキルは単体実行可能。プロジェクト側で `npx claude --skill design-lint` 的に実行できる設計。

#### 1-6. Files to Create/Modify

```
NEW:
  skills/design-scaffold/SKILL.md
  skills/design-scaffold/references/tokens-schema.json
  skills/design-lint/SKILL.md
  skills/design-lint/references/lint-contract.md
  skills/shared/references/design-system-contract.md
  commands/design-scaffold.md
  commands/design-lint.md

MODIFY:
  skills/design-guide/SKILL.md          # Phase 6 で scaffold への導線追加
  skills/design-guide/references/design-md-template.md  # tokens.json 対応マッピングコメント追加
  CLAUDE.md                             # 新スキル情報追加
  plugin.json                           # バージョンバンプ + 新コマンド登録
```

---

### Phase 2: Component Catalog Schema + 生成

**目的:** 承認済みコンポーネントの仕様を schema で定義し、フレームワーク別の実装を自動生成する

#### 2-1. catalog-schema.json の設計

```jsonc
// catalog-schema.json（概要）
{
  "type": "object",
  "required": ["version", "framework", "components"],
  "properties": {
    "version":   { "type": "string" },
    "framework": { "enum": ["react", "preact", "flutter", "vanilla", "postcss"] },
    "components": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "variants", "props", "tokens"],
        "properties": {
          "name":     { "type": "string", "description": "コンポーネント名 (PascalCase)" },
          "category": { "enum": ["action", "container", "input", "navigation", "feedback", "layout"] },
          "variants": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["name", "styles"],
              "properties": {
                "name":   { "type": "string" },
                "styles": {
                  "type": "object",
                  "description": "各 CSS プロパティと使用する token への参照",
                  "properties": {
                    "background":   { "$ref": "#/$defs/tokenRef" },
                    "color":        { "$ref": "#/$defs/tokenRef" },
                    "borderRadius": { "$ref": "#/$defs/tokenRef" },
                    "padding":      { "$ref": "#/$defs/tokenRef" },
                    "shadow":       { "$ref": "#/$defs/tokenRef" }
                  }
                }
              }
            }
          },
          "states": {
            "type": "object",
            "description": "hover, focus, active, disabled の各状態定義"
          },
          "props": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name":     { "type": "string" },
                "type":     { "type": "string" },
                "required": { "type": "boolean" },
                "default":  {}
              }
            }
          },
          "tokens": {
            "type": "array",
            "items": { "type": "string" },
            "description": "このコンポーネントが参照する token パス一覧"
          },
          "a11y": {
            "type": "object",
            "description": "アクセシビリティ要件 (role, aria-*, keyboard navigation)"
          }
        }
      }
    }
  },
  "$defs": {
    "tokenRef": {
      "type": "string",
      "pattern": "^\\$tokens\\.",
      "description": "tokens.json への参照パス (例: $tokens.colors.primary)"
    }
  }
}
```

#### 2-2. design-scaffold: component-catalog.json 生成

DESIGN.md の Component Stylings セクションから自動生成:

- **Buttons** → `{ name: "Button", variants: [Primary, Secondary, Ghost, Destructive], states: [hover, focus, active, disabled] }`
- **Cards** → `{ name: "Card", variants: [Default], props: [title, children] }`
- **Inputs** → `{ name: "Input", variants: [Default, Error], states: [focus, error, disabled] }`
- **Navigation** → `{ name: "Nav", variants: [Default] }`

各スタイル値は `$tokens.*` 参照で表現（直書き値禁止）。

#### 2-3. React/Preact コンポーネント生成

catalog.json + tokens.json → 型安全なコンポーネント実装を生成。

**生成ルール:**
- CSS は tokens.css の custom properties 経由でのみスタイリング
- Props は catalog.json の props 定義に完全準拠
- Variants は catalog.json の variants で定義されたもののみ
- a11y 要件を HTML 属性として自動付与

**生成後の検証:**
- TypeScript 型チェック通過
- catalog.json の全 variants がカバーされていること
- tokens 参照が全て tokens.json に存在すること

#### 2-4. 未承認コンポーネント検出 lint

| ルール ID | 検出対象 | 説明 |
|-----------|---------|------|
| `DL101` | 未登録コンポーネント | catalog.json に定義されていないコンポーネントの使用 |
| `DL102` | 未登録バリアント | 定義されていない variant prop の使用 |
| `DL103` | 直接スタイル上書き | catalog コンポーネントへの inline style 注入 |

#### 2-5. Files to Create/Modify

```
NEW:
  skills/design-scaffold/references/catalog-schema.json

MODIFY:
  skills/design-scaffold/SKILL.md      # catalog 生成フロー追加
  skills/design-lint/SKILL.md          # DL101-103 ルール追加
  skills/design-lint/references/lint-contract.md  # catalog lint ルール追加
```

---

### Phase 3: Page Definition + Layout Rules

**目的:** ページ構成とレイアウトを schema で制約し、LLM の自由度をページ単位で制限する

#### 3-1. page-schema.json の設計

```jsonc
// page-schema.json（概要）
{
  "type": "object",
  "required": ["name", "route", "layout", "sections"],
  "properties": {
    "name":  { "type": "string" },
    "route": { "type": "string" },
    "layout": {
      "type": "object",
      "properties": {
        "type":       { "enum": ["single-column", "sidebar-left", "sidebar-right", "dashboard-grid", "split"] },
        "maxWidth":   { "$ref": "#/$defs/tokenRef" },
        "padding":    { "$ref": "#/$defs/tokenRef" }
      }
    },
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "components"],
        "properties": {
          "id":    { "type": "string" },
          "order": { "type": "number" },
          "components": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "component": { "type": "string", "description": "catalog のコンポーネント名" },
                "variant":   { "type": "string" },
                "props":     { "type": "object" },
                "repeat":    { "type": "boolean", "description": "リスト表示かどうか" }
              }
            }
          },
          "layout": {
            "type": "object",
            "properties": {
              "direction": { "enum": ["row", "column"] },
              "gap":       { "$ref": "#/$defs/tokenRef" },
              "wrap":      { "type": "boolean" }
            }
          }
        }
      }
    },
    "allowedComponents": {
      "type": "array",
      "items": { "type": "string" },
      "description": "このページで使用可能なコンポーネント名リスト（省略時は catalog 全体）"
    }
  }
}
```

#### 3-2. layout-schema.json の設計

```jsonc
// layout-schema.json（概要）
{
  "type": "object",
  "required": ["grid", "spacing", "responsive"],
  "properties": {
    "grid": {
      "type": "object",
      "properties": {
        "columns":   { "$ref": "#/$defs/tokenRef" },
        "gap":       { "$ref": "#/$defs/tokenRef" },
        "maxWidth":  { "$ref": "#/$defs/tokenRef" }
      }
    },
    "spacing": {
      "type": "object",
      "description": "各コンテキストでの spacing ルール",
      "properties": {
        "sectionGap":     { "$ref": "#/$defs/tokenRef" },
        "componentGap":   { "$ref": "#/$defs/tokenRef" },
        "internalPadding": { "$ref": "#/$defs/tokenRef" }
      }
    },
    "constraints": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "rule":        { "type": "string" },
          "enforcement": { "enum": ["lint", "visual", "rubric"] },
          "description": { "type": "string" }
        }
      },
      "description": "自然言語の Do's/Don'ts を機械検証可能なルールに変換"
    }
  }
}
```

#### 3-3. design-generate スキル

page-definition + component-catalog → 制約付きページ生成。

**生成プロセス:**
1. `.design/pages/{page}.json` を Read
2. `.design/component-catalog.json` を Read
3. `.design/tokens.json` を Read
4. `allowedComponents` で使用可能コンポーネントをフィルタ
5. `sections` の順序と構成に従いページを組み立て
6. 各コンポーネントは catalog 定義のコードをインポート（0から書かない）
7. layout-rules.json の constraints を適用
8. 生成後、design-lint を自動実行

**LLM の自由度:**
- 許可: セクション内のコンテンツ（テキスト・画像の内容）
- 許可: アニメーション・トランジション（schema 未定義領域）
- 禁止: コンポーネントの変更・追加
- 禁止: tokens にない値の使用
- 禁止: レイアウト構成の変更

#### 3-4. ページ定義 lint

| ルール ID | 検出対象 | 説明 |
|-----------|---------|------|
| `DL201` | page-def 未定義ページ | pages/ に定義がないページの作成 |
| `DL202` | allowedComponents 違反 | ページで許可されていないコンポーネントの使用 |
| `DL203` | セクション順序違反 | page-def の sections.order と異なる配置 |
| `DL204` | レイアウトルール違反 | layout-rules.json の constraints 違反 |

#### 3-5. Files to Create/Modify

```
NEW:
  skills/design-scaffold/references/page-schema.json
  skills/design-scaffold/references/layout-schema.json
  skills/design-generate/SKILL.md
  skills/design-generate/references/generation-constraints.md
  commands/design-generate.md

MODIFY:
  skills/design-scaffold/SKILL.md      # page/layout 生成フロー追加
  skills/design-lint/SKILL.md          # DL201-204 ルール追加
```

---

### Phase 3.5: Base Design Approval（人間の承認ゲート）

**目的:** 人間の主観判断を「1回の承認行為」に集約し、承認済み成果物を以降の全検証の baseline として確定する

#### 核心思想

100% 主観を排除するのは不可能。「何が正しいデザインか」の最終判断は人間にしかできない。
しかし、その判断は **1回で済む**。1回 OK を出せば、以降は「OK 出したものと同じかどうか」を機械的に判定するだけ。

#### 3.5-1. Base Mockup 生成

Phase 1-3 で作った scaffold（tokens + catalog + page-defs）から、**全コンポーネント + 代表ページ** の完成版 mockup を生成する。

**生成対象:**
- **コンポーネントカタログ**: catalog.json の全コンポーネント × 全 variant × 全 state を一覧表示するHTML
- **代表ページ**: pages/ に定義された各ページのフル実装 mockup
- tokens.css を適用済み、Google Fonts 読み込み済みのスタンドアロン HTML

**生成先:** `mockups/base/` ディレクトリ

```
mockups/base/
├── components.html        # 全コンポーネント一覧
├── landing.html           # pages/landing.json の実装
├── dashboard.html         # pages/dashboard.json の実装
└── ...
```

#### 3.5-2. 人間の承認フロー

1. 生成された mockup を「ブラウザで開いて確認して」と案内
2. AskUserQuestion で承認を求める:
   ```
   header: "Base Design 承認"
   options:
     - "承認する — このデザインを baseline として確定"
     - "修正が必要 — フィードバックを伝える"
   ```
3. 修正フィードバック → 修正 → 再生成 → 再度承認を求める（ループ）
4. 承認 → baseline 確定

#### 3.5-3. Baseline 確定

承認時に以下を実行:

1. **スクリーンショット取得**: Playwright で全 mockup のスクリーンショットを撮影
   ```
   .design/baseline/screenshots/
   ├── components/
   │   ├── button-primary.png
   │   ├── button-secondary.png
   │   ├── button-ghost.png
   │   ├── card-default.png
   │   └── ...
   ├── pages/
   │   ├── landing-desktop.png
   │   ├── landing-tablet.png
   │   ├── landing-mobile.png
   │   └── ...
   ```
2. **承認メタデータ記録**:
   ```json
   // .design/baseline/approval.json
   {
     "version": "1.0.0",
     "approvedAt": "2026-04-14T19:30:00Z",
     "approvedBy": "human",
     "tokensHash": "sha256:...",    // tokens.json のハッシュ
     "catalogHash": "sha256:...",   // catalog.json のハッシュ
     "screenshotCount": 24,
     "notes": "Initial base design approval"
   }
   ```
3. **mockups/base/ を Git コミット**: 承認済み成果物としてバージョン管理

#### 3.5-4. Baseline の再承認トリガー

以下の場合、baseline の再承認が必要:

- tokens.json の値が変更された（hash 不一致）
- catalog.json にコンポーネントが追加/変更された
- design-validate 実行時に approval.json の hash と現在の hash を比較し、不一致なら警告

#### 3.5-5. Files to Create/Modify

```
MODIFY:
  skills/design-scaffold/SKILL.md      # approval フロー追加
  skills/design-validate/SKILL.md      # hash 検証 + 再承認警告追加
```

---

### Phase 4: Visual Testing (Storybook + Playwright)

**目的:** コンポーネントとページの見た目を **承認済み baseline スクリーンショット** と比較し、差分を定量的に検出する

#### 4-1. Storybook stories 自動生成

component-catalog.json → `.stories.tsx` を自動生成。

**生成ルール:**
- 各コンポーネントの全 variants を stories として生成
- 全 states (hover, focus, active, disabled) をカバー
- tokens.css を decorator でグローバル注入
- Dark mode variant も生成（tokens にダーク定義がある場合）

#### 4-2. Playwright visual regression

```typescript
// tests/visual/components.spec.ts（生成テンプレート）
import { test, expect } from '@playwright/test';

test.describe('Design System Visual Regression', () => {
  test('Button - Primary variant', async ({ page }) => {
    await page.goto('/storybook/iframe.html?id=button--primary');
    await expect(page).toHaveScreenshot('button-primary.png', {
      maxDiffPixelRatio: 0.01,  // 1% まで許容
    });
  });
  // ... 全 variant × 全 state
});
```

**baseline 管理:**
- **Phase 3.5 で人間が承認した mockup のスクリーンショットが baseline** になる
- `.design/baseline/screenshots/` に保存済みのものを Playwright の expected として使用
- 以降の実行で差分を検出
- 閾値: `maxDiffPixelRatio: 0.01`（1%）— 設定可能
- baseline の再生成は Phase 3.5 の再承認フローを経由する（勝手に baseline を更新しない）

#### 4-3. ページレベル visual test

page-definition から全ページの visual regression test を生成。

- 各ページ × 各ブレークポイント (sm, md, lg, xl) でスクリーンショット
- responsive behavior が layout-rules に準拠しているか視覚的に確認

#### 4-4. design-validate スキル: visual test 実行

```
Step 1: Storybook ビルド (npx storybook build)
Step 2: Playwright テスト実行 (npx playwright test tests/visual/)
Step 3: 結果解析
  - 全 pass → ✅ Visual Gate 通過
  - diff あり → 差分ファイル一覧 + diff percentage レポート
  - baseline なし → 初回生成して baseline 確定
```

#### 4-5. Files to Create/Modify

```
NEW:
  skills/design-validate/SKILL.md
  skills/design-validate/references/validation-pipeline.md
  commands/design-validate.md

MODIFY:
  skills/design-scaffold/SKILL.md      # stories 生成フロー追加
```

---

### Phase 5: Rubric Judge

**目的:** 機械的に検証不能な「統一感」「体験の自然さ」を構造化ルーブリックで LLM 評価する

#### 5-1. rubric-schema.json の設計

```jsonc
// rubric-schema.json（概要）
{
  "type": "object",
  "required": ["version", "criteria"],
  "properties": {
    "version": { "type": "string" },
    "passingScore": { "type": "number", "description": "合格最低スコア (0-100)" },
    "criteria": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "weight", "scoring", "rubric"],
        "properties": {
          "id":     { "type": "string" },
          "name":   { "type": "string" },
          "weight": { "type": "number", "minimum": 0, "maximum": 1 },
          "scoring": { "enum": ["binary", "scale-5", "scale-10"] },
          "verification": { "enum": ["mechanical", "visual", "llm-judge"] },
          "rubric": {
            "type": "object",
            "description": "各スコアレベルの具体的な判定基準",
            "properties": {
              "pass":    { "type": "string" },
              "partial": { "type": "string" },
              "fail":    { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

#### 5-2. デフォルト rubric 項目

| ID | 名前 | 検証方法 | Weight |
|----|------|---------|--------|
| `R001` | Token Compliance | mechanical (lint) | 0.25 |
| `R002` | Component Compliance | mechanical (lint) | 0.20 |
| `R003` | Layout Compliance | mechanical (lint) | 0.15 |
| `R004` | Visual Consistency | visual (Playwright) | 0.15 |
| `R005` | Visual Harmony | llm-judge | 0.10 |
| `R006` | Interaction Coherence | llm-judge | 0.08 |
| `R007` | Responsive Behavior | visual (Playwright) | 0.07 |

**Weight 配分の原則:** mechanical (0.60) > visual (0.22) > llm-judge (0.18)
→ 機械検証が支配的。LLM judge は最後の 18% のみ。

#### 5-3. LLM Judge 実行

```
Input:
  - 生成されたコードのスクリーンショット
  - DESIGN.md の Do's/Don'ts セクション
  - rubric.json の llm-judge 項目

Prompt:
  「以下のスクリーンショットを DESIGN.md のデザインシステムに照らして評価してください。
   各項目について pass/partial/fail で判定し、根拠を1文で述べてください。」

Output:
  { "R005": { "score": "pass", "reason": "..." },
    "R006": { "score": "partial", "reason": "..." } }
```

**Judge の独立性:** 生成した LLM とは別のインスタンスで評価する（自己採点防止）。
design-validate スキル内で Agent ツールを使い、judge 専用エージェントを起動する。

#### 5-4. 統合ゲート

```
design-validate 実行フロー:

1. design-lint 実行 → R001, R002, R003 のスコア算出
   ├── 1つでも FAIL → 即停止、修正指示
   └── 全 PASS → 続行

2. Visual Test 実行 → R004, R007 のスコア算出
   ├── diff > 閾値 → 差分レポート + 修正指示
   └── 閾値以内 → 続行

3. Rubric Judge 実行 → R005, R006 のスコア算出
   └── 全項目の weighted average 算出

4. 総合判定
   ├── total >= passingScore → ✅ PASS（evidence 付き）
   └── total < passingScore  → ❌ FAIL（項目別改善提案）

Evidence 出力:
{
  "timestamp": "...",
  "scores": { "R001": 100, "R002": 100, ... },
  "totalScore": 94,
  "verdict": "PASS",
  "details": { ... }
}
```

#### 5-5. Files to Create/Modify

```
NEW:
  skills/design-scaffold/references/rubric-schema.json

MODIFY:
  skills/design-scaffold/SKILL.md      # rubric.json 生成追加
  skills/design-validate/SKILL.md      # rubric judge フロー追加
  skills/design-validate/references/validation-pipeline.md  # rubric 統合
```

---

## ✅ Tests

### Phase 1 検証項目
- [ ] tokens-schema.json が valid な JSON Schema であること
- [ ] サンプル DESIGN.md から tokens.json が正しく生成されること
- [ ] tokens.json が tokens-schema.json に対して valid であること
- [ ] tokens.css が tokens.json の全値を CSS custom properties として含むこと
- [ ] React theme.ts が tokens.json と 1:1 対応すること
- [ ] design-lint が直書きカラーコードを検出すること (DL001)
- [ ] design-lint が直書きフォントを検出すること (DL002)
- [ ] design-lint が直書き spacing を検出すること (DL003)
- [ ] design-lint が CSS 変数使用時に false positive を出さないこと
- [ ] design-lint の結果が JSON 形式でレポートされること

### Phase 2 検証項目
- [ ] catalog-schema.json が valid な JSON Schema であること
- [ ] DESIGN.md の Component Stylings から catalog.json が正しく生成されること
- [ ] catalog.json の全 token 参照が tokens.json に存在すること
- [ ] 生成された React コンポーネントが TypeScript 型チェックを通過すること
- [ ] 未登録コンポーネント使用を lint が検出すること (DL101)
- [ ] 未登録 variant 使用を lint が検出すること (DL102)

### Phase 3 検証項目
- [ ] page-schema.json / layout-schema.json が valid な JSON Schema であること
- [ ] ページ定義の allowedComponents が catalog.json に存在するコンポーネントのみ参照すること
- [ ] design-generate が page-def に従ったページを生成すること
- [ ] 生成されたページが design-lint を全項目パスすること
- [ ] allowedComponents 外のコンポーネント使用を lint が検出すること (DL202)

### Phase 3.5 検証項目
- [ ] base mockup が tokens.css を正しく適用していること
- [ ] base mockup が catalog.json の全コンポーネント × 全 variant を含むこと
- [ ] 承認フロー（AskUserQuestion → 修正ループ → 確定）が動作すること
- [ ] approval.json に正しいハッシュ値が記録されること
- [ ] Playwright でスクリーンショットが .design/baseline/screenshots/ に保存されること
- [ ] tokens.json 変更時に hash 不一致が検出され、再承認警告が出ること

### Phase 4 検証項目
- [ ] Storybook stories が catalog.json の全コンポーネント×全 variant をカバーすること
- [ ] Playwright スクリーンショット比較が動作すること
- [ ] baseline 生成 → 変更 → diff 検出の一連のフローが動作すること
- [ ] 各ブレークポイントでの responsive テストが動作すること

### Phase 5 検証項目
- [ ] rubric-schema.json が valid な JSON Schema であること
- [ ] mechanical 項目 (R001-R003) が lint 結果と一致すること
- [ ] visual 項目 (R004, R007) が Playwright 結果と一致すること
- [ ] LLM judge が構造化された判定を返すこと
- [ ] 統合ゲートの weighted average 算出が正しいこと
- [ ] evidence が verification-gate 契約に準拠すること

---

## 🔒 Security

- [ ] tokens.json に機密情報（API キー等）が混入しないことを検証
- [ ] 生成されたコンポーネントに XSS 脆弱性がないこと（dangerouslySetInnerHTML 禁止）
- [ ] LLM judge のプロンプトインジェクション対策（ユーザー入力を直接 rubric に含めない）
- [ ] .design/ ディレクトリにはコード実行可能なファイルを含めない（JSON/CSS のみ）

---

## 📊 Progress

| Step | Status |
|------|--------|
| Phase 1: Design Tokens Schema + Lint | 🟢 |
| Phase 2: Component Catalog Schema + 生成 | ⚪ |
| Phase 3: Page Definition + Layout Rules | ⚪ |
| Phase 3.5: Base Design Approval（人間の承認ゲート） | ⚪ |
| Phase 4: Visual Testing (Storybook + Playwright) | ⚪ |
| Phase 5: Rubric Judge | ⚪ |
| CLAUDE.md 更新 | ⚪ |
| plugin.json バージョンバンプ | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Review the plan → Write tests → Implement → Commit with `claude-skills:commit` 🚀
