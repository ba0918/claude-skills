---
name: brainstorm
description: アイデアの壁打ちに特化したスキル。発散→収束→plan化の導線を提供する。壁打ち中はファイル編集を一切行わず議論に集中する。「壁打ち」「brainstorm」「アイデア」で起動。
---

# Brainstorm

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

A skill dedicated to idea sparring (壁打ち): discussion only — the agent never drifts into implementation. Session outcomes are persisted as idea memos for later reference.

## Workflow Selection

Decide the workflow from the leading keyword of $ARGUMENTS:

- `wrap` → **Wrap Workflow** (organize & summarize)
- `list` → **List Workflow**
- `plan` → **Plan Workflow** (convert to plan)
- `resume` → **Resume Workflow** (restart from an existing memo)
- (none or a theme string) → **Session Workflow**

---

## Session Workflow

### Constraints

Do not edit, create, or overwrite any file (including notebooks) during the session. Do not generate code, propose implementation work, or start implementation — never say "let me implement this" (explaining concepts in pseudocode is fine).

Allowed: read-only codebase investigation (file reads, pattern search, file listing, read-only shell commands such as `git log`, `git diff`, `ls`), Codex second opinions via a subagent, and dialogue with the user.

### Flow

1. Take the theme from $ARGUMENTS (ask the user if absent).
2. Initialize `codex_available = true` and `stuck_hint_shown = false`. Do not pre-create any state files.
3. Enter the sparring loop:
   a. Receive the user's message.
   b. **Stuck detection** (only while `stuck_hint_shown == false`): if the message contains any of these keywords (substring match, case-insensitive) —
      - Japanese: 「行き詰ま」「わからない」「どうすれば」「手詰まり」「煮詰ま」「堂々巡り」「進まない」
      - English: "stuck", "no idea", "don't know", "dead end", "going in circles"

      then place the following block at the very top of the response generated in step d, and set `stuck_hint_shown = true`. Later keyword hits are suppressed. Fixed output order for the whole response: hint block (if any) → Codex-unavailable notice (if any) → response body → `💡 Codex の視点:` section (if any).
      ```
      💡 行き詰まった時は `/claude-skills:problem-solving` で思考ツールを試せます:
      - `simplify` — 「全ては〇〇の特殊ケース」を見つける
      - `invert` — 前提を反転させてみる
      - `collide` — 無関係な概念を衝突させる
      - `scale` — 極端なスケールでテストする
      - `pattern` — 他ドメインのパターンから学ぶ
      ```
   c. **Codex second opinion** (only while `codex_available == true`): dispatch the Codex subagent with the theme, the user's message, and a 1–3 sentence summary of the discussion so far (use the literal string `（最初のターン、履歴なし）` on the first turn). Prompt: 「以下の壁打ちテーマとユーザーの発言に対して、異なる視点・反論・見落とし・関連するアイデアを提供してください。テーマ: {theme}。ユーザーの発言: {user_message}。これまでの議論: {summary}」. Pass conversation text only — never file-read results.
      - On failure (call errors out, times out, Codex is unavailable in the environment, or the response is empty / malformed): display `⚠️ Codex unavailable — proceeding with Claude only` once in the step-d response (positioned per the fixed output order above), set `codex_available = false`, and skip Codex on later turns. Do not fabricate a Codex opinion.
   d. Generate the response (integrating Codex's opinion when present): question, probe, push back, offer alternative angles. When a Codex opinion exists, append at the end:
      ```
      💡 Codex の視点:
      {Codex の意見の要約}
      ```
   e. Investigate the codebase read-only as needed.
   f. Ask the user for the next input.
   g. When the user says "wrap" / 「まとめて」 / 「終わり」 etc., exit the loop.
4. On exit, show the pointer to Wrap:
   ```
   壁打ちを終了します。
   `/claude-skills:brainstorm-wrap` でアイデアをメモに整理できます。
   ```

**Note**: Response generation and subagent calls cannot run concurrently — call Codex first, then generate the response.

Shared contract details: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Sparring behavior

- Probe with questions (Why? What if? How about?); state concerns frankly; propose alternative approaches; periodically summarize the discussion.
- Back feasibility claims with read-only codebase investigation.
- When the discussion starts converging on a specific technology, check the gravitational pull — ask 「その技術を使わないとしたら、何を解決しようとしてる？」 or 「技術名を抜いても問題を説明できる？」 as questions, not blocks.

---

## Wrap Workflow

### Precondition

If the current conversation contains no sparring session (bare `/claude-skills:brainstorm-wrap`), reply 「壁打ちセッションが見つかりません。先に `/claude-skills:brainstorm テーマ` で壁打ちを行ってください」 and stop.

### Steps

1. Organize the sparring content from the current conversation.
2. Confirm the title and summary with the user. When interaction is impossible, derive them from the conversation and state that assumption in the completion message.
3. Ensure `.agents/artifacts/ideas/` exists (`mkdir -p`).
4. Generate the slug: `yyyymmddhhmmss_{kebab-title}` (`date +%Y%m%d%H%M%S`; kebab-title is a short ASCII translation of the title). If `.agents/artifacts/ideas/{slug}.md` already exists, re-run `date` for a fresh timestamp — overwriting an existing memo is reserved for Wrap after Resume.
5. Create the memo at `.agents/artifacts/ideas/{slug}.md` from [references/idea-template.md](references/idea-template.md).
6. Update `.agents/artifacts/ideas/idea-status.md` (create with this header if absent):
   ```markdown
   # Idea Status

   **Last Updated:** YYYY-MM-DD HH:MM:SS

   | Idea | Tags | Created | Status | Summary |
   |------|------|---------|--------|---------|
   ```
7. Append a row. The link text is the memo's `#` heading title (the human-readable title confirmed in Step 2) — idea-status.md is a derived index and rebuild-index regenerates each row from the memo's `#` heading, so a kebab slug here would flip on every rebuild:
   ```
   | [{アイデアの # 見出しタイトル}]({slug}.md) | `{tags}` | {YYYY-MM-DD HH:MM:SS} | 💡 Idea | {summary} |
   ```
8. Update **Last Updated** to now.
9. Show the completion message, opening with a summary-first block per the [human-readable summary contract](../shared/references/human-readable-summary.md): state the core of the saved idea in 1–2 plain lines and name the open questions left by the session (or 「なし」). No verbatim replay or exhaustive lists:
   ```
   📝 つまり: {保存したアイデアが「つまり何なのか」を、メモを読んでいない人にも
      伝わる平易な 1〜2 行で}。未決定点: {残った論点、なければ「なし」}

   ✅ アイデアを保存しました!
   📄 File: .agents/artifacts/ideas/{slug}.md
   📋 Index: .agents/artifacts/ideas/idea-status.md
   ```

### Security

If the sparring content contains sensitive information, confirm with the user before writing it to the memo. When interaction is impossible and sensitive information is detected, do not write the memo — report that explicit confirmation is required. Keep secret values (tokens, keys, personal data) out of the summary block as well — omit or replace with a category name per the contract's degradation rule.

---

## List Workflow

1. Read `.agents/artifacts/ideas/idea-status.md`; if absent, reply 「まだアイデアがありません」 and stop.
2. Display the table as-is.
3. Show the count:
   ```
   📊 アイデア数: {N}
   ```

---

## Plan Workflow

1. Read `.agents/artifacts/ideas/idea-status.md`; if absent, reply 「まだアイデアがありません」 and stop.
2. Have the user select the target idea. Run the explicit selection step even when only one entry exists (present the table; never silently proceed). When interaction is impossible and exactly one entry exists, present the table, proceed with that entry, and state the assumption; with multiple entries, stop and ask for a selection.
3. Read the idea file.
   - **Title source**: the link text in the first column of idea-status.md (= the memo's `#` heading title; Wrap saves it and rebuild-index regenerates with the same value).
   - **Summary source**: the memo's `## Summary` section body.
4. Run the `claude-skills:plan-create` skill with argument `{Title}: {Summary from idea file}` — plan-create uses $ARGUMENTS verbatim as the What & Why seed.
   - plan-create creates `.agents/artifacts/plans/{new_timestamp}_{kebab-title}.md` (`new_timestamp` is `date +%Y%m%d%H%M%S` at plan-create launch). Keep this path for Steps 4.5 and 7.
   - Suppress plan-create's own completion message — Step 7 is this workflow's single completion message.
4.5. Optional cycle execution:
   - If `--cycle` is present in the original `$ARGUMENTS`: remove the flag, then run `claude-skills:cycle` with the created plan file path as the argument. Skip Step 7 entirely (cycle produces its own completion log).
   - Otherwise continue to Step 5.
5. Archive — run only after confirming the plan file from Step 4 exists (move the file **before** updating its Status):
   - Ensure `.agents/artifacts/ideas/archives/` exists (`mkdir -p`).
   - Move `.agents/artifacts/ideas/{slug}.md` to `.agents/artifacts/ideas/archives/{slug}.md`.
   - Delete the row from idea-status.md and update `Last Updated` to today.
6. In the archived file, change `**Status:** 💡 Idea` to `**Status:** 📋 Planned`.
7. Show the completion message (`{plan path}` is the path kept from Step 4; `{slug}` is the idea memo's filename stem including its timestamp prefix):
   ```
   ✅ アイデアから plan を作成しました!
   📄 Plan: {plan path}
   📦 Archived: .agents/artifacts/ideas/archives/{slug}.md

   ## Next Steps
   1. `/plan-review` で計画をレビュー
   2. `/claude-skills:cycle` でサイクル実行
   ```

---

## Resume Workflow

Reload an existing idea memo and restart the sparring session with it as context. The Session Workflow constraints apply unchanged (no file edits, no implementation).

### Steps

1. Take the slug from $ARGUMENTS after the `resume` keyword.
   - No slug → read idea-status.md, show the table, and have the user select (if idea-status.md is absent, reply 「まだアイデアがありません」 and stop).
2. Read `.agents/artifacts/ideas/{slug}.md`; if missing, list `.agents/artifacts/ideas/` and stop with an error.
3. Show the recap and enter the loop:
   ```
   📄 アイデア "{title}" を読み込みました。

   ## 前回のまとめ
   {Summary セクションの内容}

   ## 未解決の疑問
   {Open Questions セクションの内容}

   ここから壁打ちを再開します！
   ```
4. Initialize `codex_available = true` and `stuck_hint_shown = false`, then run the same sparring loop as Session Workflow steps 3a–3g (stuck detection, Codex second opinion, and the failure fallback all included), using the previous Open Questions as the primary starting points.
5. On exit, point to Wrap in update mode:
   ```
   壁打ちを終了します。
   `/claude-skills:brainstorm-wrap` でアイデアメモを更新できます。
   ```

### Wrap after Resume

When Wrap runs after Resume, it **updates the existing memo in place** (same slug, no new file). The idea-status.md row stays as-is; only **Last Updated** changes.

---

## File Structure (generated in the project using this skill)

```
.agents/artifacts/ideas/
  idea-status.md             - index file
  yyyymmddhhmmss_{slug}.md   - individual idea memos
  archives/                  - store for planned / dropped ideas
```

## Status Types

| Status | Meaning |
|--------|---------|
| 💡 Idea | Sparred, not yet planned |
| 📋 Planned | Converted to a plan |
| 🗑️ Dropped | Abandoned |

## Template

- **Idea memo:** [references/idea-template.md](references/idea-template.md)

## Notes

- idea-status.md is the index — reading it alone gives the full picture.
- Plan / Drop both archive the memo (move to archives/ + delete the table row).
- Keep sensitive information out of sparring memos.
