---
name: design-guide
description: プロジェクト用の DESIGN.md（デザインシステム定義）を対話型ディスカバリーで作成し、それに基づくモックアップも生成するスキル。二択の具体的な選択肢でぼんやりしたデザインイメージを構造化し、AIっぽくない一貫したUI生成の基盤を作る。「デザインガイド」「design guide」「DESIGN.md作成」「デザイントークン」「モックアップ」「mockup」で起動。
---

# Design Guide

プロジェクト用の DESIGN.md を対話型ディスカバリーで作成するスキル。
Google Stitch が提唱した DESIGN.md フォーマットに準拠し、AI コーディングエージェントが一貫したUIを生成するためのデザインシステム定義を生成する。

**核心**: デザインの指示は言語化が難しい。オープンクエスチョンではなく **二択〜四択の具体的な選択肢** で方向性を絞り込み、ユーザーのぼんやりしたイメージを構造化する。

## Workflow Selection

$ARGUMENTS の先頭キーワードでワークフローを決定する:

- `update` → **Update Workflow**（既存 DESIGN.md の修正）
- `mockup` → **Mockup Workflow**（DESIGN.md に基づくモックアップ生成）
- (なし or 説明文字列) → **Session Workflow**（新規作成）

---

## Session Workflow（対話型ディスカバリー → DESIGN.md 生成）

### 絶対的な制約

#### ディスカバリー中（Phase 1-5）の禁止ツール

- **Edit** ツール — ファイル編集禁止
- **Write** ツール — ファイル作成禁止
- **NotebookEdit** ツール — ノートブック編集禁止

Phase 6（生成フェーズ）でのみファイル書き込みを許可する。

#### 許可ツール

- **AskUserQuestion** — ユーザーとの対話（メインの進行手段）
- **Read** — 既存プロジェクトの調査（コードベース・設定ファイルの確認用）
- **Grep / Glob** — パターン検索（既存スタイル・フレームワークの検出用）
- **Bash** — 読み取り専用コマンドのみ

### フロー概要

```
Phase 1: プロジェクトコンテキスト把握
Phase 2: ビジュアルムード決定（二択ラッシュ）
Phase 3: カラーパレット選定
Phase 4: タイポグラフィ選定
Phase 5: コンポーネント＆レイアウト確認
Phase 6: DESIGN.md 生成
```

### 事前チェック

1. プロジェクトルートに `DESIGN.md` が既に存在するか確認
   - 存在する場合: 「既存の DESIGN.md があります。上書きしますか？ それとも `/claude-skills:design-guide-update` で部分修正しますか？」と AskUserQuestion で確認
   - 上書きを選んだ場合: 続行
   - 部分修正を選んだ場合: Update Workflow に切り替え
2. プロジェクトの技術スタック検出（Glob/Grep で package.json, Cargo.toml, go.mod, pubspec.yaml 等を確認）
   - フレームワーク（React, Vue, Svelte, Flutter 等）を特定し、コンポーネントスタイリングの提案に反映

### Phase 1: プロジェクトコンテキスト

質問バンク: [references/discovery-questions.md](references/discovery-questions.md) の Phase 1 を参照。

1. AskUserQuestion でプロジェクトの種類を質問
2. AskUserQuestion でターゲットユーザーを質問
3. AskUserQuestion で与えたい印象を質問（multiSelect: true）
4. $ARGUMENTS にプロジェクト説明があればそれも考慮

**中間まとめ**: Phase 1 の回答を整理してユーザーに表示。

```
📋 Phase 1 まとめ
- プロジェクト: {type}
- ターゲット: {audience}
- 印象: {impressions}
- 技術スタック: {detected_stack}

この方向で Phase 2 に進みます！
```

### Phase 2: ビジュアルムード（二択ラッシュ）

質問バンク: [references/discovery-questions.md](references/discovery-questions.md) の Phase 2 を参照。

6-7 問の二択〜三択を AskUserQuestion で1問ずつ出す:

1. カラーモード（ライト / ダーク / 両対応）
2. カラートーン（暖色 / 寒色 / ニュートラル）
3. 情報密度（ゆったり / みっちり）
4. 角の形状（まるっと / カクッと / 中間）
5. 色の強さ（ビビッド / ミュート）
6. 深度表現（フラット / 立体的）
7. フォントの方向性（サンセリフ / セリフ / ミックス）

**中間まとめ**: Phase 2 の回答を整理してユーザーに表示。

```
🎨 Phase 2 まとめ（ビジュアルムード）
- カラーモード: {mode}
- トーン: {tone}
- 密度: {density}
- 角丸: {radius}
- 彩度: {saturation}
- 深度: {depth}
- フォント: {font_direction}

この方向でカラーパレットを提案します！
```

### Phase 3: カラーパレット選定

質問バンク: [references/discovery-questions.md](references/discovery-questions.md) の Phase 3 を参照。
アンチパターン: [references/anti-patterns.md](references/anti-patterns.md) のカラーセクションを照合。

1. Phase 2 の回答から解釈マトリクスに基づき **3つのパレット候補** を生成
2. AskUserQuestion の **preview** フィールドで各パレットを ASCII 表現で提示:
   ```
   Option A: "名前"
   ──────────────────
   Primary:    #XXXXXX ████
   Secondary:  #XXXXXX ████
   Accent:     #XXXXXX ████
   Background: #XXXXXX
   Surface:    #XXXXXX ████
   Text:       #XXXXXX ████
   Error:      #DC2626 ████
   Success:    #16A34A ████
   ```
3. ユーザーが選択後、微調整を AskUserQuestion で確認（「この色味で OK？」）
4. Dark Mode を定義する場合は、同じ流れでダークパレットも提案

**アンチパターンチェック**: 生成したパレットが anti-patterns.md の禁止カラーパターンに該当しないことを確認。該当する場合は別候補を生成。

### Phase 4: タイポグラフィ選定

質問バンク: [references/discovery-questions.md](references/discovery-questions.md) の Phase 4 を参照。
アンチパターン: [references/anti-patterns.md](references/anti-patterns.md) の禁止フォントを照合。

1. Phase 2 の Q10 回答に基づき **3つのフォントペアリング候補** を生成
2. AskUserQuestion の **preview** で各候補を提示:
   ```
   Option A: "Clean Tech"
   ──────────────────────
   Heading: Outfit (700)
   Body:    Plus Jakarta Sans (400)
   Code:    JetBrains Mono (400)

   Scale:
   Display  48px / H1 36px / H2 28px
   H3 22px / Body 16px / Caption 12px
   ```
3. ユーザーが選択後、サイズスケールの微調整を確認

**禁止チェック**: 生成したフォント候補に anti-patterns.md の禁止フォントが含まれていないことを確認。

### Phase 5: コンポーネント＆レイアウト確認

質問バンク: [references/discovery-questions.md](references/discovery-questions.md) の Phase 5 を参照。

1. Phase 2-4 の全回答から自動導出ルールに基づきコンポーネントスタイルを提案
2. AskUserQuestion の **preview** で主要コンポーネントのスタイルを提示:
   ```
   ┌─────────────────────────────┐
   │ Components Preview          │
   ├─────────────────────────────┤
   │                             │
   │  [■ Primary Button]         │
   │  border-radius: 12px       │
   │  padding: 12px 24px         │
   │                             │
   │  ┌─── Card ──────────────┐  │
   │  │ radius: 16px          │  │
   │  │ shadow: sm             │  │
   │  │ padding: 24px          │  │
   │  └───────────────────────┘  │
   │                             │
   │  [________Input________]    │
   │  radius: 8px, border: 1px  │
   │                             │
   │  Spacing: 8px base          │
   │  Scale: 4 8 12 16 24 32 48 │
   │  Max width: 1200px          │
   └─────────────────────────────┘
   ```
3. 「この方向で OK？微調整ある？」と AskUserQuestion で確認
4. Do's / Don'ts を Phase 2 の回答に基づいて自動生成し、確認
5. レスポンシブのブレークポイントとモバイル戦略を確認

### Phase 6: DESIGN.md 生成

テンプレート: [references/design-md-template.md](references/design-md-template.md) を使用。

1. Phase 1-5 で収集した全決定事項をテンプレートに流し込む
2. プロジェクトルートに `DESIGN.md` を **Write** ツールで生成
3. CLAUDE.md への参照追記を **提案** する（自動追記はしない）:
   ```
   📝 CLAUDE.md に以下を追記することを推奨します:

   ## Design System
   This project uses a design system defined in `DESIGN.md` at the project root.
   Always refer to this file when generating or modifying any UI component.
   - Use only colors, fonts, and spacing values defined in DESIGN.md
   - Do not invent new values or use defaults from any framework
   - Match component states to the patterns in DESIGN.md
   ```
4. AskUserQuestion で CLAUDE.md への追記を実行するか確認
   - 「追記する」→ CLAUDE.md を Read → 末尾に追記
   - 「自分でやる」→ スキップ
5. 完了メッセージ:
   ```
   ✅ DESIGN.md を生成しました！
   📄 File: DESIGN.md
   
   これで AI がUIを生成する時、このファイルを参照して一貫したデザインを保てます。
   修正したい場合は `/claude-skills:design-guide-update` を使ってね。
   ```
6. **scaffold への導線:**
   ```
   🔧 機械的検証を有効にするには:
   `/claude-skills:design-scaffold` で tokens.json + lint 設定を生成できます。
   これにより、デザイントークン違反の自動検出が可能になります。
   ```

---

## Update Workflow（既存 DESIGN.md の修正）

### 前提チェック

1. プロジェクトルートに `DESIGN.md` が存在するか確認
   - なければ「DESIGN.md が見つかりません。`/claude-skills:design-guide` で新規作成してください」と表示して終了

### Steps

1. `DESIGN.md` を Read で読み込む
2. 現在のデザインシステムの概要を表示:
   ```
   📋 現在の DESIGN.md
   - Theme: {mood}
   - Primary: {primary_color}
   - Font: {heading_font} / {body_font}
   - Density: {density}
   - Radius: {radius_style}
   ```
3. AskUserQuestion でどのセクションを修正するか質問:
   - Visual Theme & Atmosphere
   - Color Palette
   - Typography
   - Component Stylings
   - Layout Principles
   - その他（フリーテキスト）
4. 選択されたセクションに対して、Session Workflow の該当 Phase と同じ対話フローを実行
   - Color Palette → Phase 3 相当
   - Typography → Phase 4 相当
   - Component Stylings → Phase 5 相当
   - Visual Theme → Phase 1-2 相当（ただし影響する他セクションの更新も提案）
5. 修正内容を preview で確認後、Edit ツールで DESIGN.md を更新
6. 変更箇所のサマリーを表示:
   ```
   ✅ DESIGN.md を更新しました！
   📝 変更箇所:
   - {section}: {変更内容の要約}
   ```

### 連鎖更新の提案

あるセクションの変更が他セクションに影響する場合（例: Primary カラー変更 → Component Stylings のボタン色も変わる）、AskUserQuestion で連鎖更新を提案する。

---

## Mockup Workflow（Schema ベースモックアップ生成 + Base Design 承認）

**v2 設計:** `.design/` の schema（tokens + catalog + page-schema）に基づいてモックアップを生成し、
自動 lint 検証の後、人間の承認を得て **baseline を確定** する。
このフローが「人間の主観判断を1回に集約する」ゲートウェイとなる。

```
┌─────────────────────────────────────────────┐
│ フィードバックループ（納得いくまで繰り返し）    │
│                                             │
│  Step 1: 前提チェック + scaffold 有無確認      │
│  Step 2: ページ定義の対話作成 or 確認          │
│  Step 3: モックアップ生成（schema 制約付き）    │
│  Step 4: 自動 lint 検証（DL001-204）          │
│  Step 5: 人間に提示 + フィードバック           │
│    └── 修正要望あり → Step 2 or 3 に戻る      │
│  Step 6: 承認 → baseline 確定 ★              │
└─────────────────────────────────────────────┘
```

### 前提チェック

1. プロジェクトルートに `DESIGN.md` が存在するか確認
   - なければ「`/claude-skills:design-guide` で DESIGN.md を作成してください」と表示して終了
2. `.design/tokens.json` が存在するか確認
   - なければ「`/claude-skills:design-scaffold` で tokens を生成してください」と表示して終了
3. `.design/component-catalog.json` が存在するか確認
   - なければ「`/claude-skills:design-scaffold` で catalog を生成してください」と表示して終了
4. 全ファイルを Read で読み込み:
   - `.design/tokens.json`
   - `.design/tokens.css`
   - `.design/component-catalog.json`
   - `.design/layout-rules.json`（存在する場合）
   - `.design/pages/*.json`（存在する場合）

### Step 1: モックアップ対象の決定

AskUserQuestion で何をモックアップするか質問:

header: "対象"

| Option | Description |
|--------|-------------|
| コンポーネントカタログ | catalog.json の全コンポーネント × 全 variant を一覧表示 |
| ページモックアップ | ページ定義に基づく完全なページ（なければ対話で定義作成） |
| フルセット（推奨） | コンポーネント一覧 + 全ページ。Base Design 承認に最適 |

`mockup` 以降の $ARGUMENTS に具体的な指示があればそれを優先する。

### Step 2: ページ定義の作成 or 確認

#### `.design/pages/` にページ定義がない場合

AskUserQuestion でページ構成を対話的に決定し、page-schema.json に準拠するページ定義を生成する。

1. AskUserQuestion でプロジェクトの主要ページを質問:
   ```
   header: "主要ページ"
   question: "モックアップを作るページを選んでください"
   multiSelect: true
   options:
     - "ランディングページ"
     - "ダッシュボード"
     - "一覧ページ"
     - "フォームページ"
   ```
2. 各ページに対して:
   - レイアウトタイプを質問（single-column / sidebar / dashboard-grid / split）
   - セクション構成を提案し確認
   - 使用コンポーネントを catalog.json から選択
3. `.design/pages/{page-name}.json` に Write

#### `.design/pages/` にページ定義がある場合

既存のページ定義を表示し、このまま使うか修正するか確認。

### Step 3: モックアップ生成

#### 出力形式

AskUserQuestion で出力形式を質問:

header: "出力形式"

| Option | Description |
|--------|-------------|
| HTML + CSS（スタンドアロン）（推奨） | ブラウザで即開けるシングルファイル HTML。Base Design 確認に最適 |
| React コンポーネント | JSX + CSS Modules。プロジェクトに組み込み可能 |
| HTML + Tailwind | Tailwind CSS クラスを使用。CDN 読み込みでスタンドアロン動作 |

#### 絶対的な制約（Schema 制約）

以下の値は **tokens.json / catalog.json / page-schema に定義されたもののみ** を使用する:

- **色**: tokens.json の `colors.*` のみ。CSS 変数 `var(--color-*)` 経由で使用
- **フォント**: tokens.json の `typography.*` のみ。CSS 変数 `var(--font-*)` 経由
- **スペーシング**: tokens.json の `spacing.scale` のみ。CSS 変数 `var(--spacing-*)` 経由
- **角丸**: tokens.json の `components.*.borderRadius` のみ。CSS 変数 `var(--radius-*)` 経由
- **シャドウ**: tokens.json の `depth.*.shadow` のみ。CSS 変数 `var(--shadow-*)` 経由
- **コンポーネント**: catalog.json に定義されたもののみ
- **ページ構成**: pages/*.json のセクション定義に準拠
- **ブレークポイント**: tokens.json の `responsive.breakpoints` のみ

#### 創造的自由の範囲

schema を厳守した上で、以下は自由に工夫する:

- セクション内のコンテンツ（テキスト・ダミーデータ・画像 placeholder）
- アニメーション・トランジション（schema 未定義の領域）
- [references/anti-patterns.md](references/anti-patterns.md) のポジティブパターンの活用

#### 生成プロセス

1. `.design/tokens.css` を `<link>` or `<style>` で読み込み
2. Google Fonts の `<link>` タグでフォント読み込み
3. catalog.json に基づくコンポーネントの HTML/JSX を構築
4. pages/*.json のセクション定義に従いページ構成
5. レスポンシブ対応: tokens.json の responsive.breakpoints に従う
6. **コンポーネントカタログ HTML** を生成:
   - catalog.json の全コンポーネント × 全 variant × 全 state を一覧表示
   - 各コンポーネントのスタイルを視覚的に確認可能な形式

出力先:
```
mockups/base/
├── components.html       # コンポーネントカタログ
├── {page-name}.html      # 各ページのモックアップ
└── ...
```

### Step 4: 自動 lint 検証

生成されたモックアップに対して、design-lint のロジックを即座に適用:

1. 全モックアップファイルに DL001-006（Token Compliance）を適用
2. DL101-103（Component Compliance）を適用
3. DL201-204（Page/Layout Compliance）を適用
4. 結果をサマリー表示:

```
🔍 Mockup Lint Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files: mockups/base/*.html
Token Compliance (DL001-006): ✅ 0 violations
Component Compliance (DL101-103): ✅ 0 violations
Page Compliance (DL201-204): ✅ 0 violations

Result: ALL PASS ✅
```

**lint FAIL の場合:** 自動修正を試み、修正不能な違反はエラーとしてレポート。修正後に再検証。
lint が全 PASS するまで Step 5 に進まない。

### Step 5: 人間に提示 + フィードバック

lint PASS 後、モックアップを人間に提示:

```
✅ モックアップを生成しました！（lint: ALL PASS）

📁 生成ファイル:
  mockups/base/components.html — コンポーネントカタログ
  mockups/base/{page-name}.html — {ページ名}

ブラウザで開いて確認してね。
```

AskUserQuestion で承認 or フィードバック:

```
header: "Base Design 確認"
options:
  - "承認する — このデザインを baseline として確定"
  - "トークンを調整したい — 色・フォント・spacing 等を変えたい"
  - "コンポーネントを調整したい — variant やスタイルを変えたい"
  - "ページ構成を変えたい — セクションの追加・削除・並び替え"
```

#### フィードバックループ

| フィードバック種別 | ループ先 | 操作 |
|------------------|---------|------|
| トークン調整 | `/design-guide-update` → `/design-scaffold` → Step 3 | DESIGN.md 修正 → tokens 再生成 → モック再生成 |
| コンポーネント調整 | `/design-scaffold` → Step 3 | catalog 修正 → モック再生成 |
| ページ構成変更 | Step 2 → Step 3 | page-schema 修正 → モック再生成 |
| 微調整（テキスト・配置） | Step 3 | Edit でモック直接修正 → 再 lint |

### Step 6: 承認 → Baseline 確定

承認が得られた場合:

1. **スクリーンショット取得**（Playwright が利用可能な場合）:
   ```bash
   # 各モックアップのスクリーンショットを撮影
   npx playwright screenshot mockups/base/components.html .design/baseline/screenshots/components.png
   ```
   Playwright 未導入の場合は「手動でスクリーンショットを `.design/baseline/screenshots/` に保存してください」と案内

2. **approval.json 生成**:
   ```json
   {
     "version": "1.0.0",
     "approvedAt": "{ISO 8601 timestamp}",
     "approvedBy": "human",
     "tokensHash": "{SHA-256 of tokens.json}",
     "catalogHash": "{SHA-256 of component-catalog.json}",
     "screenshotCount": {N},
     "mockupFiles": ["components.html", "{page-name}.html", ...],
     "notes": ""
   }
   ```
   `.design/baseline/approval.json` に Write

3. **完了メッセージ**:
   ```
   ✅ Base Design を承認し、baseline を確定しました！
   
   📁 Baseline:
     .design/baseline/approval.json — 承認メタデータ
     .design/baseline/screenshots/  — Visual test の baseline
   
   これ以降の UI 生成は、この baseline に対して機械的に検証されます。
   
   次のステップ:
     `/claude-skills:design-generate` で実際のコードを生成
     `/claude-skills:design-validate` で検証ゲートを実行
   
   ⚠️ tokens.json や catalog.json を変更した場合、
   baseline の再承認が必要です（hash 不一致で自動検出）。
   ```

---

## References

- **テンプレート:** [references/design-md-template.md](references/design-md-template.md)
- **質問バンク:** [references/discovery-questions.md](references/discovery-questions.md)
- **アンチパターン:** [references/anti-patterns.md](references/anti-patterns.md)

## Notes

- DESIGN.md は AI エージェント向けの「デザインシステム翻訳レイヤー」であり、完全なデザインシステムの代替ではない
- 生成された DESIGN.md は Git でバージョン管理し、デザイン変更は PR レビュー対象にすることを推奨
- frontend-design スキルと併用する場合、DESIGN.md のトークンが優先される（frontend-design の汎用ガイドラインより、プロジェクト固有の定義が上位）
