#!/bin/bash
# Install claude-skills: create symlinks in ~/.claude/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

mkdir -p "$CLAUDE_DIR/commands" "$CLAUDE_DIR/skills"

echo "Installing commands..."
for f in "$SCRIPT_DIR"/commands/*.md; do
  name="$(basename "$f")"
  ln -sf "$f" "$CLAUDE_DIR/commands/$name"
  echo "  $name"
done

echo "Installing skills..."
for d in "$SCRIPT_DIR"/skills/*/; do
  name="$(basename "$d")"
  ln -sfn "$d" "$CLAUDE_DIR/skills/$name"
  echo "  $name/"
done

# .skill files
for f in "$SCRIPT_DIR"/skills/*.skill; do
  [ -f "$f" ] || continue
  name="$(basename "$f")"
  ln -sf "$f" "$CLAUDE_DIR/skills/$name"
  echo "  $name"
done

echo "Done!"
