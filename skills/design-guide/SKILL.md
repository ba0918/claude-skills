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

## Mockup Workflow（DESIGN.md に基づくモックアップ生成）

DESIGN.md のトークンを **厳密に適用** してモックアップを生成する。
frontend-design スキルの美学原則を活用しつつ、カラー・フォント・スペーシングは DESIGN.md の定義に従う。

### 前提チェック

1. プロジェクトルートに `DESIGN.md` が存在するか確認
   - なければ「DESIGN.md が見つかりません。`/claude-skills:design-guide` で新規作成してください」と表示して終了
2. `DESIGN.md` を Read で読み込み、全トークンを把握

### Step 1: モックアップ対象の決定

AskUserQuestion で何をモックアップするか質問:

header: "対象"

| Option | Description |
|--------|-------------|
| ページレイアウト | ランディングページ、ダッシュボード、設定画面等の全体レイアウト |
| コンポーネント集 | ボタン・カード・フォーム・ナビ等の主要コンポーネント一覧 |
| 特定の画面 | ユーザー指定の具体的な画面（ログイン、プロフィール等） |

`mockup` 以降の $ARGUMENTS に具体的な指示があればそれを優先する。

### Step 2: 出力形式の決定

AskUserQuestion で出力形式を質問:

header: "出力形式"

| Option | Description |
|--------|-------------|
| HTML + CSS（スタンドアロン） | ブラウザで即開けるシングルファイル HTML。CDN フォント読み込み付き |
| React コンポーネント | JSX + CSS-in-JS or CSS Modules。プロジェクトに組み込み可能 |
| HTML + Tailwind | Tailwind CSS クラスを使用。CDN 読み込みでスタンドアロン動作 |

### Step 3: モックアップ生成

#### 絶対的な制約（トークン厳守ルール）

以下の値は **DESIGN.md に定義されたもののみ** を使用する。独自の値を発明してはならない:

- **色**: Color Palette セクションの値のみ。`rgba()` 変換や `opacity` 調整は許可するが、新しい色の導入は禁止
- **フォント**: Typography セクションのフォントファミリーのみ。サイズ・ウェイトも定義に従う
- **スペーシング**: Layout Principles の spacing scale の値のみ
- **角丸**: Component Stylings の border-radius 値のみ
- **シャドウ**: Depth & Elevation の shadow 定義のみ
- **ブレークポイント**: Responsive Behavior の値のみ

#### 創造的自由の範囲

トークンを厳守した上で、以下は自由に工夫する:

- レイアウト構成（グリッドの使い方、セクション配置）
- アニメーション・トランジション（DESIGN.md で未定義の領域）
- コンテンツ配置（テキスト・画像のバランス）
- インタラクションパターン（hover 演出の具体的な実装）
- [references/anti-patterns.md](references/anti-patterns.md) のポジティブパターンを積極的に活用

#### 生成プロセス

1. DESIGN.md からトークンを CSS 変数として抽出:
   ```css
   :root {
     --color-primary: #XXXXXX;
     --color-secondary: #XXXXXX;
     --font-heading: 'Font Name', fallback;
     --spacing-base: Npx;
     /* ... DESIGN.md の全トークン ... */
   }
   ```
2. CSS 変数を使ってコンポーネントとレイアウトを実装
3. Google Fonts の `<link>` タグでフォントを読み込む（HTML 出力の場合）
4. レスポンシブ対応: DESIGN.md の Responsive Behavior に従う

### Step 4: 出力と確認

1. モックアップファイルを Write ツールで生成:
   - HTML: `mockups/{name}.html`
   - React: `mockups/{name}.tsx` + `mockups/{name}.css`
   - 出力先ディレクトリは必要に応じて `mkdir -p`
2. 完了メッセージ:
   ```
   ✅ モックアップを生成しました！
   📄 File: mockups/{name}.html
   
   ブラウザで開いて確認してね。
   修正したい場合はフィードバックを教えてください。
   ```
3. AskUserQuestion で追加の調整要望を確認:
   - 「OK！」→ 終了
   - 修正フィードバック → Edit で調整して再度確認（ループ）

### トークン違反チェック

モックアップ生成後、以下を自己検証する:

1. CSS で使われている色が全て DESIGN.md の Color Palette に存在するか
2. font-family が DESIGN.md の Typography に定義されたものか
3. padding / margin / gap が DESIGN.md の spacing scale の値か
4. border-radius が Component Stylings の定義値か

違反がある場合は修正してから出力する。

---

## References

- **テンプレート:** [references/design-md-template.md](references/design-md-template.md)
- **質問バンク:** [references/discovery-questions.md](references/discovery-questions.md)
- **アンチパターン:** [references/anti-patterns.md](references/anti-patterns.md)

## Notes

- DESIGN.md は AI エージェント向けの「デザインシステム翻訳レイヤー」であり、完全なデザインシステムの代替ではない
- 生成された DESIGN.md は Git でバージョン管理し、デザイン変更は PR レビュー対象にすることを推奨
- frontend-design スキルと併用する場合、DESIGN.md のトークンが優先される（frontend-design の汎用ガイドラインより、プロジェクト固有の定義が上位）
