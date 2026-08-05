#!/usr/bin/env bash
# Ollama executor wrapper for process_runner.
#
# Reads a prompt from stdin, sends it to a local Ollama model via the HTTP API,
# and writes the response to the file specified by $OUTPUT_FILE.
#
# Required env vars (set in backends.json argv via `env`):
#   OLLAMA_MODEL  — model tag (e.g. qwen3:14b)
#   OUTPUT_FILE   — path to write the response artifact
#
# Optional:
#   OLLAMA_HOST   — base URL (default: http://localhost:11434)
#   OLLAMA_TEMPERATURE — temperature (default: 0)
#   OLLAMA_NUM_PREDICT — max tokens (default: 4096)

set -euo pipefail

: "${OLLAMA_MODEL:?OLLAMA_MODEL is required}"
: "${OUTPUT_FILE:?OUTPUT_FILE is required}"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_TEMPERATURE="${OLLAMA_TEMPERATURE:-0}"
OLLAMA_NUM_PREDICT="${OLLAMA_NUM_PREDICT:-4096}"

PROMPT="$(cat)"

if [ -z "$PROMPT" ]; then
  echo "ERROR: empty prompt on stdin" >&2
  exit 1
fi

PAYLOAD=$(python3 -c "
import json, sys
prompt = sys.stdin.read()
print(json.dumps({
    'model': '${OLLAMA_MODEL}',
    'messages': [{'role': 'user', 'content': prompt}],
    'stream': False,
    'options': {
        'temperature': ${OLLAMA_TEMPERATURE},
        'num_predict': ${OLLAMA_NUM_PREDICT}
    }
}))
" <<< "$PROMPT")

RESPONSE=$(curl -sf "${OLLAMA_HOST}/api/chat" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --max-time 600)

python3 -c "
import json, sys
resp = json.loads(sys.stdin.read())
content = resp.get('message', {}).get('content', '')
# Strip thinking tags if present (qwen3 thinking mode)
import re
content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
with open('${OUTPUT_FILE}', 'w') as f:
    f.write(content)
print(f'Wrote {len(content)} chars to ${OUTPUT_FILE}', file=sys.stderr)
" <<< "$RESPONSE"
