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

## Output Format
For each finding, report:
- severity: AUTO_FIX | NEEDS_JUDGMENT | OK
- file: Target file path
- section: Relevant section name
- description: Description of the discrepancy
- suggestion: Fix suggestion (for AUTO_FIX/NEEDS_JUDGMENT)
- reason: Rationale for the judgment
```

## Judgment Criteria

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
