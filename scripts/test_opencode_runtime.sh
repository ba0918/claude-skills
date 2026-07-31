#!/bin/sh
# OpenCode installed environment only. Run directly, not through a Node child
# process: some OpenCode versions vary skill discovery by their launcher.
set -eu

json_escape() {
  # `od` lets this stay independent from Node/Python while handling every byte
  # that JSON requires to be escaped. POSIX paths cannot contain NUL.
  printf '%s' "$1" | LC_ALL=C od -An -v -tx1 |
    while IFS= read -r line; do
      for byte in $line; do
        case "$byte" in
          22) printf '\\"' ;;
          5c) printf '\\\\' ;;
          08) printf '\\b' ;;
          09) printf '\\t' ;;
          0a) printf '\\n' ;;
          0c) printf '\\f' ;;
          0d) printf '\\r' ;;
          0[0-7]|0b|0e|0f|1[0-9a-f]) printf '\\u00%s' "$byte" ;;
          *) printf '%b' "\\$(printf '%03o' "0x$byte")" ;;
        esac
      done
    done
}

# Exercise the path-to-JSON boundary without needing an OpenCode installation.
if [ "${OPENCODE_RUNTIME_TEST_JSON_ESCAPE:-0}" = "1" ]; then
  input=$(printf 'quote" slash\\ tab\t newline\n carriage\r backspace\b formfeed\f')
  expected='quote\" slash\\ tab\t newline\n carriage\r backspace\b formfeed\f'
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
