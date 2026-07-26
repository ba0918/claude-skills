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

# Mockup Diff — Detect and Fix Visual Differences Between Mockup and App

## Boundary with design-validate

| | design-validate | mockup-diff |
|--|----------------|-------------|
| **Compared** | baseline screenshots vs implementation code | mockup HTML vs the running app |
| **Detects** | hardcoded tokens, use of undefined tokens, pixel diff | spacing drift, broken fonts, layout bugs in dynamic states |
| **Role** | verification of mechanical rule compliance | the last mile of implementation quality |
| **In the pipeline** | after design-generate | after porting into the app |

```
design-guide → design-scaffold → design-generate
         ↓                              ↓
    [HUMAN APPROVAL]               mockups/base/*.html
         ↓                              ↓
    baseline fixed              implemented in app
         ↓                              ↓
    design-validate            mockup-diff ← ★
```

## Workflow Overview

```
Phase 0: SETUP    — investigate the project + generate the compare script (first run only)
Phase 1: CAPTURE  — screenshot both the mockup and the app with the generated script
Phase 2: COMPARE  — put the screenshots side by side and compare visually
Phase 3: ANALYZE  — pin down the cause of CSS / component / font differences
Phase 4: FIX      — fix the code + update tests
Phase 5: VERIFY   — re-screenshot and confirm the differences are gone
```

---

## Phase 0: SETUP (first run or when settings change)

Run this when `.design/mockup-diff/config.json` does not exist, or when `$ARGUMENTS` contains `setup`.
If config.json already exists and no setup instruction was given, skip to Phase 1.

### Step 1: Project Investigation

Auto-detect the following:

#### 1-1. Framework and build tool detection

Investigate with file search and pattern search:

| File | What to detect |
|---------|---------|
| `package.json` | framework from dependencies/devDependencies (React, Vue, Svelte, Next.js, ...) |
| `Cargo.toml` → `tauri` | a Tauri app |
| `vite.config.*` | uses Vite |
| `next.config.*` | uses Next.js |
| `webpack.config.*` | uses webpack |

#### 1-2. Identify how to start the dev server

Identify the dev server start command from the `scripts` section of `package.json`:
- Check script names such as `dev`, `start`, `serve`
- Infer the port number (Vite: 5173, Next.js: 3000, CRA: 3000, ...)

#### 1-3. Analyze the DOM structure of the mockup HTML

Read the mockup file and extract:
- the page-switching mechanism (CSS class toggle, hash routing, separate HTML files, ...)
- selectors for navigation elements
- selector / ID patterns for page containers

#### 1-4. Navigation structure on the app side

Investigate the app source code with pattern search:
- the routing approach (React Router, file-based routing, ...)
- selectors for navigation components
- how page transitions happen (link buttons, tabs, ...)

#### 1-5. Identify API mocking requirements

| Framework | Mocking approach |
|-------------|----------|
| Tauri | `tauri-invoke` — inject `window.__TAURI_INTERNALS__` |
| Next.js (API routes) | `fetch-intercept` — Playwright's `page.route()` |
| MSW already installed | `msw` — reuse the project's existing MSW setup |
| Static pages / SSG | `none` — no mocking needed |

### Step 2: Generate config.json

Draft config.json from the investigation results and confirm it with the user.

```
header: "config 確認"
question: "以下の設定で比較スクリプトを生成します。修正が必要な箇所はありますか？"
options:
  - "この設定で OK"
  - "修正したい箇所がある"
```

Example of how to display the settings:
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

After confirmation, save it to `.design/mockup-diff/config.json`.

**config.json schema:**

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

### Step 3: Generate the compare script

Generate the project-specific compare script in **strict conformance** with the requirements in
[references/script-requirements.md](references/script-requirements.md).

Output: `.design/mockup-diff/compare.mjs`

**Generation principles:**

1. Satisfy every mandatory requirement in script-requirements.md
2. Do not hardcode config.json values — read config.json and use them dynamically
3. Pick the API mock injection pattern matching `apiMock.type` from script-requirements.md
4. When `apiMock.type` is `tauri-invoke` or `fetch-intercept`, load the mock responses from `apiMock.responsesFile`
5. Implement error handling and cleanup exactly as script-requirements.md requires
6. Resolve Playwright with `createRequire` and load it dynamically from the project's `node_modules`

### Step 4: Generate the API mock response file (when applicable)

When `apiMock.type` is anything other than `none`:

1. Detect API calls (invoke, fetch, ...) in the app source code with pattern search
2. Generate a deterministic dummy response for each API endpoint
3. Save them to `.design/mockup-diff/mock-responses.json`
4. Confirm the response contents with the user

### Step 5: Smoke check (dry run)

```bash
cd <project-root>
node .design/mockup-diff/compare.mjs --help
```

Confirm the help text is displayed correctly.
If an error appears, investigate the cause and fix the script.

### SETUP completion message

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

### Preconditions

1. Confirm `.design/mockup-diff/config.json` exists
   - If missing, tell the user 「Phase 0: SETUP を先に実行してください」
2. Confirm `.design/mockup-diff/compare.mjs` exists
   - Same as above if missing

### Run the script

```bash
cd <project-root>
node .design/mockup-diff/compare.mjs
```

Optionally run only specific pages:
```bash
node .design/mockup-diff/compare.mjs --pages today,report
```

### Check the result

Check the script's exit code:
- `0`: success → go to Phase 2
- non-zero: read the error message, investigate the cause, and fix it

---

## Phase 2: COMPARE

Load the screenshot images and review them side by side. Cover every page, using `output` and `pages` from config.json:

```
{output}/mockup-{page}.png
{output}/app-{page}.png
```

**Do not move on until every page has been reviewed.**

For each page, observe:
- how well the overall layout agrees
- differences in color, font, and spacing
- differences in component display state
- obvious layout breakage

---

## Phase 3: ANALYZE

Classify the differences into the categories below and report them to the user.

### Visual bugs (to be fixed)

| Category | Example |
|---------|-----|
| **Color** | the status dot has the wrong color |
| **Spacing** | padding/margin does not match the mockup |
| **Font** | missing font-weight causing faux bold, size mismatch |
| **Animation** | missing CSS animation/transition |
| **Interaction** | missing hover / disabled / focus styles |
| **Layout** | mismatched flex / grid / width / position |
| **Responsive** | breakage at breakpoints |

### Not to be fixed

- **Data differences**: differing mock data values (names, numbers, etc. are just dummy-data differences)
- **Known issues**: unimplemented features, intentional differences
- **Rendering engine differences**: slight differences between CDN fonts and self-hosted woff2 (acceptable)

### Report format

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

For each difference:

1. Compare the mockup CSS/HTML with the corresponding app code and pin down the cause
2. Fix the CSS / TSX / Vue / font files, etc.
3. Update the affected tests (unit / E2E / visual)
4. Check for regressions with the project's test command

### Common difference patterns

| Pattern | How to fix |
|---------|---------|
| padding/margin mismatch | Match the CSS values to the mockup. Use the values defined in tokens.json |
| missing font-weight | Add the woff2 + an @font-face declaration |
| missing conditional CSS class | Toggle className/class dynamically in TSX/Vue |
| animation not implemented | Add @keyframes + the animation property |
| missing hover/disabled | Add pseudo-class selectors |
| broken flex/grid | Adjust the layout properties |

---

## Phase 5: VERIFY

1. Run the script again, following the same steps as Phase 1
2. Load the new screenshots and the mockup images and compare again
3. Confirm every must-fix difference is resolved
4. Report the result to the user

```
✅ 差分検証完了！

修正した差分:
  - [スペーシング] .header top-padding: 16px → 24px ✅
  - [フォント] heading font-weight: 400 → 600 ✅

残存する許容差分:
  - [データ] Provider 名の違い（モックデータ差）
```

If differences remain, go back to Phase 3 and fix them.

---

## File Structure

Files generated in the target project:

```
.design/mockup-diff/
├── config.json             # project-specific settings
├── compare.mjs             # the generated compare script
├── mock-responses.json     # API mock responses (when applicable)
└── screenshots/            # screenshot output
    ├── mockup-{page}.png
    ├── app-{page}.png
    └── comparison.html
```

## Cautions

- Rendering differences between Playwright (Chromium) and the Tauri WebView / individual browsers cannot be detected by this script. Comparison is limited to Playwright vs Playwright
- Slight differences between CDN fonts (mockup) and self-hosted woff2 (app) are acceptable
- If a dev server is already running in another process, the script fails with a port-in-use error. Stop it beforehand, or specify another port with `--port`
- Whether to add `config.json` and `compare.mjs` to `.gitignore` is left to the project (committing is recommended when sharing with a team)

## References

- **Script requirements:** [references/script-requirements.md](references/script-requirements.md)
- **Shared contract:** [shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
