## Mockup Workflow (schema-based mockup generation + Base Design approval)

**v2 design:** generate mockups from the `.design/` schema (tokens + catalog + page-schema),
then, after automatic lint verification, obtain human approval and **fix the baseline**.
This flow is the gateway that "concentrates human subjective judgement into a single point".

```
┌─────────────────────────────────────────────┐
│ The feedback loop (repeat until satisfied)  │
│                                             │
│  Step 1: pre-checks + is scaffold present   │
│  Step 2: create or confirm page definitions │
│  Step 3: generate mockups (schema-bound)    │
│  Step 4: automatic lint (DL001-204)         │
│  Step 5: present to the human + feedback    │
│    └── changes wanted → back to Step 2 or 3 │
│  Step 6: approval → fix the baseline ★      │
└─────────────────────────────────────────────┘
```

### Pre-checks

1. Check whether `DESIGN.md` exists at the project root
   - If not, state that DESIGN.md should be created with `/claude-skills:design-guide`, then stop
2. Check whether `.design/tokens.json` exists
   - If not, state that tokens should be generated with `/claude-skills:design-scaffold tokens`, then stop
3. Check whether `.design/component-catalog.json` exists
   - If not, state that the catalog should be generated with `/claude-skills:design-scaffold catalog`, then stop
4. Read every file:
   - `.design/tokens.json`
   - `.design/tokens.css`
   - `.design/component-catalog.json`
   - `.design/layout-rules.json` (if present)
   - `.design/pages/*.json` (if present)

### Step 1: decide what to mock up

Present choices to the user asking what to mock up:

header: "Target"

| Option | Description |
|--------|-------------|
| The component catalog | List every component × every variant from catalog.json |
| Page mockups | Complete pages built from the page definitions (if none exist, create them interactively) |
| The full set (recommended) | Component list + every page. Best suited to Base Design approval |

If the $ARGUMENTS after `mockup` carry a concrete instruction, that takes precedence.

### Step 2: create or confirm the page definitions

#### When `.design/pages/` holds no page definitions

Decide the page structure interactively by presenting choices to the user, and generate page definitions that conform to page-schema.json.

1. Present choices to the user asking for the project's main pages:
   ```
   header: "Main pages"
   question: "Choose the pages to build mockups for"
   multiSelect: true
   options:
     - "A landing page"
     - "A dashboard"
     - "A list page"
     - "A form page"
   ```
2. For each page:
   - Ask for the layout type (single-column / sidebar / dashboard-grid / split)
   - Propose a section structure and confirm it
   - Choose the components to use from catalog.json
3. Write to `.design/pages/{page-name}.json`

#### When `.design/pages/` holds page definitions

Show the existing page definitions and confirm whether to use them as they are or edit them.

### Step 3: mockup generation

#### Output format

Present choices to the user asking for the output format:

header: "Output format"

| Option | Description |
|--------|-------------|
| HTML + CSS (standalone) (recommended) | A single-file HTML that opens straight in a browser. Best suited to checking the Base Design |
| React components | JSX + CSS Modules. Can be dropped into the project |
| HTML + Tailwind | Uses Tailwind CSS classes. Runs standalone via a CDN load |

#### Absolute constraints (schema constraints)

Use **only values defined in tokens.json / catalog.json / page-schema** for the following:

- **Colour**: only `colors.*` from tokens.json, used through the CSS variable `var(--color-*)`
- **Font**: only `typography.*` from tokens.json, through `var(--font-*)`
- **Spacing**: only `spacing.scale` from tokens.json, through `var(--spacing-*)`
- **Corner radius**: only `components.*.borderRadius` from tokens.json, through `var(--radius-*)`
- **Shadow**: only `depth.*.shadow` from tokens.json, through `var(--shadow-*)`
- **Components**: only those defined in catalog.json
- **Page structure**: conforming to the section definitions in pages/*.json
- **Breakpoints**: only `responsive.breakpoints` from tokens.json

#### Where creative freedom applies

While holding strictly to the schema, the following are yours to shape:

- The content inside a section (text, dummy data, image placeholders)
- Animation and transitions (an area the schema does not define)
- Drawing on the positive patterns in [references/anti-patterns.md](anti-patterns.md)

#### Generation process

1. Load `.design/tokens.css` through a `<link>` or `<style>`
2. Load fonts through a Google Fonts `<link>` tag
3. Build the components' HTML/JSX from catalog.json
4. Compose the pages following the section definitions in pages/*.json
5. Responsive behaviour: follow responsive.breakpoints from tokens.json
6. Generate a **component catalog HTML**:
   - List every component × every variant × every state from catalog.json
   - In a form where each component's style can be checked visually

Output location:
```
mockups/base/
├── components.html       # the component catalog
├── {page-name}.html      # the mockup of each page
└── ...
```

### Step 4: automatic lint verification

Apply the design-lint logic to the generated mockups immediately:

1. Apply DL001-006 (Token Compliance) to every mockup file
2. Apply DL101-103 (Component Compliance)
3. Apply DL201-204 (Page/Layout Compliance)
4. Show a summary of the results:

```
🔍 Mockup Lint Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files: mockups/base/*.html
Token Compliance (DL001-006): ✅ 0 violations
Component Compliance (DL101-103): ✅ 0 violations
Page Compliance (DL201-204): ✅ 0 violations

Result: ALL PASS ✅
```

**When lint FAILs:** attempt an automatic fix, and report any violation that cannot be fixed as an error. Re-verify after fixing.
Do not proceed to Step 5 until lint passes completely.

### Step 5: present to the human and take feedback

Once lint passes, present the mockups to the human:

```
✅ Mockups generated! (lint: ALL PASS)

📁 Generated files:
  mockups/base/components.html — the component catalog
  mockups/base/{page-name}.html — {page name}

Open them in a browser and take a look.
```

Present choices to the user for approval or feedback:

```
header: "Base Design review"
options:
  - "Approve — fix this design as the baseline"
  - "Adjust the tokens — change colors, fonts, spacing, and so on"
  - "Adjust the components — change variants or styles"
  - "Change the page structure — add, remove, or reorder sections"
```

#### The feedback loop

| Kind of feedback | Loops back to | Operation |
|------------------|---------|------|
| Token adjustment | `/design-guide-update` → `/design-scaffold tokens` → Step 3 | Edit DESIGN.md → regenerate tokens → regenerate mockups |
| Component adjustment | `/design-scaffold catalog` → Step 3 | Edit the catalog → regenerate mockups |
| Page-structure change | Step 2 → Step 3 | Edit the page-schema → regenerate mockups |
| Fine-tuning (text, placement) | Step 3 | Edit the mockup directly → re-lint |

### Step 6: approval → fixing the baseline

Once approval is given:

1. **Take screenshots** (when Playwright is available):
   ```bash
   # take a screenshot of each mockup
   npx playwright screenshot mockups/base/components.html .design/baseline/screenshots/components.png
   ```
   If Playwright is not installed, state that screenshots should be saved manually into `.design/baseline/screenshots/`

2. **Generate approval.json**:
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
   Save it to `.design/baseline/approval.json`

3. **Completion message**:
   ```
   ✅ The Base Design is approved and the baseline is fixed!
   
   📁 Baseline:
     .design/baseline/approval.json — the approval metadata
     .design/baseline/screenshots/  — the baseline for visual tests
   
   From here on, UI generation is verified mechanically against this baseline.
   
   Next steps:
     `/claude-skills:design-generate` to generate the actual code
     `/claude-skills:design-validate` to run the verification gate
   
   ⚠️ If tokens.json or catalog.json is changed,
   the baseline must be re-approved (detected automatically by the hash mismatch).
   ```

