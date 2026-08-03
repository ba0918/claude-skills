### Step 1: Parse DESIGN.md

Read DESIGN.md and map each section onto an internal data structure.

**Parse rules (table → JSON mapping):**

| DESIGN.md section | Table columns | tokens.json path |
|---------------------|-------------|-----------------|
| Color Palette | Role, Value | `colors.{camelCase(role)}` |
| Dark Mode Overrides | Role, Value | `colorsDark.{camelCase(role)}` |
| Typography | Level, Font Family, Size, Weight, Line Height, Letter Spacing | `typography.scale.{camelCase(level)}` |
| Component Stylings > Buttons | Variant, Background, Text, Border, Border Radius, Padding | `components.buttons` |
| Component Stylings > Cards | (key-value pairs) | `components.cards` |
| Component Stylings > Inputs | (key-value pairs) | `components.inputs` |
| Component Stylings > Navigation | (key-value pairs) | `components.navigation` |
| Layout Principles | (key-value pairs) | `spacing.*` |
| Depth & Elevation | Level, Name, Usage, Shadow | `depth.{name}` |
| Responsive Behavior | Breakpoint, Name, Min Width, Behavior | `responsive.breakpoints.{breakpoint}` |

**Table parse procedure:**
1. Detect rows delimited by `|`
2. Identify the header row and the separator row (`|---|`)
3. Split data rows into columns and trim the surrounding whitespace
4. Associate column names with values

**Font Family parsing:**
- Extract font names from the Font Family column of the Typography table
- Also extract the stack including fallbacks from plain-text lines such as `- **Heading font:**`
- When both exist, prefer the plain-text line (it carries the fallback information)

### Step 2: Generate tokens.json

Convert the parsed data into JSON conforming to [tokens-schema.json](tokens-schema.json) — read the schema in full before generating.

1. Initialize `version` to `"1.0.0"`
2. Normalize every color value to 6-digit hex (`#FFF` → `#FFFFFF`)
3. Set `fontKey` on each Typography scale level (uses the Heading font → `"headingFont"`, Body → `"bodyFont"`, Code → `"codeFont"`)
4. Build the spacing scale as a sorted array
5. Create the `.design/` directory (`mkdir -p .design`)
6. Save to `.design/tokens.json`

**Self-verification after generation:**
- Read the generated tokens.json back and confirm every required field of the schema is present
- Confirm every color value matches the `#[0-9a-fA-F]{6}` pattern
- Confirm spacing.scale is sorted in ascending order

### Step 3: Generate tokens.css

Convert tokens.json into CSS custom properties.
Follow the **CSS custom property naming rules** of design-system-contract strictly.

**Conversion process:**
1. Read tokens.json
2. Convert every token into a CSS custom property
3. Separate the sections with comments
4. Save to `.design/tokens.css`

**Generation template:**

```css
/* =================================================================
 * Design Tokens — Auto-generated from tokens.json
 * DO NOT EDIT MANUALLY. Run design-scaffold to regenerate.
 * ================================================================= */

:root {
  /* ── Colors ── */
  --color-primary: {colors.primary};
  --color-primary-hover: {colors.primaryHover};
  --color-secondary: {colors.secondary};
  --color-accent: {colors.accent};
  --color-background: {colors.background};
  --color-surface: {colors.surface};
  --color-surface-alt: {colors.surfaceAlt};
  --color-error: {colors.error};
  --color-warning: {colors.warning};
  --color-success: {colors.success};
  --color-text-primary: {colors.textPrimary};
  --color-text-secondary: {colors.textSecondary};
  --color-text-disabled: {colors.textDisabled};
  --color-border: {colors.border};
  --color-focus-ring: {colors.focusRing};

  /* ── Typography ── */
  --font-heading: {typography.headingFont};
  --font-body: {typography.bodyFont};
  --font-code: {typography.codeFont};

  --font-size-display: {typography.scale.display.size}px;
  --font-weight-display: {typography.scale.display.weight};
  --line-height-display: {typography.scale.display.lineHeight};
  /* ... emit size, weight, lineHeight, letterSpacing for every level ... */

  /* ── Spacing ── */
  --spacing-base: {spacing.baseUnit}px;
  /* emit each spacing.scale value as --spacing-0, --spacing-1, ... */

  /* ── Component Radii ── */
  --radius-button: {components.buttons.borderRadius}px;
  --radius-card: {components.cards.borderRadius}px;
  --radius-input: {components.inputs.borderRadius}px;

  /* ── Depth ── */
  --shadow-raised: {depth.raised.shadow};
  --shadow-overlay: {depth.overlay.shadow};
  --shadow-modal: {depth.modal.shadow};
  --shadow-toast: {depth.toast.shadow};
}
```

**Dark mode:**
When `colorsDark` exists, also emit a `@media (prefers-color-scheme: dark)` block:
```css
@media (prefers-color-scheme: dark) {
  :root {
    --color-background: {colorsDark.background};
    --color-surface: {colorsDark.surface};
    /* ... */
  }
}
```

### Step 4: Generate the React/Preact theme (when the framework is detected)

When the project uses React/Preact (`react` or `preact` present in `package.json`), generate a TypeScript theme object.

1. Create the `components/{framework}/` directory
2. Save it to `components/{framework}/theme.ts`

**Generation template:**
```typescript
// Auto-generated from .design/tokens.json
// DO NOT EDIT MANUALLY. Run design-scaffold to regenerate.

export const theme = {
  colors: {
    primary: '{colors.primary}',
    primaryHover: '{colors.primaryHover}',
    // ... all color tokens
  },
  typography: {
    headingFont: "{typography.headingFont}",
    bodyFont: "{typography.bodyFont}",
    codeFont: "{typography.codeFont}",
    scale: {
      display: { size: {size}, weight: {weight}, lineHeight: {lh} },
      // ... all levels
    },
  },
  spacing: {
    base: {spacing.baseUnit},
    scale: [{spacing.scale join ', '}],
  },
  components: {
    buttons: { borderRadius: {r}, paddingY: {py}, paddingX: {px} },
    cards: { borderRadius: {r}, padding: {p} },
    inputs: { borderRadius: {r}, paddingY: {py}, paddingX: {px} },
  },
  depth: {
    flat: '{depth.flat.shadow}',
    raised: '{depth.raised.shadow}',
    overlay: '{depth.overlay.shadow}',
    modal: '{depth.modal.shadow}',
    toast: '{depth.toast.shadow}',
  },
} as const;

export type Theme = typeof theme;
```

### Step 5: Generate lint-config.json

Generate the default lint settings at `.design/lint-config.json`.

**Defaults:**
```json
{
  "include": ["src/**/*.{tsx,jsx,ts,css}"],
  "exclude": ["node_modules/**", ".design/**", "**/*.test.*", "**/*.spec.*", "**/*.stories.*"],
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

**Adjustments by detected framework:**
- React/Preact: add `"**/*.tsx"`, `"**/*.jsx"` to `include`
- Flutter: lint is not supported (a future adapter will cover it) → do not generate `lint-config.json`
- VanillaJS: set `include` to `"**/*.js"`, `"**/*.css"`

### Step 6: Completion report

```
✅ Design scaffold generated!

📁 Generated files:
  .design/tokens.json      — design token definitions
  .design/tokens.css       — CSS custom properties
  .design/lint-config.json — lint config
  components/react/theme.ts — React theme object (only when detected)

📊 Token counts:
  Colors: {n} tokens
  Typography: {n} levels
  Spacing: {n} scale values
  Components: {n} definitions
  Depth: {n} elevation levels
  Breakpoints: {n} defined

Next step:
  1. Check how far the codebase complies with `/claude-skills:design-lint`
```

