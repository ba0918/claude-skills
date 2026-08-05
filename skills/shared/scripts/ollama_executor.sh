#!/usr/bin/env bash
# Ollama executor wrapper for process_runner.
#
# Reads a prompt from stdin and runs it against a local Ollama model in two
# calls (the convention is normative in
# skills/skill-regression/references/process-queue.md § Text-only backends):
#
#   call 1  produce the deliverable itself → saved as artifact.md next to
#           $OUTPUT_FILE, the caller's re-judge counterpart
#   call 2  continue the conversation, self-assess → $OUTPUT_FILE
#
# Scope: this is a pure-text executor — no tool use, no file access. It cannot
# read skill files referenced by path in the prompt and cannot touch the unit's
# staged tree; the only artifacts are the two files this wrapper writes.
# Restrict it to scenarios whose prompt is self-contained (read-only /
# report-style fixtures). A failed call 1 fails the unit without reaching
# call 2: a truncated deliverable must not be self-assessed.
#
# Required env vars (set in backends.json argv via `env`):
#   OLLAMA_MODEL  — model tag (e.g. qwen3:14b)
#   OUTPUT_FILE   — path to write the report artifact
#
# Optional:
#   OLLAMA_HOST        — base URL (default: http://localhost:11434)
#   OLLAMA_TEMPERATURE — temperature (default: 0)
#   OLLAMA_NUM_PREDICT — max tokens (default: 4096)
#   OLLAMA_MAX_TIME    — curl timeout in seconds, per call (default: 600)

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

ARTIFACT_FILE="$(dirname "$OUTPUT_FILE")/artifact.md"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

STAGE1_NOTE='This backend answers the Task in two calls, and this is call 1 of 2. Do step 1 only: follow the skill and produce the deliverable itself — the full text of whatever the Situation calls for. Do not emit the self-assessment report JSON yet; that is call 2.'
STAGE2_NOTE='This is call 2 of 2. The deliverable from call 1 has been saved verbatim as this unit'\''s artifact; assess that text, not what you meant to write. Do step 2 now: self-assess against the numbered items and output only the report JSON object — no prose, no code fences.'

# 設定値・プロンプト・応答本文は Python ソースへ文字列展開せず env / ファイル経由で
# 受け渡す。展開だとモデル応答内の任意テキストがそのまま Python 構文に化ける
send_chat() {
  # $1: messages JSON ファイル、$2: 検証済み応答本文の書き込み先
  local payload
  local response
  payload=$(MESSAGES_FILE="$1" python3 -c '
import json, os, sys

def numeric(name):
    raw = os.environ[name]
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        sys.exit(f"ERROR: {name} must be numeric (got {raw!r})")

with open(os.environ["MESSAGES_FILE"]) as f:
    messages = json.load(f)
print(json.dumps({
    "model": os.environ["OLLAMA_MODEL"],
    "messages": messages,
    "stream": False,
    "options": {
        "temperature": numeric("OLLAMA_TEMPERATURE"),
        "num_predict": numeric("OLLAMA_NUM_PREDICT"),
    },
}))
')
  # -f を付けない: HTTP エラー時も本文（ollama の error JSON）を受けて下段で
  # 内容ごと報告する。-f は本文を捨てるため model not found 等が無言になる
  response=$(curl -s --show-error "${OLLAMA_HOST}/api/chat" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    --max-time "$OLLAMA_MAX_TIME")

  printf '%s' "$response" | CONTENT_OUT="$2" python3 -c '
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
# deliverable, so fail loudly instead.
content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL)
if "<think>" in content:
    sys.exit("ERROR: unclosed <think> block — completion truncated "
             "(raise OLLAMA_NUM_PREDICT)")
if resp.get("done_reason") == "length":
    sys.exit("ERROR: completion hit the num_predict cap — output is truncated "
             "(raise OLLAMA_NUM_PREDICT)")
if not content.strip():
    sys.exit("ERROR: empty completion from ollama")

with open(os.environ["CONTENT_OUT"], "w") as f:
    f.write(content)
print("Wrote %d chars to %s" % (len(content), os.environ["CONTENT_OUT"]),
      file=sys.stderr)
'
}

# call 1: 成果物生成。検証済み本文が artifact.md になる（検証前の応答は書かない —
# 途切れた成果物を実物として残すと、call 2 を止めた意味が消える）
printf '%s' "$PROMPT" | STAGE_NOTE="$STAGE1_NOTE" \
  MESSAGES_OUT="$TMP_DIR/messages1.json" python3 -c '
import json, os, sys
with open(os.environ["MESSAGES_OUT"], "w") as f:
    json.dump([{"role": "user",
                "content": sys.stdin.read() + "\n\n" + os.environ["STAGE_NOTE"]}], f)
'
send_chat "$TMP_DIR/messages1.json" "$ARTIFACT_FILE"

# call 2: 会話を継続して self-assess。assistant turn は artifact.md の実体から積む
# （= 呼び出し側が突き合わせるのと同一のテキストを自己評価させる）
MESSAGES_IN="$TMP_DIR/messages1.json" ARTIFACT_FILE="$ARTIFACT_FILE" \
  STAGE_NOTE="$STAGE2_NOTE" MESSAGES_OUT="$TMP_DIR/messages2.json" python3 -c '
import json, os
with open(os.environ["MESSAGES_IN"]) as f:
    messages = json.load(f)
with open(os.environ["ARTIFACT_FILE"]) as f:
    messages.append({"role": "assistant", "content": f.read()})
messages.append({"role": "user", "content": os.environ["STAGE_NOTE"]})
with open(os.environ["MESSAGES_OUT"], "w") as f:
    json.dump(messages, f)
'
send_chat "$TMP_DIR/messages2.json" "$OUTPUT_FILE"
