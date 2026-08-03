### Step 7: Generate the component catalog

From the Component Stylings section of DESIGN.md, generate `component-catalog.json` conforming to [catalog-schema.json](catalog-schema.json) — read the schema in full before generating.

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

