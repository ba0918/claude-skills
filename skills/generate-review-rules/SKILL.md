---
name: generate-review-rules
description: Analyze a project's CLAUDE.md, documentation, and code structure, and generate project-specific review rules (.agents/config/review-rules.md) for plan-reviewer and for code review. Use when the user says "generate review rules", "create review-rules", or "set up reviews". Use it as setup before starting reviews in a new project.
---

# Generate Review Rules

Artifact paths follow the [Artifact Store consumer contract](../shared/references/artifact-paths.md). Resolve and validate the store before reading or writing artifacts.

Analyze the project's documentation and code structure to generate project-specific review rules in `.agents/config/review-rules.md` for use with plan-reviewer and code reviews.

## Workflow

### Step 1: Gather Information

Read the following sources in order (only those that exist):

1. `CLAUDE.md` (project root) — Focus on Design Principles, Tech Stack, and Architecture sections
2. `docs/ARCHITECTURE.md` or `docs/architecture.md`
3. `docs/SECURITY.md` or `docs/security.md`
4. `.agents/artifacts/status.md` — Understand the current project state

### Step 2: Detect Project Characteristics

Follow the language detection contract in [../shared/references/lang-detect.md](../shared/references/lang-detect.md) to identify the project's language/framework composition.

The contract covers: Rust, TypeScript/JavaScript, Go, Python, Dart, PHP (including legacy 5.x), Java/Kotlin, Ruby, C#, HTML/CSS.

Search for marker files by listing files. Multiple matches across subdirectories suggest a monorepo.

### Step 3: Generate Rules

Generate `.agents/config/review-rules.md` from the collected information.

Output template: [references/output-template.md](references/output-template.md)

**Generation rules:**
- Design principles explicitly stated in CLAUDE.md should be **quoted verbatim** (do not alter through interpretation)
- Add typical pitfalls specific to the language/framework in the Language/Framework Specific section
- Omit sections for perspectives that don't exist in the project (don't force-fill)
- Each rule should be specific and verifiable (vague expressions like "use good design" are prohibited)

### Step 4: Confirm and Output

1. If `.agents/config/review-rules.md` already exists, confirm overwrite with the user
2. Present the generated content to the user and provide an opportunity for adjustments
3. Write the file after approval
