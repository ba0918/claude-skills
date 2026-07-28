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

Note: Claude Code plugin users do NOT need to copy rules/ manually.
The plugin's SessionStart hook (hooks/hooks.json) injects rules/skill-routing.md
into the session context automatically.

Optional manual copy — only for users who install skills individually without
the plugin, or for agents other than Claude Code:

  mkdir -p ~/.claude/rules
  cp rules/*.md ~/.claude/rules/
EOF
