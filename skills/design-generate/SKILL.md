---
name: design-generate
description: ページ定義（.design/pages/*.json）+ コンポーネントカタログに基づいて、制約付きでページを生成するスキル。LLM の自由度をセクション内コンテンツに限定し、デザインの再現性を保証する。「ページ生成」「design generate」「制約付き生成」で起動。
---

# Design Generate

ページ定義 + コンポーネントカタログに基づいて、**制約付き** でページを生成する。
LLM の自由度を「承認済みコンポーネントの組み立て」と「セクション内コンテンツ」に限定し、デザインの再現性を構造的に保証する。

**共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md) を参照。

## 前提条件

1. `.design/tokens.json` が存在すること
2. `.design/tokens.css` が存在すること
3. `.design/component-catalog.json` が存在すること
4. `.design/pages/` に1つ以上のページ定義が存在すること

いずれかが欠けている場合:
```
❌ 必要なファイルが見つかりません:
  {欠けているファイル一覧}

`/claude-skills:design-scaffold` で生成してください。
```

## Workflow

### Step 1: 生成対象の決定

$ARGUMENTS にページ名が指定されている場合はそのページを生成。
未指定の場合は AskUserQuestion で質問:

```
header: "生成するページ"
options:
  - pages/ 配下の各ページ定義を動的にリスト
  - "全ページ一括生成"
```

### Step 2: 定義ファイル読み込み

1. `.design/tokens.json` を Read
2. `.design/tokens.css` を Read
3. `.design/component-catalog.json` を Read
4. `.design/pages/{target}.json` を Read
5. `.design/layout-rules.json` を Read（存在する場合）

### Step 3: 制約の構築

ページ定義から以下の制約を構築:

#### コンポーネント制約
- `allowedComponents` が定義されている場合 → そのリスト内のコンポーネントのみ使用可
- 未定義の場合 → catalog 全体を許可
- 各コンポーネントは catalog の定義通りの props / variants / states のみ使用

#### レイアウト制約
- `layout.type` に従ったページ構造（single-column, sidebar, grid 等）
- `sections` の順序を厳守（`order` フィールドで制御）
- 各セクションの `layout`（direction, gap, columns）に従う

#### トークン制約
- 全ての色 → `var(--color-*)`
- 全てのフォント → `var(--font-*)`
- 全ての spacing → `var(--spacing-*)`
- 全ての角丸 → `var(--radius-*)`
- 全ての shadow → `var(--shadow-*)`

### Step 4: ページ生成

#### 生成プロセス

1. **ページシェル生成**: layout.type に基づいた HTML/JSX の外枠を構築
2. **セクション配置**: sections 定義の order 順にセクションを配置
3. **コンポーネント配置**: 各セクションの components 定義に従い、catalog のコンポーネントをインポート・配置
4. **コンテンツ注入**: 各コンポーネントの props にコンテンツ（テキスト・画像パス等）を設定
5. **スタイリング**: tokens.css の CSS 変数のみを使用してスタイリング
6. **レスポンシブ**: responsive 定義に従ったブレークポイント対応

#### LLM の自由度

**許可:**
- セクション内のコンテンツ（テキスト・画像の **内容**）
- アニメーション・トランジション（DESIGN.md / schema 未定義の領域）
- コンテンツの文言・ダミーデータ
- 画像の placeholder（`<img src="https://placehold.co/..." />`）

**禁止:**
- コンポーネントの追加・変更・削除
- tokens にない値の使用
- セクション構成の変更
- allowedComponents 外のコンポーネント使用
- inline style でのトークン対象プロパティ上書き
- カスタム CSS クラスでのトークン値直書き

#### 生成コードの構造

**React/Preact の場合:**
```typescript
// pages/{PageName}.tsx — Generated from .design/pages/{name}.json
import { Button, Card, Input, Nav } from '../components/react';
import '../.design/tokens.css';

export const {PageName}: React.FC = () => {
  return (
    <div className="page page--{layout.type}" style={{ maxWidth: 'var(--spacing-max-content-width)' }}>
      {/* Section: {section.id} */}
      <section className="section section--{section.id}">
        {/* Components placed per page definition */}
      </section>
    </div>
  );
};
```

**HTML スタンドアロンの場合:**
```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page.title}</title>
  <link rel="stylesheet" href=".design/tokens.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <!-- Google Fonts links from tokens.typography -->
  <style>
    /* Page-specific layout styles using CSS variables only */
  </style>
</head>
<body>
  <!-- Sections and components per page definition -->
</body>
</html>
```

### Step 5: 自動 Lint 実行

生成完了後、即座に design-lint を実行して違反を検出:

1. 生成されたファイルに対して DL001-006 + DL101-103 を適用
2. 違反が検出された場合:
   - 自動修正（var(--*) への置換等）を試みる
   - 修正不能な違反はエラーとしてレポート
3. 全ルール PASS を確認してから出力

### Step 6: 出力と確認

**生成先:**
- React: `src/pages/{PageName}.tsx`（AskUserQuestion で出力先を確認）
- HTML: `mockups/{page-name}.html`

```
✅ ページを生成しました！
📄 File: {output_path}

📊 使用コンポーネント:
  {コンポーネント名}: {variant} × {個数}

🔍 Lint: PASS ✅
  DL001-006: 0 violations
  DL101-103: 0 violations

ブラウザで開いて確認してね。
修正したい場合はフィードバックを教えてください。
```

AskUserQuestion で追加調整を確認:
- 「OK」→ 終了
- 修正フィードバック → Edit で修正 → 再 lint → 再確認（ループ）

## ページ定義の対話的作成

`.design/pages/` が空の場合、または新しいページを追加したい場合:

1. AskUserQuestion でページの種類を質問:
   ```
   header: "ページタイプ"
   options:
     - "ランディングページ"
     - "ダッシュボード"
     - "一覧ページ"
     - "フォームページ"
   ```
2. layout-rules.json の `patterns` から推奨パターンを提案
3. AskUserQuestion でセクション構成を確認
4. catalog.json のコンポーネントリストから各セクションの配置を決定
5. `.design/pages/{name}.json` に Write
6. 続けてページ生成に進む

## 絶対的な制約

- **ページ定義なしの生成は禁止**。必ず `.design/pages/*.json` を経由する
- 生成コードは **design-lint の全ルールに PASS** しなければならない
- コンポーネントのインポートは catalog 生成ファイルからのみ（自前定義禁止）
- CSS 値は全て CSS custom properties 経由（直書き値禁止）
- page-def の `sections.order` を変更してはならない

## References

- **Page Schema:** [../design-scaffold/references/page-schema.json](../design-scaffold/references/page-schema.json)
- **Layout Schema:** [../design-scaffold/references/layout-schema.json](../design-scaffold/references/layout-schema.json)
- **Catalog Schema:** [../design-scaffold/references/catalog-schema.json](../design-scaffold/references/catalog-schema.json)
- **共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
