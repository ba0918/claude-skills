#!/usr/bin/env bash
# migrate-cycles-to-plans.sh
#
# Migrate docs/cycles/ → docs/plans/ across a project.
# - Renames the directory
# - Updates all text references in *.md files
# - Flips CRITICAL guard warnings
#
# Usage:
#   migrate-cycles-to-plans.sh [check|run]
#     check  — dry-run: report what would change (default)
#     run    — execute migration

set -euo pipefail

MODE="${1:-check}"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
OLD_DIR="docs/cycles"
NEW_DIR="docs/plans"

# Counters
files_to_move=0
refs_to_update=0
warnings=()

# ─── Preflight ───────────────────────────────────────────────

if [[ ! -d "$PROJECT_ROOT/$OLD_DIR" ]]; then
  echo "✅ Nothing to migrate: $OLD_DIR does not exist."
  exit 0
fi

if [[ -d "$PROJECT_ROOT/$NEW_DIR" ]]; then
  echo "⛔ Cannot migrate: $NEW_DIR already exists."
  echo "   Manual merge required — aborting."
  exit 1
fi

# ─── Count files to move ─────────────────────────────────────

files_to_move=$(find "$PROJECT_ROOT/$OLD_DIR" -type f | wc -l | tr -d ' ')

# ─── Find text references ────────────────────────────────────

# Scan *.md files in project root, excluding .git/ and node_modules/
mapfile -t ref_files < <(
  grep -rl --include='*.md' --exclude-dir='.git' --exclude-dir='node_modules' \
    "docs/cycles" "$PROJECT_ROOT" 2>/dev/null || true
)
refs_to_update=${#ref_files[@]}

# ─── Check mode: report ──────────────────────────────────────

if [[ "$MODE" == "check" ]]; then
  echo "══════════════════════════════════════"
  echo "MIGRATION CHECK: $OLD_DIR → $NEW_DIR"
  echo "══════════════════════════════════════"
  echo ""
  echo "📁 Files to move: $files_to_move"
  echo "📝 Files with references to update: $refs_to_update"

  if [[ $refs_to_update -gt 0 ]]; then
    echo ""
    echo "Affected files:"
    for f in "${ref_files[@]}"; do
      relpath="${f#"$PROJECT_ROOT"/}"
      count=$(grep -c "docs/cycles" "$f" 2>/dev/null || echo 0)
      echo "  - $relpath ($count references)"
    done
  fi

  echo ""
  echo "Run with 'run' to execute migration."
  exit 0
fi

# ─── Run mode: execute ───────────────────────────────────────

if [[ "$MODE" != "run" ]]; then
  echo "⛔ Unknown mode: $MODE"
  echo "   Usage: migrate-cycles-to-plans.sh [check|run]"
  exit 1
fi

echo "══════════════════════════════════════"
echo "MIGRATION: $OLD_DIR → $NEW_DIR"
echo "══════════════════════════════════════"
echo ""

# Step 1: Move directory
echo "📁 Moving $OLD_DIR → $NEW_DIR ..."
mv "$PROJECT_ROOT/$OLD_DIR" "$PROJECT_ROOT/$NEW_DIR"
echo "   Done. ($files_to_move files moved)"

# Step 2: Update text references
echo ""
echo "📝 Updating references in $refs_to_update files ..."

updated_count=0
for f in "${ref_files[@]}"; do
  relpath="${f#"$PROJECT_ROOT"/}"

  # The file may now be under docs/plans/ instead of docs/cycles/
  actual_path="$f"
  if [[ ! -f "$actual_path" ]]; then
    actual_path="${f/docs\/cycles/docs\/plans}"
  fi
  if [[ ! -f "$actual_path" ]]; then
    warnings+=("⚠️  File not found after move: $relpath")
    continue
  fi

  # Replace docs/cycles → docs/plans (handles both with and without trailing slash)
  if grep -q "docs/cycles" "$actual_path" 2>/dev/null; then
    sed -i 's|docs/cycles|docs/plans|g' "$actual_path"
    updated_count=$((updated_count + 1))
    echo "   ✓ $relpath"
  fi
done

# Step 3: Flip CRITICAL guard warnings
# Old: "Do NOT use docs/plans/" → New: "Do NOT use docs/cycles/"
# (After step 2, the old warning became "Do NOT use docs/plans/" which is now wrong)
echo ""
echo "🔄 Flipping CRITICAL guard warnings ..."

guard_count=0
mapfile -t guard_files < <(
  grep -rl --include='*.md' --exclude-dir='.git' --exclude-dir='node_modules' \
    "Do NOT use docs/plans/" "$PROJECT_ROOT" 2>/dev/null || true
)

for f in "${guard_files[@]}"; do
  [[ -z "$f" ]] && continue
  if [[ -f "$f" ]]; then
    sed -i 's|Do NOT use docs/plans/|Do NOT use docs/cycles/|g' "$f"
    relpath="${f#"$PROJECT_ROOT"/}"
    guard_count=$((guard_count + 1))
    echo "   ✓ $relpath"
  fi
done

# ─── Summary ─────────────────────────────────────────────────

echo ""
echo "══════════════════════════════════════"
echo "MIGRATION COMPLETE"
echo "══════════════════════════════════════"
echo "📁 Files moved:      $files_to_move"
echo "📝 Files updated:    $updated_count"
echo "🔄 Guards flipped:   $guard_count"

if [[ ${#warnings[@]} -gt 0 ]]; then
  echo ""
  echo "Warnings:"
  for w in "${warnings[@]}"; do
    echo "  $w"
  done
fi

echo ""
echo "💡 Next steps:"
echo "   1. Review changes: git diff"
echo "   2. Run doc-check to verify consistency"
echo "   3. Commit the migration"
