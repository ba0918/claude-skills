---
name: design-scaffold
description: DESIGN.md から machine-readable なデザインシステム（tokens.json + tokens.css + component-catalog + lint 設定）を scaffold 生成するスキル。design-guide で作った DESIGN.md を機械的検証可能な形に変換する。「デザインスキャフォールド」「scaffold」「トークン生成」で起動。
---

# Design Scaffold

A skill that generates machine-readable design system files from DESIGN.md.
It converts the "human-readable dictionary of values" produced by design-guide into a **schema-based system that can be verified mechanically**.

**Shared contract:** see [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md).

## Preconditions

1. `DESIGN.md` exists at the project root
   - If it does not, display "DESIGN.md not found. Create it with `/claude-skills:design-guide`." and stop
2. Read DESIGN.md and grasp the structure of every section

## Workflow

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

Convert the parsed data into JSON conforming to [references/tokens-schema.json](references/tokens-schema.json).

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

### Step 7: Generate the component catalog

From the Component Stylings section of DESIGN.md, generate `component-catalog.json` conforming to [references/catalog-schema.json](references/catalog-schema.json).

#### 7-1. Extract components from DESIGN.md

Map each subsection of Component Stylings onto a component definition:

| DESIGN.md subsection | Component name | Category |
|------------------------|---------------|---------|
| Buttons | `Button` | `action` |
| Cards | `Card` | `container` |
| Inputs | `Input` | `input` |
| Navigation | `Nav` | `navigation` |

#### 7-2. Example of generating the Button component

The Buttons table in DESIGN.md:
```
| Variant | Background | Text | Border | Border Radius | Padding |
```

→ catalog.json:
```json
{
  "name": "Button",
  "category": "action",
  "description": "An interactive action button",
  "variants": [
    {
      "name": "primary",
      "styles": {
        "background": "$tokens.colors.primary",
        "color": "$tokens.components.buttons.variants.primary.color",
        "border": "none",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    },
    {
      "name": "secondary",
      "styles": {
        "background": "transparent",
        "color": "$tokens.colors.primary",
        "border": "$tokens.components.buttons.variants.secondary.border",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    },
    {
      "name": "ghost",
      "styles": {
        "background": "transparent",
        "color": "$tokens.colors.textPrimary",
        "border": "none",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    },
    {
      "name": "destructive",
      "styles": {
        "background": "$tokens.colors.error",
        "color": "#FFFFFF",
        "border": "none",
        "borderRadius": "$tokens.components.buttons.borderRadius",
        "paddingY": "$tokens.components.buttons.paddingY",
        "paddingX": "$tokens.components.buttons.paddingX",
        "cursor": "pointer",
        "transition": "all 0.2s ease"
      }
    }
  ],
  "states": [
    {
      "name": "hover",
      "trigger": ":hover",
      "styles": { "background": "$tokens.colors.primaryHover" }
    },
    {
      "name": "focus",
      "trigger": ":focus-visible",
      "styles": { "shadow": "0 0 0 2px $tokens.colors.focusRing" }
    },
    {
      "name": "active",
      "trigger": ":active",
      "styles": { "opacity": 0.9 }
    },
    {
      "name": "disabled",
      "trigger": ":disabled",
      "styles": { "opacity": 0.5, "cursor": "not-allowed" }
    }
  ],
  "props": [
    { "name": "variant", "type": "\"primary\" | \"secondary\" | \"ghost\" | \"destructive\"", "required": false, "default": "primary" },
    { "name": "size", "type": "\"sm\" | \"md\" | \"lg\"", "required": false, "default": "md" },
    { "name": "disabled", "type": "boolean", "required": false, "default": false },
    { "name": "onClick", "type": "() => void", "required": false },
    { "name": "children", "type": "ReactNode", "required": true }
  ],
  "tokens": [
    "$tokens.colors.primary",
    "$tokens.colors.primaryHover",
    "$tokens.colors.error",
    "$tokens.colors.textPrimary",
    "$tokens.colors.focusRing",
    "$tokens.components.buttons.borderRadius",
    "$tokens.components.buttons.paddingY",
    "$tokens.components.buttons.paddingX"
  ],
  "a11y": {
    "role": "button",
    "ariaAttributes": [
      { "name": "aria-disabled", "boundToProp": "disabled" }
    ],
    "keyboardNav": [
      { "key": "Enter", "action": "activate" },
      { "key": "Space", "action": "activate" }
    ],
    "minContrastRatio": 4.5
  }
}
```

#### 7-3. Generate Card, Input, and Nav the same way

Generate a catalog entry from each component's DESIGN.md definition with the same procedure.
Express every style value as a `$tokens.*` reference; hardcoded values are allowed only for CSS keywords (`none`, `transparent`, `inherit`).

#### 7-4. Self-verification of catalog.json

After generation:
1. Confirm every `$tokens.*` reference exists in tokens.json
2. Confirm each component's variants correspond 1:1 with the DESIGN.md definitions
3. Confirm the props types are valid TypeScript

#### 7-5. Save to `.design/component-catalog.json`

### Step 8: Generate React/Preact components

When the framework is React/Preact, generate the component implementations from catalog.json.

#### Generation rules

1. **Style only through the custom properties in tokens.css**
   - `$tokens.colors.primary` → `var(--color-primary)`
   - `$tokens.components.buttons.borderRadius` → `var(--radius-button)`
2. **Props conform exactly to the props definitions in catalog.json**
   - Generate the TypeScript types automatically
   - Set the default values
3. **Only the variants listed in catalog.json**
   - Switch with the variant prop, implement with CSS classes
4. **Only the states listed in catalog.json**
   - CSS pseudo-class + JS event handler
5. **Attach the a11y requirements automatically as HTML attributes**
   - role, aria-*, keyboard navigation

#### Generation template (Button example)

```typescript
// components/react/Button.tsx — Auto-generated from .design/component-catalog.json
// DO NOT EDIT MANUALLY. Run design-scaffold to regenerate.

import React from 'react';
import './Button.css';

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  disabled = false,
  onClick,
  children,
}) => {
  return (
    <button
      className={`btn btn--${variant} btn--${size}`}
      disabled={disabled}
      onClick={onClick}
      aria-disabled={disabled}
    >
      {children}
    </button>
  );
};
```

```css
/* components/react/Button.css — Auto-generated from .design/component-catalog.json */

.btn {
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: var(--font-body);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
  border-radius: var(--radius-button);
}

.btn--primary {
  background: var(--color-primary);
  color: /* tokens.components.buttons.variants.primary.color */;
  padding: var(--spacing-/* paddingY */) var(--spacing-/* paddingX */);
}

/* ... styles for each variant, state, and size ... */

.btn:hover:not(:disabled) { /* hover styles */ }
.btn:focus-visible { box-shadow: 0 0 0 2px var(--color-focus-ring); outline: none; }
.btn:active:not(:disabled) { opacity: 0.9; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
```

#### Generate index.ts

```typescript
// components/react/index.ts — Auto-generated
export { Button } from './Button';
export type { ButtonProps } from './Button';
export { Card } from './Card';
export type { CardProps } from './Card';
export { Input } from './Input';
export type { InputProps } from './Input';
export { Nav } from './Nav';
export type { NavProps } from './Nav';
```

### Step 9: Completion report (extended)

Add the catalog information to the Step 6 completion report:

```
📊 Components:
  Components: {n} defined (Button, Card, Input, Nav)
  Variants: {n} total
  Props: {n} total
  Framework: {framework}

📁 Additional generated files:
  .design/component-catalog.json — component specification definitions
  components/{framework}/Button.tsx + Button.css
  components/{framework}/Card.tsx + Card.css
  components/{framework}/Input.tsx + Input.css
  components/{framework}/Nav.tsx + Nav.css
  components/{framework}/index.ts
```

### Step 10: Generate layout rules

From the Layout Principles + Do's/Don'ts sections of DESIGN.md, generate `layout-rules.json` conforming to [references/layout-schema.json](references/layout-schema.json).

#### 10-1. Layout Principles → grid / spacing

| DESIGN.md field | layout-rules.json path |
|---------------------|----------------------|
| Grid: {columns} columns, {gap}px gap | `grid.columns`, `grid.gap` |
| Max content width: {width}px | `grid.maxWidth` |
| Base unit: {unit}px | (spacing.baseUnit lives in tokens.json) |
| Section spacing: {spacing}px | `spacing.sectionGap` |
| White space philosophy: {description} | converted into constraints |

#### 10-2. Do's/Don'ts → constraints conversion

Convert the Do / Don't lists in DESIGN.md into the `constraintDef` form of [references/layout-schema.json](references/layout-schema.json).

**Conversion rules:**
1. Read each Do / Don't
2. Translate it into a mechanically verifiable condition (natural language → regular expression or numeric range)
3. Decide the enforcement:
   - rules about CSS property values → `lint`
   - rules about visual placement and balance → `visual`
   - rules about overall impression and consistency → `rubric`
4. Assign IDs sequentially starting at `LC001`

#### 10-3. Save to `.design/layout-rules.json`

### Step 11: Generate page definition templates

Present options to the user and ask about the project's main pages:

```
header: "Main pages"
question: "What are the main pages of this project?"
multiSelect: true
options:
  - "Landing page"
  - "Dashboard"
  - "List page"
  - "Form page"
```

For each selected page:
1. Get the recommended layout pattern from `patterns` in layout-rules.json
2. Build the recommended placement for each section from the components in catalog.json
3. Generate a page definition conforming to [references/page-schema.json](references/page-schema.json)
4. Save it to `.design/pages/{page-name}.json`

### Step 12: Final completion report

```
📊 Layout:
  Layout Rules: {n} constraints defined
  Page Definitions: {n} pages

📁 Additional generated files:
  .design/layout-rules.json — layout constraints
  .design/pages/{page-name}.json × {n}

Next steps:
  1. Generate the pages with `/claude-skills:design-generate`
  2. Move on to the Base Design approval flow
```

## Overwrite Confirmation for an Existing .design/

When `.design/tokens.json` already exists:

1. Read the existing `version`
2. Present options to the user and confirm:
   - "Overwrite (increment the version)"
   - "Cancel"
3. On overwrite, increment the patch version of `version`

## Absolute Constraints

- **Never add** a value to tokens.json that is not defined in DESIGN.md
- tokens.json must conform to the schema 100% (fix schema violations immediately)
- CSS custom property names must follow the design-system-contract naming rules **strictly**
- Always include an "Auto-generated, DO NOT EDIT MANUALLY" comment at the top of generated files

## References

- **Token Schema:** [references/tokens-schema.json](references/tokens-schema.json)
- **Catalog Schema:** [references/catalog-schema.json](references/catalog-schema.json)
- **Page Schema:** [references/page-schema.json](references/page-schema.json)
- **Layout Schema:** [references/layout-schema.json](references/layout-schema.json)
- **Rubric Schema:** [references/rubric-schema.json](references/rubric-schema.json)
- **Shared contract:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
