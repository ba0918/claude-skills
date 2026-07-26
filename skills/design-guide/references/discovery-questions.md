# Discovery Questions

The question bank used in the discovery phase, and the answer-interpretation matrix.

## The principles of question design

- **Avoid open questions**: "What kind of colors would you like?" is forbidden. Present concrete options
- **Narrow with 2 to 4 choices**: present options (2-4) and converge on a direction
- **Make use of previews**: for color palettes and fonts, show an ASCII representation in the preview field
- **Concretize in stages**: raise the level of detail in the order mood → color direction → concrete hex values
- **An interim summary at the head of each phase**: summarize the decisions of the previous phase before moving on

## Phase 1: Project context

### Q1: The kind of project

header: "Project kind"

| Option | Description |
|--------|-------------|
| A web app / SPA | A business tool, SaaS, dashboard, or the like that has a login |
| A landing page / marketing | A product introduction, service LP, portfolio, or the like |
| A mobile app | iOS / Android / cross-platform |
| Documentation / a blog | Technical documents, a blog, a knowledge base, or the like |

### Q2: The target user

header: "User segment"

| Option | Description |
|--------|-------------|
| Developers / tech people | Engineers, designers, the tech-inclined |
| General consumers | A broad age range, with varying IT literacy |
| Business / enterprise | Corporate decision-makers, the manager tier |
| An internal tool | An internal tool used by your own team |

### Q3: The impression you want to give (multiSelect: true, up to 2)

header: "Impression"

| Option | Description |
|--------|-------------|
| Professional | Trustworthy, stable, composed |
| Approachable | Casual, bright, friendly |
| Advanced / innovative | Technological, futuristic, edgy |
| Premium / luxurious | Refined, luxury, dignified |

## Phase 2: Visual direction (a rush of binary choices)

Present each question to the user one at a time. Attach a concrete image to the description of each option.

### Q4: Color mode

header: "Color mode"

| Option | Description |
|--------|-------------|
| Light mode first | Based on a white background. Dark mode is considered later |
| Dark mode first | Based on a dark background. Common for developer tools and media |
| Designed for both | Define both palettes from the start |

### Q5: Color tone

header: "Color temperature"

| Option | Description |
|--------|-------------|
| Warm | Leaning orange, red, yellow. Approachable, energetic |
| Cool | Leaning blue, purple, green. Trustworthy, intelligent, composed |
| Neutral | Gray, beige, slate. Understated, with the content as the lead |

### Q6: Information density

header: "Density"

| Option | Description |
|--------|-------------|
| Spacious | Plenty of margin. It breathes, and the eye never gets lost |
| Dense | Prioritizing volume of information. Suited to dashboards and data |

### Q7: The shape of corners

header: "Corner radius"

| Option | Description |
|--------|-------------|
| Rounded | A soft, rounded UI. Approachable, friendly |
| Sharp | Linear and sharp. Professional, structural |
| Moderate | A moderate roundness (4-8px). The balanced type |

### Q8: The strength of color

header: "Saturation"

| Option | Description |
|--------|-------------|
| Bold | High saturation, high contrast. Eye-catching, energetic |
| Subtle | Low saturation, soft. Elegant, easy on the eyes |

### Q9: The expression of depth

header: "Depth"

| Option | Description |
|--------|-------------|
| Flat | No shadow, or extremely light. Separated by borders |
| Depth | Depth expressed with shadows and elevation |

### Q10: The direction of the fonts

header: "Fonts"

| Option | Description |
|--------|-------------|
| Sans-serif (Modern) | Geometric / Grotesque. Modern, clean |
| Serif (Classic) | Traditional, authoritative, editorial |
| Mixed (serif headings + sans-serif body) | Creating a visual rhythm through contrast |

## Phase 3: Generating the color palette

Generate 3 palette candidates from the Phase 2 answers and present them as options with previews.

### The interpretation matrix

| Temperature | Saturation | Impression | The direction of the Primary candidate |
|------|------|------|-----------------|
| Warm + Bold | — | Around #E84855, #FF6B35, #F77F00 |
| Warm + Subtle | — | Around #C1666B, #D4A373, #DDA15E |
| Cool + Bold | — | Around #2563EB, #7C3AED, #0891B2 |
| Cool + Subtle | — | Around #6B7280, #64748B, #78716C |
| Neutral + Bold | — | Around #18181B, #0F172A, #1C1917 |
| Neutral + Subtle | — | Around #9CA3AF, #A1A1AA, #A8A29E |

Present each candidate as a whole palette containing:
- Primary / Secondary / Accent
- Background / Surface
- Text Primary / Secondary
- Error / Warning / Success

### The preview format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━
 Option A: "Ocean Breeze"
━━━━━━━━━━━━━━━━━━━━━━━━━━
 Primary:    #2563EB ████
 Secondary:  #3B82F6 ████
 Accent:     #06B6D4 ████
 Background: #FFFFFF
 Surface:    #F8FAFC ████
 Text:       #0F172A ████
 Error:      #DC2626 ████
 Success:    #16A34A ████
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Phase 4: Choosing typography

Based on the Q10 answer from Phase 2, present 3 font-pairing candidates.

### The pool of font candidates

**Sans-serif (suited to headings):**
- Outfit — Geometric, modern, versatile
- Satoshi — Clean, contemporary, neutral
- Cabinet Grotesk — Bold, distinctive character
- Clash Display — Strong, editorial presence
- General Sans — Balanced, professional
- Switzer — Swiss-inspired, precise

**Sans-serif (suited to body text):**
- Plus Jakarta Sans — Friendly, readable
- DM Sans — Clean, geometric harmony
- Manrope — Semi-rounded, tech-friendly
- Geist — Vercel's font, developer-oriented
- Onest — Round, warm, accessible

**Serif:**
- Playfair Display — Elegant, editorial
- Fraunces — Quirky, warm, distinctive
- Newsreader — Traditional, readable
- Lora — Elegant, literary
- Source Serif 4 — Professional, versatile

**Monospace:**
- JetBrains Mono — Developer favorite, ligatures
- Fira Code — Ligatures, readable
- IBM Plex Mono — Clean, professional

### Forbidden fonts (from Anti-patterns)

The following must not be used. An AI reaches for them too readily, so they lack distinctiveness:
- Inter
- Roboto
- Arial
- Helvetica
- Open Sans
- Lato
- Montserrat
- Poppins
- system-ui (as a substitute for a concrete font)
- Space Grotesk

## Phase 5: Confirming components and layout

Integrate what was decided in Phases 2-4 and propose the styling of the main components.

### The automatic derivation rules

| The Phase 2 answer | The derived token |
|-------------|------------------|
| Rounded | border-radius: 12-16px (button), 16-24px (card) |
| Sharp | border-radius: 0-2px (button), 0-4px (card) |
| Moderate | border-radius: 6-8px (button), 8-12px (card) |
| Spacious | base-unit: 8px, section-gap: 64-96px, max-width: 1200px |
| Dense | base-unit: 4px, section-gap: 24-32px, max-width: 1440px |
| Flat | shadow: none, border: 1px solid {border} |
| Depth | shadow: 0 1px 3px rgba(0,0,0,0.1) to 0 25px 50px rgba(0,0,0,0.25) |

### The items to confirm

Final confirmation with the user:
- Display a preview of the generated component styles
- Ask whether this direction is acceptable
- Accept any fine adjustments as free text

## Points to watch when interpreting

- The answers are hints, not absolutes. When answers contradict each other, confirm the intent with the user
- When the user enters free text via "Other", reflect that content with the highest priority
- Throughout every phase, reflect the user's own words into the "Visual Theme & Atmosphere" section of DESIGN.md
