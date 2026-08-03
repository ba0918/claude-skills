### Step 10: Generate layout rules

From the Layout Principles + Do's/Don'ts sections of DESIGN.md, generate `layout-rules.json` conforming to [layout-schema.json](layout-schema.json) — read the schema in full before generating.

#### 10-1. Layout Principles → grid / spacing

| DESIGN.md field | layout-rules.json path |
|---------------------|----------------------|
| Grid: {columns} columns, {gap}px gap | `grid.columns`, `grid.gap` |
| Max content width: {width}px | `grid.maxWidth` |
| Base unit: {unit}px | (spacing.baseUnit lives in tokens.json) |
| Section spacing: {spacing}px | `spacing.sectionGap` |
| White space philosophy: {description} | converted into constraints |

#### 10-2. Do's/Don'ts → constraints conversion

Convert the Do / Don't lists in DESIGN.md into the `constraintDef` form of [layout-schema.json](layout-schema.json).

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
2. Build the recommended placement for each section from the components in `.design/component-catalog.json`
3. Generate a page definition conforming to [page-schema.json](page-schema.json) — read the schema in full before generating
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

