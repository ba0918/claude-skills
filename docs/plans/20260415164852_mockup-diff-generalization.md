# mockup-diff スキルの汎用化リファクタ

**Cycle ID:** `20260415164852`
**Started:** 2026-04-15 16:48:52
**Status:** 🟢 Completed

---

## 📝 What & Why

承認済みモックアップ HTML と実アプリの視覚差分を検出・修正するスキル `mockup-diff` を、特定プロジェクト（screen-knowledge Tauri GUI）へのハードコードから脱却させ、任意のプロジェクトで使える汎用スキルにリファクタする。

**背景:** design-validate はトークン準拠の機械的検証（lint + pixel diff + rubric）。mockup-diff は「承認したモックと実装のラストワンマイルの差異」を検出する別レイヤーのスキル。実際に design-guide → scaffold → generate の成果物をアプリに落とし込む際、padding/margin のズレ、フォント組み込みミス、動的状態でのレイアウト崩れが頻発しており、その差分検出・修正フローが必要。

## 🎯 Goals

- 特定プロジェクトへのハードコードを完全撤廃し、任意のフレームワーク（Tauri, Next.js, Vite+React, etc.）で使えるようにする
- Phase 0: SETUP でプロジェクトを自動調査し、テーラーメイドの比較スクリプトを LLM が生成する設計にする
- コマンドファイル・CLAUDE.md 登録・design-system-contract への組み込みなど、正式なスキルとしてのインフラを整備する

## 📐 Design

### アーキテクチャ概要

```
現状: 1つのハードコードされたスクリプトで全部やる
  scripts/compare-mockup-app.mjs ← screen-knowledge 専用

変更後: LLM がプロジェクトに合わせてスクリプトを生成する
  SKILL.md (Phase 0: SETUP)
    ├── プロジェクト調査（フレームワーク、ビルドツール、ナビ構造、モック要件）
    ├── モックアップ HTML の DOM 構造解析
    ├── 比較スクリプト生成 → ターゲットプロジェクトの .design/mockup-diff/compare.mjs
    └── 設定ファイル生成 → ターゲットプロジェクトの .design/mockup-diff/config.json
  references/
    └── script-requirements.md ← 生成スクリプトが満たすべき要件・制約
```

### デザインパイプラインにおける位置づけ

```
design-guide → design-scaffold → design-generate
         ↓                              ↓
    [HUMAN APPROVAL]               mockups/base/*.html
         ↓                              ↓
    baseline 確定              実装に落とし込み
         ↓                              ↓
    design-validate            mockup-diff ← ★ここ
    (トークン準拠の             (モック vs 実アプリの
     機械的検証)                 実装品質検証)
```

- **design-validate**: baseline スクショ vs 実装コード。トークン違反・pixel diff・rubric judge
- **mockup-diff**: モックアップ HTML vs 実行中アプリ。spacing/font/layout の実装差異を特定・修正

### Files to Change

```
skills/mockup-diff/
  SKILL.md                      - 全面リライト（Phase 0 新設、汎用化）
  scripts/compare-mockup-app.mjs - 削除（ハードコードスクリプト）
  references/
    script-requirements.md      - 新規作成（生成スクリプトの要件定義）

commands/
  mockup-diff.md                - 新規作成（コマンドエントリーポイント）

skills/shared/references/
  design-system-contract.md     - mockup-diff の位置づけを追記

CLAUDE.md                       - コマンド→スキルマッピングに追加
plugin.json                     - バージョンバンプ (1.19.0 → 1.20.0)
```

### Key Points

- **スクリプト生成アプローチ**: 汎用スクリプトで全フレームワーク対応を目指すのではなく、SETUP Phase で LLM がプロジェクトを調査し、そのプロジェクト専用の比較スクリプトを生成する。Tauri なら invoke モック注入、Next.js なら別アプローチ、素 Vite なら更にシンプル
- **生成スクリプトの出力先**: ターゲットプロジェクトの `.design/mockup-diff/` ディレクトリ。design-system-contract のファイル構造契約に追加
- **config.json**: フレームワーク種別、ページ一覧、ビューポート、dev server 起動コマンド、ナビゲーション方法等をプロジェクト固有の設定として保持
- **script-requirements.md**: 生成スクリプトが必ず満たすべき要件（Playwright 使用、エラーハンドリング、出力形式、タイムアウト処理等）を参照資料として定義

### SKILL.md のフロー設計

```
Phase 0: SETUP（初回 or 設定変更時）
  ├── Step 1: プロジェクト調査
  │     ├── フレームワーク検出（package.json, Cargo.toml 等）
  │     ├── ビルドツール検出（Vite, webpack, Next.js dev server 等）
  │     ├── モックアップ HTML の DOM 構造解析（ナビ、ページ切替、クラス名）
  │     └── API モック要件の特定（Tauri invoke, fetch 等）
  ├── Step 2: config.json 生成
  │     └── ユーザー確認（AskUserQuestion）
  ├── Step 3: compare.mjs 生成
  │     └── script-requirements.md の制約に準拠
  └── Step 4: 動作確認（dry run）

Phase 1: CAPTURE
  └── .design/mockup-diff/compare.mjs を実行

Phase 2: COMPARE
  └── Read ツールでスクショを並べて確認

Phase 3: ANALYZE
  └── 差分をカテゴリ分類してレポート

Phase 4: FIX
  └── コード修正 + テスト更新

Phase 5: VERIFY
  └── 再実行で差分解消確認
```

### config.json のスキーマ設計

```json
{
  "framework": "tauri|nextjs|vite|cra|...",
  "devServer": {
    "command": "pnpm dev",
    "port": 5173,
    "readyPattern": "Local:"
  },
  "mockup": {
    "path": "mockups/base/{page}.html",
    "navigation": {
      "type": "css-class-toggle|route|hash",
      "selector": ".page",
      "activeClass": "active"
    }
  },
  "app": {
    "navigation": {
      "type": "click-button|route|sidebar",
      "selector": "nav button",
      "pageMap": { "today": "/", "report": "/report" }
    },
    "waitStrategy": {
      "type": "selector|networkidle|timeout",
      "selector": "[data-ready]",
      "timeout": 3000
    }
  },
  "apiMock": {
    "type": "tauri-invoke|fetch-intercept|msw|none",
    "responsesFile": ".design/mockup-diff/mock-responses.json"
  },
  "pages": ["today", "report", "settings"],
  "viewport": { "width": 1280, "height": 800 },
  "output": ".design/mockup-diff/screenshots"
}
```

## ✅ Tests

スキル定義ファイル（Markdown）のためコードテストは対象外。以下を手動検証：

- [ ] SKILL.md が Phase 0-5 の全フローを網羅している
- [ ] script-requirements.md が生成スクリプトの必須要件を明確に定義している
- [ ] commands/mockup-diff.md から SKILL.md が正しく呼び出される
- [ ] CLAUDE.md のマッピングが正確
- [ ] design-system-contract.md に mockup-diff の位置づけが明記されている
- [ ] plugin.json のバージョンが正しくバンプされている

## 🔒 Security

- 生成スクリプトは `Bash` ツール経由で実行されるため、ユーザーの許可ゲートが機能する
- mock-responses.json に機密データを含めないよう script-requirements.md で注意喚起

## 📊 Progress

| Step | Status |
|------|--------|
| 1. SKILL.md リライト | 🟢 |
| 2. scripts/compare-mockup-app.mjs 削除 | 🟢 |
| 3. references/script-requirements.md 作成 | 🟢 |
| 4. commands/mockup-diff.md 作成 | 🟢 |
| 5. CLAUDE.md マッピング追加 | 🟢 |
| 6. design-system-contract.md 追記 | 🟢 |
| 7. plugin.json バージョンバンプ | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
