---
name: design-generate
description: Generate pages under constraints, based on page definitions (.design/pages/*.json) plus a component catalog. It limits the LLM's freedom to the content inside each section, which is what makes the design reproducible. Use when the user says "generate a page", "design generate", or "constrained generation".
---

# Design Generate

Generate a page **under constraints**, based on a page definition plus the component catalog.
Restricting the LLM's freedom to "assembling approved components" and "the content inside a section" structurally guarantees that the design is reproducible.

**Shared contract:** see [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md).

## Prerequisites

1. `.design/tokens.json` must exist
2. `.design/tokens.css` must exist
3. `.design/component-catalog.json` must exist
4. At least one page definition must exist under `.design/pages/`

When any of them is missing:
```
❌ Required files not found:
  {list of missing files}

Generate them with `/claude-skills:design-scaffold`.
```

## Workflow

### Step 1: Decide what to generate

If a page name is given in $ARGUMENTS, generate that page.
If none is given, present the user with options and ask:

```
header: "Pages to generate"
options:
  - dynamically list each page definition under pages/
  - "Generate all pages at once"
```

### Step 2: Read the definition files

1. Read `.design/tokens.json`
2. Read `.design/tokens.css`
3. Read `.design/component-catalog.json`
4. Read `.design/pages/{target}.json`
5. Read `.design/layout-rules.json` (when it exists)

### Step 3: Build the constraints

Read [references/generation-constraints.md](references/generation-constraints.md) first — its
constraint hierarchy, permitted degrees of freedom, and prohibitions govern Steps 3-5; the
summaries below do not replace it.

Build the following constraints from the page definition:

#### Component constraints
- When `allowedComponents` is defined → only the components in that list may be used
- When it is undefined → the whole catalog is permitted
- Each component may use only the props / variants / states exactly as the catalog defines them

#### Layout constraints
- The page structure follows `layout.type` (single-column, sidebar, grid, and so on)
- Adhere strictly to the order of `sections` (controlled by the `order` field)
- Follow each section's `layout` (direction, gap, columns)

#### Token constraints
- Every color → `var(--color-*)`
- Every font → `var(--font-*)`
- Every spacing → `var(--spacing-*)`
- Every corner radius → `var(--radius-*)`
- Every shadow → `var(--shadow-*)`

### Step 4: Generate the page

#### The generation process

1. **Generate the page shell**: build the outer HTML/JSX frame based on layout.type
2. **Place the sections**: place the sections in the order given by the sections definition
3. **Place the components**: following each section's components definition, import and place the catalog's components
4. **Inject the content**: set the content (text, image paths, and so on) into each component's props
5. **Styling**: style using only the CSS variables of tokens.css
6. **Responsive**: handle the breakpoints per the responsive definition

#### The LLM's freedom

**Permitted:**
- The content inside a section (the **contents** of text and images)
- Animations and transitions (an area left undefined by DESIGN.md / the schema)
- The wording of the content and dummy data
- Image placeholders (`<img src="https://placehold.co/..." />`)

**Forbidden:**
- Adding, changing, or removing a component
- Using a value that is not in the tokens
- Changing the section composition
- Using a component outside allowedComponents
- Overriding a token-governed property with an inline style
- Writing a token value literally in a custom CSS class

#### The structure of the generated code

**For React/Preact:**
```typescript
// pages/{PageName}.tsx — Generated from .design/pages/{name}.json
import { Button, Card, Input, Nav } from '../components/react';
import '../.design/tokens.css';

export const {PageName}: React.FC = () => {
  return (
    <div className="page page--{layout.type}" style={{ maxWidth: 'var(--spacing-max-content-width)' }}>
      {/* Section: {section.id} */}
      <section className="section section--{section.id}">
        {/* Components placed per page definition */}
      </section>
    </div>
  );
};
```

**For standalone HTML:**
```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page.title}</title>
  <link rel="stylesheet" href=".design/tokens.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <!-- Google Fonts links from tokens.typography -->
  <style>
    /* Page-specific layout styles using CSS variables only */
  </style>
</head>
<body>
  <!-- Sections and components per page definition -->
</body>
</html>
```

### Step 5: Run the lint automatically

As soon as generation completes, run design-lint to detect violations:

1. Apply DL001-006 + DL101-103 to the generated files
2. When violations are detected:
   - Attempt an automatic fix (replacing with var(--*), and so on)
   - Report violations that cannot be fixed as errors
3. Confirm that every rule PASSes before emitting the output

### Step 6: Output and confirmation

**Where it is written:**
- React: `src/pages/{PageName}.tsx` (present the user with options and confirm the output location)
- HTML: `mockups/{page-name}.html`

```
✅ Page generated!
📄 File: {output_path}

📊 Components used:
  {component name}: {variant} × {count}

🔍 Lint: PASS ✅
  DL001-006: 0 violations
  DL101-103: 0 violations

Open it in a browser and check it.
If you want changes, share your feedback.
```

Present the user with options and confirm any further adjustment:
- 「OK」 → finish
- Correction feedback → fix the code → re-lint → confirm again (a loop)

## Creating a page definition interactively

When `.design/pages/` is empty, or when the user wants to add a new page:

1. Present the user with options and ask for the page type:
   ```
   header: "Page type"
   options:
     - "Landing page"
     - "Dashboard"
     - "List page"
     - "Form page"
   ```
2. Propose a recommended pattern from the `patterns` of layout-rules.json
3. Present the user with options and confirm the section composition
4. Decide the placement for each section from the component list of catalog.json
5. Save it to `.design/pages/{name}.json`
6. Continue on to generating the page

## Absolute Constraints

- **Generating without a page definition is forbidden.** Always go through `.design/pages/*.json`
- The generated code must **PASS every rule of design-lint**
- Import components only from the catalog-generated files (defining your own is forbidden)
- Every CSS value goes through a CSS custom property (literal values are forbidden)
- Never change the page definition's `sections.order`

## References

- **Details of the generation constraints:** [references/generation-constraints.md](references/generation-constraints.md) — the constraint hierarchy / the permitted degrees of freedom / the prohibitions and their corresponding lint rules
- **Page Schema:** [../design-scaffold/references/page-schema.json](../design-scaffold/references/page-schema.json)
- **Layout Schema:** [../design-scaffold/references/layout-schema.json](../design-scaffold/references/layout-schema.json)
- **Catalog Schema:** [../design-scaffold/references/catalog-schema.json](../design-scaffold/references/catalog-schema.json)
- **Shared contract:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
