---
name: mockup-diff
description: >
  承認済みモックアップ HTML と実アプリのスクリーンショットを Playwright で自動取得し、
  並べて比較 → 差分を特定 → コードを修正する一連のワークフロー。
  初回は SETUP でプロジェクトを自動調査し、テーラーメイドの比較スクリプトを生成する。
  「モックアップと比較」「mockup diff」「見た目の差分」「デザイン差分チェック」
  「モックと実装が違う」「スクショ比較」で起動。
  DESIGN.md / mockup HTML を持つプロジェクトで使用する。
---

# Mockup Diff (Codex Edition)

承認済みモックアップ HTML と実行中アプリのスクリーンショットを Playwright で自動取得し、
並べて比較 → 差分を特定 → コードを修正する。
初回は Phase 0: SETUP でプロジェクトを自動調査し、テーラーメイドの比較スクリプトを生成する。

## Codex CLI ツールの使い分け

- **apply_patch** — 比較スクリプト（`.design/mockup-diff/compare.mjs`）・config.json・mock-responses.json の生成、および Phase 4 での実装コード（CSS / TSX / Vue / フォント宣言等）修正。ファイルへの書き込みはすべて apply_patch で行う（shell リダイレクトでのファイル書き込みは禁止）
- **shell** — プロジェクト調査（`rg` / `find` / `cat`）、生成した比較スクリプトの実行（`node .design/mockup-diff/compare.mjs ...`）、Playwright によるスクショ取得の起動、スクショの比較確認、テストコマンドによる regression 確認。**スクショ取得・比較は playwright/node 前提。プロジェクトに未導入なら該当ステップは実行できない**
- **会話ターンでの確認** — config.json ドラフトの確認・API モックレスポンス内容の確認など、ユーザー確認を伴う分岐は会話ターンで平文の質問（選択肢は列挙して番号/短文で回答を促す）として尋ねる。確認が取れない headless 文脈では確認を求めず、調査結果のドラフトをそのまま採用して先へ進む

## design-validate との棲み分け

| | design-validate | mockup-diff |
|--|----------------|-------------|
| **比較対象** | baseline スクショ vs 実装コード | モックアップ HTML vs 実行中アプリ |
| **検出するもの** | トークン直書き、未定義トークン使用、pixel diff | spacing ズレ、フォント崩れ、動的状態のレイアウトバグ |
| **位置づけ** | 機械的ルール準拠の検証 | 実装品質のラストワンマイル |
| **パイプライン上** | design-generate の後 | アプリへの落とし込み後 |

```
design-guide → design-scaffold → design-generate
         ↓                              ↓
    [HUMAN APPROVAL]               mockups/base/*.html
         ↓                              ↓
    baseline 確定              アプリに実装
         ↓                              ↓
    design-validate            mockup-diff ← ★
```

## ワークフロー概要

```
Phase 0: SETUP    — プロジェクト調査 + 比較スクリプト自動生成（初回のみ）
Phase 1: CAPTURE  — 生成スクリプトでモック + アプリの両方をスクショ撮影
Phase 2: COMPARE  — スクショを shell で並べて比較
Phase 3: ANALYZE  — CSS / コンポーネント / フォントの差分原因を特定
Phase 4: FIX      — コード修正 + テスト更新
Phase 5: VERIFY   — 再スクショで差分解消を確認
```

---

## Phase 0: SETUP（初回 or 設定変更時）

`.design/mockup-diff/config.json` が存在しない場合、または `$ARGUMENTS` に `setup` が含まれる場合に実行する。
既に config.json が存在し setup 指示もない場合は Phase 1 にスキップする。

### Step 1: プロジェクト調査

以下を自動検出する:

#### 1-1. フレームワーク・ビルドツール検出

shell（`rg` / `find`）で以下を調査:

| ファイル | 検出対象 |
|---------|---------|
| `package.json` | dependencies/devDependencies からフレームワーク（React, Vue, Svelte, Next.js 等） |
| `Cargo.toml` → `tauri` | Tauri アプリ |
| `vite.config.*` | Vite 使用 |
| `next.config.*` | Next.js 使用 |
| `webpack.config.*` | webpack 使用 |

#### 1-2. Dev server 起動方法の特定

`package.json` の `scripts` セクションから dev server 起動コマンドを特定:
- `dev`, `start`, `serve` 等のスクリプト名を確認
- ポート番号を推定（Vite: 5173, Next.js: 3000, CRA: 3000 等）

#### 1-3. モックアップ HTML の DOM 構造解析

モックアップファイルを shell（`cat`）で読み込み:
- ページ切替の仕組み（CSS class toggle, hash routing, 個別 HTML ファイル等）
- ナビゲーション要素のセレクタ
- ページコンテナのセレクタ・ID パターン

#### 1-4. アプリ側のナビゲーション構造

アプリのソースコードを shell（`rg`）で調査:
- ルーティング方法（React Router, file-based routing 等）
- ナビゲーションコンポーネントのセレクタ
- ページ遷移の方法（リンクボタン、タブ等）

#### 1-5. API モック要件の特定

| フレームワーク | モック方式 |
|-------------|----------|
| Tauri | `tauri-invoke` — `window.__TAURI_INTERNALS__` を注入 |
| Next.js (API routes) | `fetch-intercept` — Playwright の `page.route()` |
| MSW 導入済み | `msw` — プロジェクト既存の MSW 設定を活用 |
| 静的ページ / SSG | `none` — モック不要 |

### Step 2: config.json 生成

調査結果を基に config.json のドラフトを作成し、会話ターンでユーザーに確認する。

```
「以下の設定で比較スクリプトを生成します。修正が必要な箇所はありますか？」
  1. この設定で OK
  2. 修正したい箇所がある（該当箇所を教えてください）
```

設定の表示例:
```
📋 Mockup Diff 設定
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Framework:   Tauri + React (Vite)
Dev Server:  pnpm dev (port 5173)
Pages:       today, report, settings
Viewport:    1280x800
API Mock:    tauri-invoke
Mockup:      mockups/base/{page}.html
Output:      .design/mockup-diff/screenshots
```

確認後（headless 文脈では確認を省略し）、`.design/mockup-diff/config.json` を apply_patch で書き込む。

**config.json のスキーマ:**

```json
{
  "framework": "tauri|nextjs|vite|cra|static|...",
  "devServer": {
    "command": "pnpm dev",
    "port": 5173,
    "readyPattern": "Local:",
    "startupTimeout": 30000
  },
  "mockup": {
    "path": "mockups/base/{page}.html",
    "navigation": {
      "type": "css-class-toggle|route|hash|separate-files",
      "selector": ".page",
      "activeClass": "active",
      "navSelector": "nav button"
    }
  },
  "app": {
    "navigation": {
      "type": "click-button|route|sidebar|tab",
      "selector": "nav button",
      "pageMap": {}
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
  "pages": [],
  "viewport": { "width": 1280, "height": 800 },
  "output": ".design/mockup-diff/screenshots"
}
```

### Step 3: 比較スクリプト生成

[references/script-requirements.md](references/script-requirements.md) の要件に**厳密に準拠**して、
プロジェクト固有の比較スクリプトを apply_patch で生成する。

出力先: `.design/mockup-diff/compare.mjs`

**生成時の原則:**

1. script-requirements.md の全必須要件を満たすこと
2. config.json の値をハードコードするのではなく、config.json を読み込んで動的に使用すること
3. `apiMock.type` に応じた API モック注入パターンを script-requirements.md から選択すること
4. `apiMock.type` が `tauri-invoke` または `fetch-intercept` の場合、`apiMock.responsesFile` からモックレスポンスを読み込むこと
5. エラーハンドリング・クリーンアップを script-requirements.md の要件通りに実装すること
6. Playwright の解決に `createRequire` を使い、プロジェクトの `node_modules` から動的にロードすること

### Step 4: API モックレスポンスファイル生成（該当する場合）

`apiMock.type` が `none` 以外の場合:

1. アプリのソースコードから API コール（invoke, fetch 等）を shell（`rg`）で検出
2. 各 API エンドポイントに対する決定論的なダミーレスポンスを生成
3. `.design/mockup-diff/mock-responses.json` を apply_patch で書き込む
4. 会話ターンでレスポンスの内容を確認（headless 文脈では確認を省略）

### Step 5: 動作確認（dry run）

```bash
cd <project-root>
node .design/mockup-diff/compare.mjs --help
```

ヘルプが正常に表示されることを確認する。
エラーが出た場合は原因を調査し、スクリプトを修正する。

### SETUP 完了メッセージ

```
✅ Mockup Diff セットアップ完了！

📁 生成ファイル:
  .design/mockup-diff/config.json       — 設定ファイル
  .design/mockup-diff/compare.mjs       — 比較スクリプト
  .design/mockup-diff/mock-responses.json — API モックデータ（該当時）

次のステップ:
  このまま Phase 1 に進んでスクショ比較を実行するよ。
```

---

## Phase 1: CAPTURE

### 前提チェック

1. `.design/mockup-diff/config.json` の存在確認
   - なければ「Phase 0: SETUP を先に実行してください」と案内
2. `.design/mockup-diff/compare.mjs` の存在確認
   - なければ同上

### スクリプト実行

```bash
cd <project-root>
node .design/mockup-diff/compare.mjs
```

オプションで特定ページのみ実行:
```bash
node .design/mockup-diff/compare.mjs --pages today,report
```

### 実行結果の確認

スクリプトの exit code を確認:
- `0`: 正常終了 → Phase 2 へ
- 非ゼロ: エラーメッセージを確認し、原因を調査・修正

---

## Phase 2: COMPARE

shell でスクショを並べて確認する。config.json の `output` と `pages` を参照して全ページ分を確認する:

```
{output}/mockup-{page}.png
{output}/app-{page}.png
```

**全ページ分を確認するまで次に進まない。**

各ページについて以下を観察:
- 全体的なレイアウトの一致度
- 色・フォント・spacing の差異
- コンポーネントの表示状態の差異
- 明らかなレイアウト崩れ

---

## Phase 3: ANALYZE

差分を以下のカテゴリに分類してユーザーに報告する。

### 視覚バグ（修正対象）

| カテゴリ | 例 |
|---------|-----|
| **色** | ステータスドットの色が間違い |
| **スペーシング** | padding/margin がモックと不一致 |
| **フォント** | font-weight 欠損で faux bold、サイズ不一致 |
| **アニメーション** | CSS animation/transition の欠落 |
| **インタラクション** | hover / disabled / focus スタイル欠落 |
| **レイアウト** | flex / grid / 幅 / 位置の不一致 |
| **レスポンシブ** | ブレークポイントでの崩れ |

### 修正対象外

- **データ差分**: モックデータの値の違い（名前、数値等はダミーデータの差）
- **既知 issue**: 未実装機能、意図的な差異
- **レンダリングエンジン差**: CDN フォント vs self-hosted woff2 の微差（許容範囲）

### レポート形式

```
📊 差分分析レポート
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## {page} ページ

### 🔴 修正必須
1. [スペーシング] .header の top-padding が 24px（モック）vs 16px（アプリ）
   原因候補: CSS shorthand の展開ミス
   影響ファイル: src/components/Header.css

### 🟡 要確認
1. [フォント] heading の font-weight が 600（モック）vs 400（アプリ）
   原因候補: woff2 の weight 600 未組み込み

### ⚪ 許容
1. [データ] Provider 名が異なる（モックデータの差）
```

---

## Phase 4: FIX

差分ごとに:

1. モックアップの CSS/HTML とアプリの対応コードを比較し原因特定
2. CSS / TSX / Vue / フォントファイル等を apply_patch で修正
3. 影響を受けるテスト（unit / E2E / visual）を更新
4. プロジェクトのテストコマンドで regression 確認

### よくある差分パターン

| パターン | 修正方針 |
|---------|---------|
| padding/margin 不一致 | CSS 値をモックに合わせる。tokens.json 定義値を使用 |
| font-weight 欠損 | woff2 追加 + @font-face 宣言追加 |
| 条件付き CSS クラス欠落 | TSX/Vue で className/class を動的切替 |
| animation 未実装 | @keyframes + animation プロパティ追加 |
| hover/disabled 欠落 | 疑似クラスセレクタ追加 |
| flex/grid 崩れ | レイアウトプロパティを調整 |

---

## Phase 5: VERIFY

1. Phase 1 と同じ手順で再度スクリプト実行
2. shell で新しいスクショとモックを再比較
3. 全ての修正必須差分が解消されたことを確認
4. 結果をユーザーに報告

```
✅ 差分検証完了！

修正した差分:
  - [スペーシング] .header top-padding: 16px → 24px ✅
  - [フォント] heading font-weight: 400 → 600 ✅

残存する許容差分:
  - [データ] Provider 名の違い（モックデータ差）
```

差分が残っている場合は Phase 3 に戻り、追加修正を行う。

---

## ファイル構造

ターゲットプロジェクトに生成されるファイル:

```
.design/mockup-diff/
├── config.json             # プロジェクト固有の設定
├── compare.mjs             # 生成された比較スクリプト
├── mock-responses.json     # API モックレスポンス（該当時）
└── screenshots/            # スクリーンショット出力
    ├── mockup-{page}.png
    ├── app-{page}.png
    └── comparison.html
```

## 注意事項

- Playwright (Chromium) と Tauri WebView / 各ブラウザのレンダリング差は本スクリプトでは検出不可。Playwright 同士の比較に限定される
- CDN フォント（モック）vs self-hosted woff2（アプリ）の微差は許容範囲
- dev server が既に別プロセスで起動中の場合、スクリプトはポート使用中エラーを出す。事前に停止するか、`--port` で別ポートを指定する
- `config.json` や `compare.mjs` は `.gitignore` に追加するかはプロジェクトの判断に委ねる（チーム共有する場合はコミット推奨）

## References

- **スクリプト要件:** [references/script-requirements.md](references/script-requirements.md)
- **共有契約:** [shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
