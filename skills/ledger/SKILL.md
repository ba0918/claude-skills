---
name: ledger
description: greenfield の要件・仕様・ドメイン知識を人間と裁定し、現在有効な合意を状態付きの台帳として正本化する。仕様の空白を暗黙補完させず、未裁定事項を可視化したいときに使う。workflow は extract / session / status / orient。「合意台帳」「ledger」「裁定セッション」「台帳を作って」「合意を裁定して」「何が決まって何が未裁定か」で起動する。
---

# ledger — Agreement Ledger

Establish the currently valid agreements as a stateful source of truth, so that the LLM never fills the gaps in a specification implicitly.

## Core invariants

- The LLM may be a proposer but never an approver. `AGREED` is generated only from an approval event in which a human explicitly answered a claim at the same revision.
- Only `AGREED` / `DELEGATED` rows may serve as grounds for implementation. Where no agreement exists, surface it as `UNDECIDED`.
- When running headless with no human answer available, extract stops at the draft preview and session stops without any state transition. status remains runnable because it is read-only.

## Workflow routing

Pick exactly one with the first argument.

| Argument | How to run |
|---|---|
| `extract` | Before running, read only [extract-workflow.md](references/extract-workflow.md) in full and follow its procedure |
| `session` | Before running, read only [session-workflow.md](references/session-workflow.md) in full and follow its procedure |
| `orient` | Before running, read only [orient-workflow.md](references/orient-workflow.md) in full and follow its procedure |
| `status` | Completes with the fast path below alone. Do not read any other file, including referenced ones |
| (none) | If no ledger exists, guide the user to extract; if one exists, run the status fast path |

## status fast path

status does not modify the ledger. Because this section contains everything required, emit a short human-facing decision view in the following order without reading the schema source of truth, the vocabulary source of truth, the templates, or any other workflow.

1. 「停止要因」 — high-risk undecided items that block implementation
2. 「高リスク未裁定の上位」 — the top high-risk undecided items
3. 「期限切れ委任」 — expired delegations
4. 「次の一手」 — the next move
5. 「再開地点」 — where to resume

Open with 「未裁定 N 件 / 高リスク M 件」 and defer the full list of agreed items and the history to a detail view. Keep the whole thing within one or two scrolls. Do not expose internal state words as-is: rephrase them for humans, `UNDECIDED` as 「未裁定」 and `DELEGATED` as 「任せた（範囲: …）」. If the input contains no claims, do not invent content — show only the counts and what information is missing.

## Completion

A workflow that makes changes reports the verification commands it ran, their exit codes, the number of detections, the changes made, and any unresolved items. status is read-only and generates neither state transitions nor approval events.
