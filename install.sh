#!/bin/bash
# install.sh — claude-skills installer
#
# Usage:
#   ./install.sh              # Install both Claude Code (legacy) and Codex CLI skills
#   ./install.sh codex        # Install Codex CLI skills only
#   ./install.sh claude       # Install Claude Code skills only (legacy)
#
# Claude Code (recommended):
#   claude plugin install claude-skills@<marketplace>
#   claude --plugin-dir /path/to/claude-skills

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-all}"

# ─────────────────────────────────────────────
# Codex CLI skills installation
# ─────────────────────────────────────────────
install_codex() {
  local codex_dir="$HOME/.codex"
  local skills_dir="$codex_dir/skills"

  if [ ! -d "$codex_dir" ]; then
    echo "⚠  ~/.codex not found — is Codex CLI installed?"
    echo "   Skipping Codex CLI skill installation."
    return 1
  fi

  mkdir -p "$skills_dir"

  echo "Installing Codex CLI skills..."
  local count=0
  for d in "$SCRIPT_DIR"/codex-skills/*/; do
    local name
    name="$(basename "$d")"

    # shared/ is a resource directory, not a skill
    [ "$name" = "shared" ] && continue

    ln -sfn "$d" "$skills_dir/$name"
    echo "  $name -> $d"
    count=$((count + 1))
  done

  echo "Done! ($count Codex skills installed)"
}

# ─────────────────────────────────────────────
# Claude Code legacy installation (deprecated)
# ─────────────────────────────────────────────
install_claude_legacy() {
  local claude_dir="$HOME/.claude"

  echo "══════════════════════════════════════════════════════════════"
  echo "  ⚠  DEPRECATED: Claude Code legacy symlink installation."
  echo ""
  echo "  Recommended: Use Claude Code plugin format instead:"
  echo ""
  echo "    claude plugin install claude-skills@<marketplace>"
  echo "    claude --plugin-dir /path/to/claude-skills"
  echo ""
  echo "══════════════════════════════════════════════════════════════"
  echo ""

  read -p "Continue with legacy symlink installation? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Skipped Claude Code legacy installation."
    return 0
  fi

  mkdir -p "$claude_dir/commands" "$claude_dir/skills" "$claude_dir/rules"

  echo "Installing commands..."
  for f in "$SCRIPT_DIR"/commands/*.md; do
    local name
    name="$(basename "$f")"
    ln -sf "$f" "$claude_dir/commands/$name"
    echo "  $name"
  done

  echo "Installing skills..."
  for d in "$SCRIPT_DIR"/skills/*/; do
    local name
    name="$(basename "$d")"
    ln -sfn "$d" "$claude_dir/skills/$name"
    echo "  $name/"
  done

  echo "Installing rules..."
  for f in "$SCRIPT_DIR"/rules/*.md; do
    [ -f "$f" ] || continue
    local name
    name="$(basename "$f")"
    ln -sf "$f" "$claude_dir/rules/$name"
    echo "  $name"
  done

  echo "Done! (Claude Code legacy installation)"
}

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
case "$MODE" in
  codex)
    install_codex
    ;;
  claude)
    install_claude_legacy
    ;;
  all)
    install_codex
    echo ""
    install_claude_legacy
    ;;
  *)
    echo "Usage: $0 [codex|claude|all]"
    exit 1
    ;;
esac
