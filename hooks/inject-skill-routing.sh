#!/bin/sh
# SessionStart hook: ルーティング表を常駐コンテキストへ注入する。
# 本文は rules/skill-routing.md を正本とし、ここでは複製しない。
set -u
table="${CLAUDE_PLUGIN_ROOT:-.}/rules/skill-routing.md"
[ -f "$table" ] || exit 0   # 欠落してもセッション開始を壊さない
cat "$table"
