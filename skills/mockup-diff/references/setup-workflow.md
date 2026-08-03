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
header: "Confirm config"
question: "The comparison script will be generated with the settings below. Is anything wrong?"
options:
  - "These settings are fine"
  - "Something needs changing"
```

Example of how to display the settings:
```
📋 Mockup Diff settings
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
[references/script-requirements.md](script-requirements.md).

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
✅ Mockup Diff setup complete!

📁 Generated files:
  .design/mockup-diff/config.json       — config file
  .design/mockup-diff/compare.mjs       — comparison script
  .design/mockup-diff/mock-responses.json — API mock data (when applicable)

Next step:
  Continue straight to Phase 1 and run the screenshot comparison.
```
