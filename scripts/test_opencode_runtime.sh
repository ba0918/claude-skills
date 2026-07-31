#!/bin/sh
# OpenCode installed environment only. Run directly, not through a Node child
# process: some OpenCode versions vary skill discovery by their launcher.
set -eu

json_escape() {
  printf '%s' "$1" | sed 's/[\\"]/\\&/g'
}

# Exercise the path-to-JSON boundary without needing an OpenCode installation.
if [ "${OPENCODE_RUNTIME_TEST_JSON_ESCAPE:-0}" = "1" ]; then
  input='quote" and \\'
  expected='quote\" and \\\\'
  test "$(json_escape "$input")" = "$expected"
  echo "ok: OpenCode runtime JSON path escaping passed"
  exit 0
fi

command -v opencode >/dev/null 2>&1 || {
  echo "opencode is required for this runtime check" >&2
  exit 2
}

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

OPENCODE_DISABLE_EXTERNAL_SKILLS=1 OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
  opencode debug config > "$tmp/config.json"
# Keep this runtime check executable in an OpenCode-only installation. Escape
# paths at every JSON boundary without requiring a separate JSON runtime.
skills_path="$root/skills"
escaped_skills_path=$(json_escape "$skills_path")
grep -F "\"$escaped_skills_path\"" "$tmp/config.json" >/dev/null

OPENCODE_DISABLE_EXTERNAL_SKILLS=1 OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
  opencode debug skill > "$tmp/skills.json"
grep -F '"name": "cycle"' "$tmp/skills.json" >/dev/null
location_path="$skills_path/cycle/SKILL.md"
escaped_location_path=$(json_escape "$location_path")
grep -F "\"location\": \"$escaped_location_path\"" "$tmp/skills.json" >/dev/null

echo "ok: OpenCode runtime plugin checks passed"
