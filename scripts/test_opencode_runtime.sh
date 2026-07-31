#!/bin/sh
# OpenCode installed environment only. Run directly, not through a Node child
# process: some OpenCode versions vary skill discovery by their launcher.
set -eu

command -v opencode >/dev/null 2>&1 || {
  echo "opencode is required for this runtime check" >&2
  exit 2
}

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

OPENCODE_DISABLE_EXTERNAL_SKILLS=1 OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
  opencode debug config > "$tmp/config.json"
# Keep this runtime check executable in an OpenCode-only installation. The
# configured absolute path is JSON-escaped and therefore appears verbatim.
grep -F "\"$root/skills\"" "$tmp/config.json" >/dev/null

OPENCODE_DISABLE_EXTERNAL_SKILLS=1 OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 \
  opencode debug skill > "$tmp/skills.json"
grep -F '"name": "cycle"' "$tmp/skills.json" >/dev/null
grep -F "\"location\": \"$root/skills/cycle/SKILL.md\"" "$tmp/skills.json" >/dev/null

echo "ok: OpenCode runtime plugin checks passed"
