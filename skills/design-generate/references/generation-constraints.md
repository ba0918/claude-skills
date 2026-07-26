# Generation Constraints

The constraint rules applied to the code the design-generate skill produces.

## The constraint hierarchy

```
Page Definition (sections, order, allowedComponents)
  → Component Catalog (variants, props, a11y)
    → Design Tokens (colors, fonts, spacing)
      → CSS Custom Properties (var(--*) only)
```

An upper constraint contains the lower ones. The page definition constrains the components, the components constrain the tokens, and the tokens constrain the CSS values.

## Permitted degrees of freedom

| Category | Freedom | Example |
|---------|--------|-----|
| Text content | completely free | the wording of headings, body text, and labels |
| Image content | URL only | the src attribute of `<img src="...">` |
| Animation | outside the token domain | `transition`, `animation`, `@keyframes` |
| Data binding | completely free | state management, API calls |
| Event handlers | completely free | the logic of onClick, onChange, etc. |

## Prohibitions

| Category | What is prohibited | Rule on violation |
|---------|---------|-------------|
| Color | using a color outside the tokens | DL001 / DL006 |
| Font | using a font outside the tokens | DL002 |
| Spacing | a spacing value outside the tokens | DL003 |
| Border radius | a border-radius outside the tokens | DL004 |
| Shadow | a box-shadow outside the tokens | DL005 |
| Component | a custom component outside the catalog | DL101 |
| Variant | a variant outside the catalog | DL102 |
| Style override | a token-governed property in an inline style | DL103 |
| Section composition | changing the sections of the page-def | DL203 |
| Layout | violating the constraints of layout-rules | DL204 |

## Examples: Do's/Don'ts → mechanically verifiable rules

The Do's/Don'ts in DESIGN.md are natural language. Convert them into a mechanically verifiable form as `constraints` in layout-rules.json.

| Do/Don't (natural language) | constraint (mechanically verifiable) |
|---------------------|---------------------|
| "Left-align by default" | `LC001: text-align: center is allowed on h1, h2 only` |
| "Leave generous whitespace" | `LC002: section gap must be one of the top 3 values of spacing.scale` |
| "Do not use grids with 3 or more columns" | `LC003: grid-template-columns column count ≤ 3` |
| "Stack cards vertically on mobile" | `LC004: flex-direction: column at the sm breakpoint` |
| "Round the corners of every element" | `LC005: border-radius: 0 is forbidden (except the allowRawValues exclusions)` |
