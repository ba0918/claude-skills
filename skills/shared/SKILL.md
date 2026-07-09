---
name: shared
description: Shared contracts, references, and scripts used by other claude-skills. Install this alongside other skills to enable cross-skill references.
---

# Shared Contracts Library

Shared contracts, references, and utility scripts used by other skills in the claude-skills collection.

**This skill does not provide standalone functionality.** It exists to support the `../shared/references/` relative path convention used by 33+ skills in this collection.

## Cross-Platform Compatibility

This skill collection uses platform-agnostic natural language for all instructions. Skills describe operations (e.g., "read the file", "run a shell command", "delegate to a subagent") without referencing specific tool API names. Each agent platform should map these descriptions to its native tools.

For historical reference, [references/tool-mapping.md](references/tool-mapping.md) documents the mapping between common platform tool names.

## Installation

Always install this skill when installing other claude-skills:

```bash
gh skill install ba0918/claude-skills shared --agent <your-agent>
```
