# Anti-Patterns: guardrails against AI-looking UI

Prohibitions distilled from the frontend-design skill and from the knowledge of the design community.
Check against them when generating DESIGN.md and when reviewing.

## Forbidden fonts

The following fonts are the ones an AI reaches for too readily, and they lack character. Do not use them:

- Inter
- Roboto
- Arial
- Helvetica
- Open Sans
- Lato
- Montserrat
- Poppins
- Space Grotesk
- system-ui / sans-serif (using only the fallback, with no concrete font specified)

## Forbidden color patterns

- **A purple gradient on a white background** — the emblem of AI-ness. Avoid the purple → blue gradient in particular
- **Indigo + white** — the feel of a characterless SaaS template
- **#6366F1 (Indigo-500) as the primary** — the feel of leaving the Tailwind default as-is
- **#8B5CF6 (Violet-500) as the accent** — the same
- **All-over grayscale + a zero-saturation accent** — outside a deliberately monochrome design, it feels lazy

## Forbidden layout patterns

- **A centered hero + 3-column cards + a CTA** — the feel of a template used verbatim
- **A left sidebar and nothing but content on the right** — a dashboard with no thought in it
- **A perfectly symmetric grid** — put in at least one asymmetric or grid-breaking element
- **The same padding for every section** — vary the pace between sections

## Forbidden component patterns

- **Every button the same size and the same style** — differentiating primary / secondary / ghost is mandatory
- **Changing only opacity on hover** — use a more deliberate interaction (a color change, scale, translateY, and so on)
- **`border-radius: 8px` unified across every element** — vary it with the element's role
- **The same shadow on every card** — be conscious of the elevation hierarchy

## What to do (Positive Patterns)

### The points of differentiation

- **Font pairing**: create contrast between headings and body
- **How the accent color is used**: a dominant color + a sharp accent beats a flat palette
- **The pace of space**: vary the margins between sections. A rhythm of dense areas and roomy ones
- **Fine detail**: grain and noise textures, decorative borders, a custom cursor, and the like
- **Asymmetric elements**: break part of the grid, overlap, place things on a diagonal
- **Deliberate choices**: whether minimal or maximal, the intent must be clear. Half-hearted is the worst outcome

### The distinctiveness checklist

After generating DESIGN.md, confirm the following:

1. Is the font absent from the forbidden list?
2. Is the primary color something other than a Tailwind / Material default value left as-is?
3. Is the corner radius something other than the same value on every element?
4. Does the hover state rely on more than opacity alone?
5. Does the layout have at least one asymmetric or grid-breaking element?
6. Is a shadow hierarchy defined (a border hierarchy in the case of flat design)?
7. Does the color combination avoid overlapping with other projects?
