#!/bin/bash
# install.sh - deprecated installer stub

set -euo pipefail

cat <<'EOF'
install.sh is deprecated.

Use the plugin installers instead:

  claude plugin marketplace add ba0918/claude-skills
  claude plugin install claude-skills@claude-skills

  codex plugin marketplace add ba0918/claude-skills
  codex plugin add claude-skills@claude-skills

  # OpenCode — add to opencode.json, then restart:
  #   "plugin": ["claude-skills@git+https://github.com/ba0918/claude-skills.git"]
  # See docs/README.opencode.md

Note: Claude Code plugin users do NOT need to copy rules/ manually.
The plugin's SessionStart hook (hooks/hooks.json) injects the using-workflow
funnel (skills/using-workflow/SKILL.md) into the session context automatically.

OpenCode plugin users also get the using-workflow funnel + quality-gate pointer
injection via .opencode/plugins/claude-skills.js (no manual rules/ copy).

Optional manual copy — only for users who install skills individually without
the plugin, or for agents other than Claude Code:

  mkdir -p ~/.claude/rules
  cp rules/*.md ~/.claude/rules/
EOF
