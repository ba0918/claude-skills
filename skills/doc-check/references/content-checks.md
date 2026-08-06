# Content Checks

Semantic consistency verification leveraging LLM reading comprehension.
Targets deeper discrepancies that structural checks cannot detect.

## Check Perspectives

### 1. Architecture Descriptions

Whether the architecture described in documentation (layer composition, dependency direction, data flow, etc.)
matches the actual code structure.

**Verification method:**
- Extract architecture sections from the document
- Verify described inter-module relationships against actual imports/dependencies
- Cross-reference descriptions like "X calls Y" or "X depends on Y" against actual code

### 2. Workflow Descriptions

Whether the procedures/flows described in documentation match actual behavior.

**Verification method:**
- Extract step-by-step procedures
- Verify that commands, functions, and files referenced in each step actually exist
- Check that flow ordering does not contradict the implementation

### 3. Configuration/Option Descriptions

Whether configuration items, command-line options, and environment variables described in documentation
are actually usable.

**Verification method:**
- Extract configuration examples and option listings from documentation
- Verify that corresponding parsers/handlers exist in the implementation code

### 4. API Documentation

Whether function signatures, arguments, return values, error codes, etc. match the implementation.

**Verification method:**
- Extract API definitions from documentation
- Compare against corresponding implementation code signatures

### 5. Undocumented-Change Detection (diff modes only)

Whether new behavior introduced by the diff is documented anywhere it belongs. Unlike
perspectives 1–4, this one reports **absences**: the finding names a missing statement
and its proposed home, not a mismatched line.

**Verification method:**
- From the change context, list the user-visible or contract-level behavior changes:
  new commands / options / modes, changed defaults, new outputs or states, new files
  with a public role
- For each change, search the target documents (including `docs/spec/` when present)
  for the place that should describe it
- When nothing describes it, report the omission with the proposed addition and its
  placement. AUTO_FIX only when the home is unambiguous (e.g., an existing table that
  enumerates all modes gains a row); otherwise NEEDS_JUDGMENT
- Skipped in `all` / file-path mode — without a diff there is no "new" to anchor on

### 6. Spec Conformance (when docs/spec/ exists)

Specs under `docs/spec/` are behavioral **contracts**, not descriptions. Check them at
contract strictness, and never auto-edit them.

**Verification method:**
- Diff modes: determine whether the diff changes behavior a spec specifies. Both
  outcomes are NEEDS_JUDGMENT — either the implementation violates the spec (report the
  violated clause), or the spec needs updating (report the proposed spec edit). The
  direction of the fix is a human decision
- `all` / file-path mode: check each spec's contract statements (entry conditions,
  prohibitions, output contracts) against the implementation, the way perspectives 1–4
  check prose but treating every mismatch as contract-grade
- **Spec edits are never AUTO_FIX.** A spec is the human-approved statement of what the
  behavior should be; changing it is a decision, not a fix. Silently rewriting a spec to
  match the code would invert the spec-first principle

## Agent Instruction Template

Prompt structure when delegating each document check to an Agent:

```
Verify whether the contents of the following document are consistent with the current codebase state.

## Target Document
{Document contents}

## Change Context (diff mode only)
{git diff contents}

## Check Perspectives
1. Whether architecture descriptions match the actual state
2. Whether workflow/procedure descriptions match actual behavior
3. Whether configuration/option descriptions match the implementation
4. Whether API documentation matches the implementation
5. (diff modes only) Whether new behavior in the diff is documented anywhere it belongs — report omissions with the proposed addition and placement
6. (when docs/spec/ exists) Whether the change conforms to the specs — spec-side edits are always NEEDS_JUDGMENT, never AUTO_FIX

## Output Format
For each finding, report:
- action: AUTO_FIX | NEEDS_JUDGMENT | OK
- file: Target file path
- section: Relevant section name (for perspective 5: the proposed home of the missing statement)
- description: Description of the discrepancy (for perspective 5: the undocumented behavior)
- suggestion: Fix suggestion (for AUTO_FIX/NEEDS_JUDGMENT)
- reason: Rationale for the judgment
```

## Judgment Criteria

AUTO_FIX / NEEDS_JUDGMENT semantics follow the shared
[fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md)
(`OK` is doc-check's own value — see its "Difference from doc-check's `OK`" section).
This classification is a fix-action axis, not a severity axis.

### AUTO_FIX (auto-fixable)
- Simple factual errors (references to non-existent files, etc.)
- Obviously outdated information (mentions of deleted features, etc.)
- Formatting discrepancies (table column mismatches, etc.)

### NEEDS_JUDGMENT (requires review)
- Changes to descriptions about design philosophy or principles
- Discrepancies with multiple possible interpretations
- Descriptions that may intentionally differ from current state (future plans, etc.)

### OK (consistent)
- Documentation descriptions match the actual state
