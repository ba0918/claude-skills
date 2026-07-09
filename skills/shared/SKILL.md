---
name: shared
description: Shared contracts, references, and scripts used by other claude-skills. Install this alongside other skills to enable cross-skill references. Includes tool compatibility mapping for Codex CLI.
---

# Shared Contracts Library

Shared contracts, references, and utility scripts used by other skills in the claude-skills collection.

**This skill does not provide standalone functionality.** It exists to support the `../shared/references/` relative path convention used by 33+ skills in this collection.

## Codex CLI Compatibility

This skill collection is written using Claude Code tool names. When running under Codex CLI, refer to [references/tool-mapping.md](references/tool-mapping.md) for the conversion mapping. Codex should interpret Claude-specific tool references (Agent, AskUserQuestion, Bash, Edit, Write, Skill, etc.) according to that mapping.

## Installation

Always install this skill when installing other claude-skills:

```bash
gh skill install ba0918/claude-skills shared --agent <your-agent>
```
