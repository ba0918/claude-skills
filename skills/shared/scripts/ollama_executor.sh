#!/usr/bin/env bash
# Ollama executor wrapper for process_runner.
#
# Reads a prompt from stdin, sends it to a local Ollama model via the HTTP API,
# and writes the response to the file specified by $OUTPUT_FILE.
#
# Scope: this is a pure-text executor — no tool use, no file access. It cannot
# read skill files referenced by path in the prompt, cannot produce artifacts in
# the unit's working directory, and can still emit a plausible-looking report.
# Restrict it to scenarios whose prompt is self-contained and whose only
# artifact is the report text (read-only / report-style fixtures). See
# skills/skill-regression/references/process-queue.md § Text-only backends.
#
# Required env vars (set in backends.json argv via `env`):
#   OLLAMA_MODEL  — model tag (e.g. qwen3:14b)
#   OUTPUT_FILE   — path to write the response artifact
#
# Optional:
#   OLLAMA_HOST        — base URL (default: http://localhost:11434)
#   OLLAMA_TEMPERATURE — temperature (default: 0)
#   OLLAMA_NUM_PREDICT — max tokens (default: 4096)
#   OLLAMA_MAX_TIME    — curl timeout in seconds (default: 600)

set -euo pipefail

: "${OLLAMA_MODEL:?OLLAMA_MODEL is required}"
: "${OUTPUT_FILE:?OUTPUT_FILE is required}"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MAX_TIME="${OLLAMA_MAX_TIME:-600}"
export OLLAMA_MODEL OUTPUT_FILE
export OLLAMA_TEMPERATURE="${OLLAMA_TEMPERATURE:-0}"
export OLLAMA_NUM_PREDICT="${OLLAMA_NUM_PREDICT:-4096}"

PROMPT="$(cat)"

if [ -z "$PROMPT" ]; then
  echo "ERROR: empty prompt on stdin" >&2
  exit 1
fi

# 設定値は Python ソースへ文字列展開せず env 経由で受け渡す。展開だと数値欄に
# 紛れた任意の Python 式がそのまま実行され、クォート入りの値で構文ごと壊れる
PAYLOAD=$(printf '%s' "$PROMPT" | python3 -c '
import json, os, sys

def numeric(name):
    raw = os.environ[name]
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        sys.exit(f"ERROR: {name} must be numeric (got {raw!r})")

print(json.dumps({
    "model": os.environ["OLLAMA_MODEL"],
    "messages": [{"role": "user", "content": sys.stdin.read()}],
    "stream": False,
    "options": {
        "temperature": numeric("OLLAMA_TEMPERATURE"),
        "num_predict": numeric("OLLAMA_NUM_PREDICT"),
    },
}))
')

# -f を付けない: HTTP エラー時も本文（ollama の error JSON）を受けて下段で
# 内容ごと報告する。-f は本文を捨てるため model not found 等が無言になる
RESPONSE=$(curl -s --show-error "${OLLAMA_HOST}/api/chat" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --max-time "$OLLAMA_MAX_TIME")

printf '%s' "$RESPONSE" | python3 -c '
import json, os, re, sys

raw = sys.stdin.read()
try:
    resp = json.loads(raw)
except json.JSONDecodeError:
    sys.exit("ERROR: ollama response is not JSON (server down, or a proxy in "
             "the way): " + raw[:200])
if "error" in resp:
    sys.exit("ERROR: ollama returned an error: " + str(resp["error"])[:500])

content = resp.get("message", {}).get("content", "")
# qwen3 thinking mode: drop the closed think block. An unclosed block means the
# completion was cut mid-thought — shipping it would grade thinking text as the
# report, so fail loudly instead.
content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL)
if "<think>" in content:
    sys.exit("ERROR: unclosed <think> block — completion truncated "
             "(raise OLLAMA_NUM_PREDICT)")
if resp.get("done_reason") == "length":
    sys.exit("ERROR: completion hit the num_predict cap — report is truncated "
             "(raise OLLAMA_NUM_PREDICT)")
if not content.strip():
    sys.exit("ERROR: empty completion from ollama")

with open(os.environ["OUTPUT_FILE"], "w") as f:
    f.write(content)
print("Wrote %d chars to %s" % (len(content), os.environ["OUTPUT_FILE"]),
      file=sys.stderr)
'
