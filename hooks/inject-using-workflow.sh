#!/bin/sh
# SessionStart hook: 幹ワークフローの漏斗（ルーティング規律込み）を常駐コンテキストへ注入する。
# 本文は skills/using-workflow/SKILL.md を正本とし、ここでは複製しない。
# frontmatter（先頭の --- ブロック）は注入対象外。
set -u
skill="${CLAUDE_PLUGIN_ROOT:-.}/skills/using-workflow/SKILL.md"
[ -f "$skill" ] || exit 0   # 欠落してもセッション開始を壊さない
awk 'NR==1 && $0=="---" {fm=1; next} fm && $0=="---" {fm=0; next} !fm' "$skill"
