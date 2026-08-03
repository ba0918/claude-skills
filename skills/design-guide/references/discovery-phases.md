### Phase 1: project context

Question bank: see Phase 1 of [references/discovery-questions.md](discovery-questions.md).

1. Present choices to the user and ask what kind of project this is
2. Present choices to the user and ask who the target users are
3. Present choices to the user and ask what impression it should give (multiSelect: true)
4. If $ARGUMENTS carries a project description, take that into account as well

**Interim summary**: organise the Phase 1 answers and show them to the user.

```
📋 Phase 1 summary
- Project: {type}
- Target: {audience}
- Impression: {impressions}
- Tech stack: {detected_stack}

Moving on to Phase 2 in this direction!
```

### Phase 2: visual mood (rapid-fire binary choices)

Question bank: see Phase 2 of [references/discovery-questions.md](discovery-questions.md).

Present 6-7 two-to-three-way choices to the user, one question at a time:

1. Colour mode (light / dark / both)
2. Colour temperature (warm / cool / neutral)
3. Information density (roomy / packed)
4. Corner shape (rounded / squared / in between)
5. Colour intensity (vivid / muted)
6. Depth treatment (flat / dimensional)
7. Font direction (sans-serif / serif / mixed)

**Interim summary**: organise the Phase 2 answers and show them to the user.

```
🎨 Phase 2 summary (visual mood)
- Color mode: {mode}
- Tone: {tone}
- Density: {density}
- Corner radius: {radius}
- Saturation: {saturation}
- Depth: {depth}
- Fonts: {font_direction}

Proposing a color palette in this direction!
```

### Phase 3: colour palette selection

Question bank: see Phase 3 of [references/discovery-questions.md](discovery-questions.md).
Anti-patterns: cross-check against the colour section of [references/anti-patterns.md](anti-patterns.md).

1. From the Phase 2 answers, generate **three palette candidates** using the interpretation matrix
2. Present each palette as ASCII art in the **preview** field of the choice prompt:
   ```
   Option A: "name"
   ──────────────────
   Primary:    #XXXXXX ████
   Secondary:  #XXXXXX ████
   Accent:     #XXXXXX ████
   Background: #XXXXXX
   Surface:    #XXXXXX ████
   Text:       #XXXXXX ████
   Error:      #DC2626 ████
   Success:    #16A34A ████
   ```
3. Once the user has chosen, present choices to confirm the fine-tuning ("is this coloring OK?")
4. If a dark mode is wanted, propose a dark palette the same way

**Anti-pattern check**: confirm the generated palette does not match a forbidden colour pattern in anti-patterns.md. If it does, generate another candidate.

### Phase 4: typography selection

Question bank: see Phase 4 of [references/discovery-questions.md](discovery-questions.md).
Anti-patterns: cross-check against the forbidden fonts in [references/anti-patterns.md](anti-patterns.md).

1. From the answer to Q10 in Phase 2, generate **three font-pairing candidates**
2. Present each candidate in the **preview** of the choice prompt:
   ```
   Option A: "Clean Tech"
   ──────────────────────
   Heading: Outfit (700)
   Body:    Plus Jakarta Sans (400)
   Code:    JetBrains Mono (400)

   Scale:
   Display  48px / H1 36px / H2 28px
   H3 22px / Body 16px / Caption 12px
   ```
3. Once the user has chosen, confirm the fine-tuning of the size scale

**Forbidden-font check**: confirm none of the generated font candidates is a forbidden font from anti-patterns.md.

### Phase 5: components and layout confirmation

Question bank: see Phase 5 of [references/discovery-questions.md](discovery-questions.md).

1. From all the Phase 2-4 answers, propose component styles using the auto-derivation rules
2. Present the styles of the main components in the **preview** of the choice prompt:
   ```
   ┌─────────────────────────────┐
   │ Components Preview          │
   ├─────────────────────────────┤
   │                             │
   │  [■ Primary Button]         │
   │  border-radius: 12px       │
   │  padding: 12px 24px         │
   │                             │
   │  ┌─── Card ──────────────┐  │
   │  │ radius: 16px          │  │
   │  │ shadow: sm             │  │
   │  │ padding: 24px          │  │
   │  └───────────────────────┘  │
   │                             │
   │  [________Input________]    │
   │  radius: 8px, border: 1px  │
   │                             │
   │  Spacing: 8px base          │
   │  Scale: 4 8 12 16 24 32 48 │
   │  Max width: 1200px          │
   └─────────────────────────────┘
   ```
3. Present choices to the user to confirm: "is this direction OK? any fine adjustments?"
4. Auto-generate the Do's / Don'ts from the Phase 2 answers and confirm them
5. Confirm the responsive breakpoints and the mobile strategy

