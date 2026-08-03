---
name: mockup-diff
description: A workflow that captures screenshots of an approved mockup HTML and of the real app automatically with Playwright, compares them side by side, identifies the differences, and fixes the code. On the first run, SETUP investigates the project automatically and generates a tailor-made comparison script. Use when the user says "compare with the mockup", "mockup diff", "visual difference", "design difference check", "the mock and the implementation differ", or "compare the screenshots". Use it in projects that have a DESIGN.md and mockup HTML.
---

# Mockup Diff — Detect and Fix Visual Differences Between Mockup and App

## Boundary with design-validate

See the [division-of-labor table in design-system-contract.md](../shared/references/design-system-contract.md#division-of-labor-with-design-validate).

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

## Phase 0: SETUP — routing

When `.design/mockup-diff/config.json` exists and `$ARGUMENTS` does not contain `setup`, start
from Phase 1 below — do not read the setup file. Otherwise (first run, or `setup` given), read
[references/setup-workflow.md](references/setup-workflow.md) in full first, and in its Step 3
also read [references/script-requirements.md](references/script-requirements.md) — load only
the file the current step names.


---

## Phase 1: CAPTURE

### Preconditions

1. Confirm `.design/mockup-diff/config.json` exists
   - If missing, tell the user "Run Phase 0: SETUP first."
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
📊 Difference analysis report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## {page} page

### 🔴 Must fix
1. [Spacing] .header top-padding is 24px (mockup) vs 16px (app)
   Likely cause: mistaken expansion of the CSS shorthand
   Affected file: src/components/Header.css

### 🟡 Needs confirmation
1. [Font] heading font-weight is 600 (mockup) vs 400 (app)
   Likely cause: weight 600 not bundled in the woff2

### ⚪ Acceptable
1. [Data] the provider name differs (a difference in the mock data)
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
✅ Difference verification complete!

Differences fixed:
  - [Spacing] .header top-padding: 16px → 24px ✅
  - [Font] heading font-weight: 400 → 600 ✅

Remaining acceptable differences:
  - [Data] the provider name differs (a mock data difference)
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
