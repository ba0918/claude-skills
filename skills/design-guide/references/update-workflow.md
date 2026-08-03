## Update Workflow (editing an existing DESIGN.md)

### Pre-checks

1. Check whether `DESIGN.md` exists at the project root
   - If it does not, state that DESIGN.md was not found and that it should be created with `/claude-skills:design-guide`, then stop

### Steps

1. Read `DESIGN.md`
2. Show an overview of the current design system:
   ```
   📋 The current DESIGN.md
   - Theme: {mood}
   - Primary: {primary_color}
   - Font: {heading_font} / {body_font}
   - Density: {density}
   - Radius: {radius_style}
   ```
3. Present choices to the user asking which section to edit:
   - Visual Theme & Atmosphere
   - Color Palette
   - Typography
   - Component Stylings
   - Layout Principles
   - Other (free text)
4. For the chosen section, run the same interactive flow as the corresponding Session Workflow phase
   (read [discovery-phases.md](discovery-phases.md) and run the matching phase)
   - Color Palette → equivalent to Phase 3
   - Typography → equivalent to Phase 4
   - Component Stylings → equivalent to Phase 5
   - Visual Theme → equivalent to Phase 1-2 (and additionally propose updating the other sections it affects)
5. Confirm the edit in a preview, then update DESIGN.md
6. Show a summary of what changed:
   ```
   ✅ DESIGN.md updated!
   📝 What changed:
   - {section}: {a summary of the change}
   ```

### Proposing cascading updates

When a change in one section affects another (e.g. changing the primary colour also changes the button colour under Component Stylings), present choices to the user and propose the cascading update.

