#!/usr/bin/env bash
set -euo pipefail

REPO="ba0918/claude-skills"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<EOF
Usage: $(basename "$0") --agent <agent> --scope <scope>

全スキルを gh skill install で一括インストールする。
shared を先頭にインストールし、インストール済みのスキルはスキップする。

Options:
  --agent <agent>   対象エージェント (必須)
                    claude-code / codex / github-copilot / cursor / gemini
  --scope <scope>   インストールスコープ (必須)
                    project / user
  --repo <owner/repo>  リポジトリ (default: $REPO)
  --from-local      ローカルからインストール
  --dry-run         実行せず対象スキルを表示
  -h, --help        このヘルプを表示

Examples:
  $(basename "$0") --agent claude-code --scope user
  $(basename "$0") --agent codex --scope user --from-local
EOF
  exit 0
}

AGENT=""
SCOPE=""
FROM_LOCAL=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)  AGENT="$2"; shift 2 ;;
    --scope)  SCOPE="$2"; shift 2 ;;
    --repo)   REPO="$2"; shift 2 ;;
    --from-local) FROM_LOCAL=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [[ -z "$AGENT" ]]; then
  echo "Error: --agent is required" >&2
  exit 1
fi
if [[ -z "$SCOPE" ]]; then
  echo "Error: --scope is required" >&2
  exit 1
fi

# Resolve install directory to check for existing skills
case "$AGENT" in
  claude-code)
    case "$SCOPE" in
      project) INSTALL_DIR=".claude/skills" ;;
      user)    INSTALL_DIR="$HOME/.claude/skills" ;;
    esac ;;
  codex)
    case "$SCOPE" in
      project) INSTALL_DIR=".agents/skills" ;;
      user)    INSTALL_DIR="$HOME/.codex/skills" ;;
    esac ;;
  github-copilot)
    case "$SCOPE" in
      project) INSTALL_DIR=".agents/skills" ;;
      user)    INSTALL_DIR="$HOME/.copilot/skills" ;;
    esac ;;
  cursor)
    case "$SCOPE" in
      project) INSTALL_DIR=".agents/skills" ;;
      user)    INSTALL_DIR="$HOME/.cursor/skills" ;;
    esac ;;
  gemini|antigravity)
    case "$SCOPE" in
      project) INSTALL_DIR=".agents/skills" ;;
      user)    INSTALL_DIR="$HOME/.gemini/skills" ;;
    esac ;;
  *)
    INSTALL_DIR=""
    echo "Warning: unknown agent '$AGENT', skip detection disabled" >&2 ;;
esac

# Discover skills from skills/*/SKILL.md
SKILLS=()
for skill_md in "$REPO_ROOT"/skills/*/SKILL.md; do
  name="$(basename "$(dirname "$skill_md")")"
  SKILLS+=("$name")
done

# Ensure shared is first
ORDERED=()
for s in "${SKILLS[@]}"; do
  if [[ "$s" == "shared" ]]; then
    ORDERED=("shared" "${ORDERED[@]}")
  else
    ORDERED+=("$s")
  fi
done

SOURCE="$REPO"
LOCAL_FLAG=""
if $FROM_LOCAL; then
  SOURCE="$REPO_ROOT"
  LOCAL_FLAG="--from-local"
fi

installed=0
skipped=0
failed=0

echo "Agent: $AGENT"
echo "Scope: $SCOPE"
echo "Source: $SOURCE"
echo "Skills: ${#ORDERED[@]}"
echo ""

for skill in "${ORDERED[@]}"; do
  # Check if already installed
  if [[ -n "$INSTALL_DIR" && -f "$INSTALL_DIR/$skill/SKILL.md" ]]; then
    echo "  skip  $skill (already installed)"
    skipped=$((skipped + 1))
    continue
  fi

  if $DRY_RUN; then
    echo "  would install  $skill"
    continue
  fi

  if gh skill install "$SOURCE" "$skill" \
       --agent "$AGENT" --scope "$SCOPE" $LOCAL_FLAG --force 2>/dev/null; then
    echo "  ✓  $skill"
    installed=$((installed + 1))
  else
    echo "  ✗  $skill (failed)" >&2
    failed=$((failed + 1))
  fi
done

echo ""
echo "Done: $installed installed, $skipped skipped, $failed failed"
