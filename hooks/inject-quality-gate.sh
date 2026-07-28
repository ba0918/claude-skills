#!/bin/sh
# SessionStart hook: 品質ゲート契約の所在と事前条件の要旨を常駐コンテキストへ注入する。
# 契約本文（約 230 行）は注入しない。skill-routing と違い全文 cat は常駐コンテキスト
# 予算を圧迫するため、正本パスの告知に留める（正本は skills/shared/references/ 側）。
set -u
root="${CLAUDE_PLUGIN_ROOT:-.}"
contract="skills/shared/references/quality-gate-contract.md"
[ -f "$root/$contract" ] || exit 0   # 契約を含まない配布形態ではセッション開始を壊さず沈黙する
profile="skills/shared/references/skill-repository-profile.md"
evidence="skills/shared/references/evidence-format.md"
printf '%s\n' \
  "Quality gate contract (recall pointer): a publish-type state transition (merge / release / distribution) requires valid verification evidence bound to the target SHA and the in-force contract version. Read the canonical sources before publishing:" \
  "- $contract (generic contract)"
[ -f "$root/$profile" ] && printf '%s\n' "- $profile (conformance profile: skill-repository)"
[ -f "$root/$evidence" ] && printf '%s\n' "- $evidence (evidence schema; checker: skills/shared/scripts/evidence_check.py)"
exit 0
