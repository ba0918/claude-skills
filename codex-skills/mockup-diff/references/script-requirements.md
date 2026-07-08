# Compare Script Requirements

Phase 0: SETUP で LLM が生成する比較スクリプト（`.design/mockup-diff/compare.mjs`）が満たすべき要件。

## 必須要件

### 1. ランタイム・依存

- **Node.js ESM** (`#!/usr/bin/env node` + `.mjs` 拡張子)
- **Playwright** (`chromium` のみ) をスクリーンショット取得に使用する
- Playwright はターゲットプロジェクトの `node_modules` から解決する
  - `import { createRequire } from "module"` で動的に resolve し、スクリプトがどこから実行されてもプロジェクトの Playwright を使えるようにする
  - **プロジェクトに Playwright がない場合は明確なエラーメッセージを出して終了する**

### 2. CLI インターフェース

必須フラグ:

| フラグ | 説明 |
|--------|------|
| `--config` | `.design/mockup-diff/config.json` のパス（デフォルト: `<project-root>/.design/mockup-diff/config.json`） |

オプションフラグ:

| フラグ | 説明 | デフォルト |
|--------|------|-----------|
| `--pages` | カンマ区切りのページ名（config.json の pages を上書き） | config.json の値 |
| `--viewport` | `幅x高さ` | config.json の値 |
| `--output` | スクリーンショット出力ディレクトリ | config.json の値 |
| `--port` | Dev server ポート番号（config.json の devServer.port を上書き） | config.json の値 |
| `--help` | ヘルプ表示 | — |

### 3. スクリーンショット取得

#### モックアップ側

1. `file://` プロトコルでモックアップ HTML を開く
2. `document.fonts.ready` を待つ
3. ページ切替がある場合は config.json の `mockup.navigation` に従う
4. 各ページのスクリーンショットを `{output}/mockup-{page}.png` に保存

#### アプリ側

1. config.json の `devServer.command` で dev server を起動する
2. **ポート疎通チェック**（`fetch` リトライ、最大30秒）で起動完了を待つ
   - `devServer.readyPattern` による stdout 検出は**フォールバック**として使用
   - タイムアウト時は明確なエラーメッセージで終了する
3. config.json の `apiMock` に従って API モックを注入する
4. config.json の `app.navigation` に従ってページ遷移する
5. config.json の `app.waitStrategy` に従ってコンテンツ描画完了を待つ
6. 各ページのスクリーンショットを `{output}/app-{page}.png` に保存

### 4. 比較 HTML 生成

- `{output}/comparison.html` にモックアップとアプリのスクショを並べた HTML を生成する
- 各ページについて左右に並べて表示
- CSS はインラインで完結（外部依存なし）

### 5. エラーハンドリング

以下の全ケースで**明確なエラーメッセージ**を出して非ゼロ exit する:

| ケース | メッセージ例 |
|--------|-------------|
| config.json が見つからない | `ERROR: Config not found: {path}. Run mockup-diff setup first.` |
| Playwright 未インストール | `ERROR: Playwright not found in {project}/node_modules. Run: npx playwright install chromium` |
| モックアップファイルが存在しない | `ERROR: Mockup file not found: {path}` |
| Dev server 起動タイムアウト | `ERROR: Dev server failed to start within 30s on port {port}` |
| Dev server ポート使用中 | `ERROR: Port {port} already in use` |
| スクリーンショット取得失敗 | `ERROR: Failed to capture screenshot for page '{page}': {reason}` |

### 6. クリーンアップ

- **正常終了・異常終了の両方**で以下をクリーンアップする:
  - 起動した dev server プロセスを `SIGTERM` で停止
  - Playwright ブラウザインスタンスを close
- `process.on("SIGINT")` / `process.on("SIGTERM")` でシグナルハンドリング

### 7. 出力構造

```
{output}/
├── mockup-{page1}.png    # モックアップのスクリーンショット
├── mockup-{page2}.png
├── app-{page1}.png       # アプリのスクリーンショット
├── app-{page2}.png
└── comparison.html       # 並べて比較する HTML
```

## API モック注入パターン

config.json の `apiMock.type` に応じた注入方法のガイドライン:

### `tauri-invoke`

```javascript
await page.addInitScript((mockData) => {
  let callbackId = 0;
  window.__TAURI_INTERNALS__ = {
    invoke: (cmd, args) => {
      if (cmd === "plugin:event|listen") return Promise.resolve(callbackId++);
      if (cmd === "plugin:event|unlisten") return Promise.resolve();
      if (cmd in mockData) return Promise.resolve(mockData[cmd]);
      console.warn(`[tauri-mock] unhandled: ${cmd}`, args);
      return Promise.resolve(null);
    },
    transformCallback: (cb) => { const id = callbackId++; return id; },
    convertFileSrc: (p) => p,
  };
}, mockData);
```

### `fetch-intercept`

```javascript
await page.route("**/api/**", (route) => {
  const url = new URL(route.request().url());
  const endpoint = url.pathname.replace(/^\/api\//, "");
  if (endpoint in mockData) {
    route.fulfill({ json: mockData[endpoint] });
  } else {
    route.continue();
  }
});
```

### `msw`

MSW がプロジェクトに導入済みの場合、既存の MSW ハンドラを活用する。
スクリプト内で独自に MSW をセットアップするのではなく、プロジェクトの MSW 設定を利用する方針。

### `none`

API モック不要（静的ページ、SSG 等）。何も注入しない。

## セキュリティ注意事項

- `mock-responses.json` に本番の API キー、トークン、個人情報を含めないこと
- 生成スクリプトは `shell` ツール経由でユーザーの許可ゲートを通過して実行される
- dev server の起動コマンドは config.json から読み取るため、意図しないコマンドが実行されないようユーザーが config.json の内容を確認すること

## 非要件（スクリプトに含めないもの）

- ピクセルレベルの自動差分検出（差分分析は LLM が shell でスクショを確認して行う）
- 自動修正機能（修正は LLM が Phase 4 で行う）
- レポート生成（分析レポートは LLM が Phase 3 で生成する）
