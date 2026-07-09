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

Optional: Claude Code rules are not installed by the plugin format.
If you want to use the repository rules as global Claude Code rules, copy them manually:

  mkdir -p ~/.claude/rules
  cp rules/*.md ~/.claude/rules/
EOF
