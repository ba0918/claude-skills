---
name: decision-journal
description: アーキテクチャ・技術選定の意思決定を判例集方式で記録・聞き取りするスキル。着手前 1 行プロトコル / LLM 選定会話（候補・裁可理由・確信度・再評価条件）の固化 / 判例の考古学的聞き取りを提供する。棄却条件の反証可能化と技術選定の来歴保存が目的で、brainstorm（アイデア発散）や plan（実装計画）とは棲み分ける。「意思決定記録の固化」「技術選定の判例」「decision journal」「なぜこの技術にしたか記録」「棄却条件を残す」で起動。
---

# Decision Journal

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Record and interview architecture and technology decisions as a body of case law.
The skill does not recommend what to decide; it is limited to **rejecting bad bets up front
and guaranteeing falsifiability**. It concentrates on making abandonment conditions
falsifiable, preserving the provenance of a selection, and recording re-evaluation
conditions — it never becomes a recommender.

[decision-protocol.md](../shared/references/decision-protocol.md) is the source of truth for
the decision protocol itself (the three passing conditions, asymmetric design, the close
procedure, and scope). This skill is the front end that applies and records that protocol.
Every record is a forward application of "process hypothesis v1", not a norm; one
forward-recorded entry carries more evidential weight than a backward interview.

## Workflow Selection

The leading keyword of $ARGUMENTS selects the workflow (Hick's Law: keep the choice at four).

- `start` → **Start Workflow** (the one-line pre-commitment protocol; declare the success criterion)
- `capture` → **Capture Workflow** (freeze an LLM selection conversation into a decision record — the main one)
- `interview` → **Interview Workflow** (archaeologically interview a past project for its case law)
- `list` → **List Workflow** (list the recorded decisions)

Decision records are stored under the `decisions` kind of the Agent Artifact Store, at
`.agents/artifacts/decisions/{slug}.md` (`slug` = `yyyymmddhhmmss_{kebab-title}`, where
kebab-title is the meaning of the title rendered in ASCII `[a-z0-9-]`; the title inside the
record may stay in its original language). Resolve and validate the store per the
artifact-store contract before writing (never embed a `docs/` path).

## Safety rules shared by every workflow

Case law and decision records can contain company names and internal circumstances.
Observe the following.

1. **Confirm with the user before writing out**: before writing to a file, ask the user
   whether the content contains confidential information (the same rule as brainstorm's Wrap).
2. **Automatic exclusion of secrets**: while assembling a record from a conversation or
   testimony, exclude anything that looks like a token, credential, private key, or password
   (the fallback for when the user confirmation is skipped).
3. **Interruption path on detection** (do not continue the happy path; three options, per
   Hick's Law):
   - `中断して確認` — show the passage in question and confirm whether to continue
   - `該当欄を除外して続行` — drop only the fields holding the secret-looking value and carry
     on. When the secret maps to no field of the record, this means "include neither that
     value nor any related mention anywhere in the record" (the absence of a matching field
     is not a reason to ignore the detection and continue)
   - `中止` — end without writing anything
4. `decisions/` belongs to the local-visibility artifact store (outside Git), so do not create
   tracked files.

---

## Start Workflow (the one-line pre-commitment protocol)

Before starting a new project or a new technical bet, declare the success criterion and leave
one line behind.

### Steps

1. Get the subject (project name, the content of the bet) from $ARGUMENTS or from the user.
2. Have the user pick one success criterion out of the four categories
   **「遊び / 学習 / 製品 / 事業」** (Hick's Law: four options; the default is 「遊び」 =
   a low-stake exploration). Confirm the scope (個人 Pj / 企業 Pj) here as well
   (default: 個人 Pj).
3. Ask exactly one follow-up question, chosen by the criterion:
   - 「製品」 or 「事業」 → what is the **indispensable condition** for that product to work?
     Will you verify it first with the cheapest end-to-end spike?
   - 「遊び」 or 「学習」 → confirm the investment ceiling (time, money); do not suppress the
     start. Propose a default inferred from the wording of $ARGUMENTS (e.g. 「週末に」 → 2 days;
     with no mention of money, default to 「なし」), and ask only when you cannot infer it.
     Record the ceiling in the 「制約」 field of the selection-time section (the one-line
     closing memo reuses the existing template field — do not add a new one).
4. Only when the higher-level selection drags a language along with it, insert the
   **one dependent-language question**: can you spend long hours with that language, and does
   it become a learning asset?
5. Save to `.agents/artifacts/decisions/{slug}.md` using the minimal form of
   [decision-record-template.md](references/decision-record-template.md) (the selection-time
   section only). Leave the outcome and loss fields empty (append later via capture). Even in
   the minimal form, keep the outcome section's field headings — including 「終了時 1 行メモ」 —
   exactly as the template has them.
6. Completion message (echo the declared success criterion in one line):
   ```
   ✅ 着手前プロトコルを記録しました
   🎯 成功基準: {遊び|学習|製品|事業} — {1 行宣言}
   📄 File: .agents/artifacts/decisions/{slug}.md
   📋 次アクション: 賭けが決したら `decision-journal capture` で結果を追記
   ```

---

## Capture Workflow (freezing an LLM selection conversation — the main one)

A selection conversation where the LLM lists candidates and the user rules on them contains the
raw material of an ADR, but the provenance — who ruled, on what grounds, with how much
confidence — is easily lost. Extract the structure from the conversation and freeze it.

### Steps

1. Identify the target selection conversation (the current conversation, or a specified log).
2. Extract the following from the conversation (**never fill a field by guessing**; for a
   field with no answer, 「復元不能」 is an acceptable formal conclusion):
   - **候補** (every option raised, including the status-quo option and the rejected ones)
   - **制約** (the premises and requirements mentioned in the conversation)
   - **裁可理由** and its **由来** (stated at the time / traces from the time / recalled
     afterwards / inferred now)
   - **確信度** (how certain the decider was. Criterion: an explicit statement of confidence
     = 高 / acceptance with reservation (「まあ〜でいいか」 and the like) = 中 / passive or
     unstated = 低. Never upgrade to 高 a confidence the conversation does not show)
   - **棄却条件・再評価条件** (what observation would make you walk away from this bet; record
     「未設定」 when there is none)
   - **成功基準** (a template header field): if a Start record for the same subject already
     exists under `decisions/`, carry that declaration over. Otherwise record
     「未設定（Start 未実施）」 — do not guess one of the four categories
   - **射程** (a template header field): 「企業 Pj」 when the conversation mentions a company or
     team operation, otherwise the default 「個人 Pj」 (never leave it blank, because the List
     Workflow displays it)
   - **賭け金** (four impact axes): fill an axis **only when the conversation touched it
     explicitly**; mark an untouched axis 「言及なし」 (do not infer it from surrounding
     information). When the conversation supports all four axes being low (small loss ceiling,
     observable exit point, small external impact, no exposure of confidential data), the
     template's "you need not fill every field when the stake is low" rule applies and a
     few lines of memo are enough
   - **各主張の証拠強度**: attach OBSERVED / REPORTED / INTERPRETATION / HYPOTHESIS at the
     moment you write each of the fields above (a selection conversation is usually OBSERVED —
     the log survives)
3. Treat every other template field as **outside Capture's remit**, as follows. Do not fill a
   blank by guessing.
   - **封印セクション**: omit the section entirely (Interview only; per the template's
     "記入の注意")
   - **結果セクション / 判旨・射程・反例**: keep the field headings and leave the contents
     empty (these are appended once the outcome exists; omitting them would delete the place
     the append goes)
4. Apply the shared safety rules. Confirm with the user before writing out, whether or not a
   secret was found. The confirmation shows **the destination path and the list of fields the
   record will carry** (presenting the full text is not required). When a secret is detected,
   replace this confirmation with the three-option interruption path.
5. Once the confirmation passes, save to `.agents/artifacts/decisions/{slug}.md` following
   [decision-record-template.md](references/decision-record-template.md).
6. Completion message (summarise the extracted candidates, ruling rationale, and confidence,
   and show the destination):
   ```
   ✅ 選定会話を決定記録に固化しました
   🧭 候補: {候補一覧}／採用: {採用案}
   📝 裁可理由: {理由}（由来: {当時明示|痕跡|事後回想|推測}・確信度: {高|中|低}）
   🔁 再評価条件: {条件 or 未設定}
   📄 File: .agents/artifacts/decisions/{slug}.md
   ```

**Note**: saving the rationale does not save the provenance — who ruled, on what grounds, with
how much confidence. The value is in **structuring** provenance, the ruling, and the
re-evaluation condition, not in "saving".

---

## Interview Workflow (archaeological interview of a case)

Interview a past project's decisions retrospectively and record them as case law.
[interview-guide.md](references/interview-guide.md) is the source of truth for the technique.
The dialogue can run long, so **save incrementally at every step so it can resume after an
interruption**.

### Steps

1. **Seal the record before interviewing** (follow the interview-guide procedure). Fix the
   hypothesis, the refutation conditions, and the predicted ending before the interview starts,
   and write them out first into the 封印セクション of `.agents/artifacts/decisions/{slug}.md`
   (this blocks retrofitting after collection; never rewrite it, whatever the interview yields).
2. **Start from free recall**. Keep case-law vocabulary (境界, 成立条件, 賭け金 and the like) out
   of your questions and let the person speak in their own words. Do not make the testimony
   converge on the shape of the template.
3. Interview field by field, attaching an **証拠強度ラベル** to each field (OBSERVED /
   REPORTED / INTERPRETATION / HYPOTHESIS; definitions in decision-record-template).
   - **Ask about the reason for stopping and the reason for not resuming separately.**
   - **Do not fabricate a comparison by presenting a list of options** (if the person did not
     compare, record 「比較なし」).
   - For a field with no memory, record 「復元不能」 as a formal conclusion.
   - Restore the template header fields (成功基準, 射程) from the testimony too. For 成功基準,
     adopt the testimony of a declaration made at the time when there is one; otherwise lead
     with 「未設定（Start 未実施）」. Keep an inference from circumstances to a parenthetical
     provisional note and label it INTERPRETATION (「復元不能」 is for when you cannot even
     confirm whether a declaration existed).
4. **Save incrementally at every step and echo the progress** (fields obtained / fields
   remaining), so that an interruption and resumption show how far you got.
5. Apply the shared safety rules (on detecting a secret, take the interruption path).
6. Completion message (present the breakdown of restored fields and 「復元不能」 fields):
   ```
   ✅ 判例を記録しました
   🗂 復元できた欄: {欄名一覧}
   🚫 復元不能: {欄名一覧}（推測で埋めていない）
   🔮 封印予想の的中/外れ: {結末分類の照合結果}
   📄 File: .agents/artifacts/decisions/{slug}.md
   ```

---

## List Workflow

### Steps

1. Enumerate `*.md` under `.agents/artifacts/decisions/` (if there are none, print
   「まだ決定記録がありません」).
2. List each record's title, success criterion, scope (個人/企業), and state.
3. Show the count summary:
   ```
   📊 決定記録数: {N}
   ```

---

## Design policy

- **skills-first**: add no command. The workflow branches on the leading keyword of $ARGUMENTS
  (the same shape as brainstorm).
- **Platform-agnostic**: use no specific tool API name or model name.
- **Not a recommender**: v1 is limited to eliciting constraints, recording abandonment
  conditions, and structuring provenance. Measure capture rate, false-trigger rate, and
  re-evaluation rate before considering making the gate blocking.
- **Boundary with brainstorm / plan**: brainstorm is idea divergence, plan is the
  implementation plan. This skill owns recording, interviewing, and preserving the provenance
  of decisions.
