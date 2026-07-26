# Design Lint Contract

The lint rule specification of the design-lint skill. Every rule references `.design/tokens.json` as the ground truth.

## Preconditions

The following files must exist before lint runs:

- `.design/tokens.json` — the ground truth for verification
- `.design/lint-config.json` — the lint settings (the defaults are used when omitted)

## lint-config.json

```json
{
  "include": ["src/**/*.tsx", "src/**/*.css", "src/**/*.jsx", "src/**/*.ts"],
  "exclude": ["node_modules/**", ".design/**", "*.test.*", "*.spec.*"],
  "rules": {
    "DL001": "error",
    "DL002": "error",
    "DL003": "warn",
    "DL004": "warn",
    "DL005": "warn",
    "DL006": "error"
  },
  "allowRawValues": {
    "colors": ["transparent", "inherit", "currentColor", "white", "black"],
    "spacing": [0, "auto"],
    "borderRadius": [0, "50%", "9999px"]
  }
}
```

## Phase 1: Token Compliance rules (DL001-DL006)

### DL001: hardcoded color codes

**What it detects:** CSS/JSX using `#XXXXXX`, `#XXX`, `rgb()`, `rgba()`, `hsl()`, or `hsla()` with a color that is not defined in the tokens.

**How it detects:**
1. Extract the following patterns from the file with regular expressions:
   - `#[0-9a-fA-F]{3,8}` — hex colors
   - `rgba?\([^)]+\)` — rgb/rgba
   - `hsla?\([^)]+\)` — hsl/hsla
2. Build the allow list from every value of the `colors` object in tokens.json
3. Add the values of `allowRawValues.colors` to the allow list as well
4. If an extracted value is not in the allow list → violation

**Exclusions:**
- Use through a CSS custom property (`var(--color-*)`) is fine
- Values inside comments are ignored
- Values listed explicitly in `allowRawValues.colors` (`transparent`, etc.) are fine

**Report example:**
```json
{
  "rule": "DL001",
  "severity": "error",
  "file": "src/components/Header.tsx",
  "line": 42,
  "column": 15,
  "value": "#FF6B6B",
  "message": "直書きカラーコード '#FF6B6B' を検出。tokens.json に定義された色または CSS 変数 var(--color-*) を使用してください。",
  "suggestion": "最も近いトークン: colors.error (#DC2626)"
}
```

### DL002: hardcoded fonts

**What it detects:** a `font-family` using a font not defined in `typography.headingFont`, `typography.bodyFont`, or `typography.codeFont` of tokens.json.

**How it detects:**
1. Extract `font-family:` declarations with a regular expression
2. Build the allow list from the typography font names in tokens.json
3. System font stacks (`-apple-system`, `BlinkMacSystemFont`, `system-ui`, etc.) are allowed
4. Fallbacks (`sans-serif`, `serif`, `monospace`) are allowed
5. If any other font name appears → violation

### DL003: hardcoded spacing

**What it detects:** `padding`, `margin`, `gap`, `top`, `right`, `bottom`, or `left` using a px value not defined in `spacing.scale` of tokens.json.

**How it detects:**
1. Extract the values of spacing-related CSS properties with a regular expression
2. Convert px values to numbers
3. Match them against the `spacing.scale` array of tokens.json
4. The values of `allowRawValues.spacing` (`0`, `auto`) are allowed
5. A value not in the scale → violation

**Exclusions:**
- The `%`, `vw`, `vh`, `em`, and `rem` units are allowed as being outside the spacing scale
- Shorthands (`padding: 12px 24px`) are verified value by value

### DL004: hardcoded border-radius

**What it detects:** a `border-radius` using a value not defined in `components.{type}.borderRadius` of tokens.json.

**How it detects:**
1. Extract the value of each `border-radius` declaration
2. Build the allow list from every borderRadius value in tokens.json
3. The values of `allowRawValues.borderRadius` (`0`, `50%`, `9999px`) are allowed
4. A value not in the list → violation

### DL005: hardcoded shadow

**What it detects:** a `box-shadow` using a shadow value not defined in `depth.*.shadow` of tokens.json.

**How it detects:**
1. Extract the value of each `box-shadow` declaration
2. Build the allow list from the shadow values of every depth level in tokens.json
3. `none` is allowed
4. A value not in the list → violation

### DL006: CSS variable not used

**What it detects:** a hardcoded value used even though a corresponding CSS variable exists in tokens.json.
A rule above DL001-005: even when the hardcoded value **matches** a value defined in the tokens, it is a violation unless it goes through the CSS variable.

**How it detects:**
1. Map every value in tokens.json to a CSS variable name (following the naming rules of design-system-contract)
2. Detect the places where a token's value is used hardcoded in the source
3. The same value used without going through `var(--*)` → violation

**Report example:**
```json
{
  "rule": "DL006",
  "severity": "error",
  "file": "src/components/Button.tsx",
  "line": 15,
  "value": "#2563EB",
  "message": "トークン値 '#2563EB' が直書きされています。var(--color-primary) を使用してください。"
}
```

## The lint execution flow

```
1. Read .design/tokens.json
2. Read .design/lint-config.json (defaults if absent)
3. Get the list of files matching the include patterns by glob
4. Remove the exclude patterns
5. Read each file and apply every enabled rule
6. Collect the violations
7. Emit the report:
   - summary: {total} violations ({errors} errors, {warnings} warnings)
   - details: the violation list by file and by rule
8. Decide the exit code:
   - 1 or more errors → FAIL
   - warnings only → PASS (with warnings)
   - no violations → PASS
```

## Report format

### Summary

```
🔍 Design Lint Results
━━━━━━━━━━━━━━━━━━━━━━━
Files scanned: 24
Violations: 7 (5 errors, 2 warnings)

❌ DL001 (color): 3 violations
❌ DL006 (css-var): 2 violations
⚠️  DL003 (spacing): 2 violations

Result: FAIL (5 errors)
```

### Details (JSON)

```json
{
  "summary": {
    "filesScanned": 24,
    "totalViolations": 7,
    "errors": 5,
    "warnings": 2,
    "result": "FAIL"
  },
  "violations": [
    {
      "rule": "DL001",
      "severity": "error",
      "file": "src/components/Header.tsx",
      "line": 42,
      "value": "#FF6B6B",
      "message": "...",
      "suggestion": "..."
    }
  ]
}
```

## Phase 2: Component Compliance rules (DL101-DL103)

Enabled only when `.design/component-catalog.json` exists. Skip this whole category when it does not.

### DL101: unregistered component

**What it detects:** use of a custom component not defined in catalog.json.

**How it detects:**
1. Extract PascalCase element names from JSX files with a regular expression: `/<([A-Z][a-zA-Z0-9]+)/g`
2. Build the allow list from the `components[].name` list of catalog.json
3. Exclude the following (not violations):
   - Native HTML elements: `div`, `span`, `p`, `a`, `button`, `input`, `form`, `img`, `h1`-`h6`, `ul`, `ol`, `li`, `table`, `tr`, `td`, `th`, `thead`, `tbody`, `section`, `article`, `header`, `footer`, `nav`, `main`, `aside`, `label`, `select`, `textarea`, `option`, `svg`, `path`, `circle`, `rect`, `line`
   - React built-ins: `Fragment`, `Suspense`, `StrictMode`, `Profiler`, `Provider`, `Consumer`
   - Preact built-ins: `Fragment`
   - Test utilities: components inside test files are out of scope (controlled by exclude in lint-config)

**severity:** `error`

### DL102: unregistered variant

**What it detects:** a variant value passed as a prop to a catalog component that is not defined in catalog.json.

**How it detects:**
1. For each catalog component name `{Name}`:
   - Extract the variant value with `<{Name}\s+[^>]*variant\s*=\s*["']([^"']+)["']`
   - Extract it with `<{Name}\s+[^>]*variant\s*=\s*\{["']([^"']+)["']\}` as well (a JSX expression)
2. Build the allow list from `components[name={Name}].variants[].name` of catalog.json
3. A variant value not in the allow list → violation

**severity:** `error`

### DL103: direct style override

**What it detects:** overriding a token-governed property with an inline style on a catalog component.

**How it detects:**
1. For each catalog component name `{Name}`:
   - Extract the inline style with `<{Name}\s+[^>]*style\s*=\s*\{\{([^}]+)\}\}`
   - Extract it with `<{Name}\s+[^>]*style\s*=\s*\{([^}]+)\}` as well
2. Parse the CSS properties inside the inline style
3. If any of the following token-governed properties appear → violation:
   - `color`, `backgroundColor`, `background`
   - `fontFamily`, `fontSize`, `fontWeight`
   - `padding`, `margin`, `gap` (spacing)
   - `borderRadius`
   - `boxShadow`
   - `border`, `borderColor`
4. The following layout properties are allowed (not violations):
   - `display`, `position`, `top`, `left`, `right`, `bottom`
   - `width`, `height`, `maxWidth`, `minWidth`, `maxHeight`, `minHeight`
   - `flex`, `flexDirection`, `flexGrow`, `flexShrink`, `flexBasis`
   - `gridColumn`, `gridRow`, `gridArea`
   - `overflow`, `zIndex`, `visibility`, `transform`
   - `textAlign`, `verticalAlign`

**severity:** `warn` (a warning level, because forbidding it outright removes all flexibility)

## Phase 3: Page/Layout Compliance rules (DL201-DL204)

Enabled only when `.design/pages/` and `.design/layout-rules.json` exist.

### DL201: page with no page-def

**What it detects:** creating a page that has no definition in `.design/pages/`.

**How it detects:**
1. Extract the page list from the routing definitions in the source (React Router's `<Route>`, Next.js's `pages/` directory, etc.)
2. Match them against the JSON filenames in `.design/pages/`
3. A page with no page-def → violation

**Note:** because it detects framework-specific routing patterns, this is approximate, regex-based detection.

**severity:** `warn` (it nudges you to create the page-def first when adding a new page)

### DL202: allowedComponents violation

**What it detects:** use of a component not included in the page definition's `allowedComponents`.

**How it detects:**
1. Extract the components used in each page file (identified from the routing, or by filename match)
2. Match them against `allowedComponents` of the corresponding page-def
3. `allowedComponents` is defined, yet a component outside the list is used → violation

**severity:** `error`

### DL203: section order violation

**What it detects:** sections placed in an order different from `sections[].order` of the page-def.

**How it detects:**
1. Get the order of appearance of the section IDs in the page file (extracted from the `className` or `id` attributes)
2. Compare it with the page-def's sections sorted by `order`
3. A differing order → violation

**severity:** `warn`

### DL204: layout rule violation

**What it detects:** violating a rule with `enforcement: "lint"` defined in `constraints` of `layout-rules.json`.

**How it detects:**
1. Extract the rules with `enforcement: "lint"` from the constraints of layout-rules.json
2. Apply each rule's `checkPattern` (a regular expression) to the source
3. Detect the violations matching the pattern

**Example:**
```json
{
  "id": "LC003",
  "rule": "grid-template-columns column count <= 3",
  "enforcement": "lint",
  "checkPattern": "grid-template-columns\\s*:.*\\b(repeat\\(([4-9]|\\d{2,})|.*\\s+.*\\s+.*\\s+)"
}
```

**severity:** follows the `severity` field of the constraint (default: `warn`)
