---
name: handoff
description: セッション間でコンテキストを引き継ぐためのスキル。コンテキストが圧迫されてきた時に save で現在の会話状態をLLMファーストな構造化テキストとして .agents/artifacts/handoff/ に保存し、次セッションで restore で読み込んで作業を継続する。引数で動作モードを切り替え。`save`（デフォルト）/ `restore [path]` / `list`。「handoff」「引き継ぎ」「次セッションに移動」「コンテキスト圧迫」「セッション切り替え」「/clear 前に保存」で起動。
---

# Handoff — Session Context Relay

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Relay the working state to the next session, LLM-first, when context pressure builds up.

## Workflows

The argument selects the mode:

- `save` (default) — dump the current context into `.agents/artifacts/handoff/`
- `restore` — load the latest handoff file, then delete it after reading
- `restore <path>` — restore from the given path
- `list` — list existing handoff files

**Ordering rule (shared by restore and list):** newest first by mtime, comparing full mtime
values (e.g. via `ls --full-time` or `stat`); only when the mtimes are truly identical,
break the tie by the filename-prefix timestamp (`YYYYMMDD_HHMMSS`) descending. Do not treat
a coarse identical `ls` display as a tie.

## Save Workflow

### Phase 1: Sanity Check

1. Create `.agents/artifacts/handoff/` if it does not exist
2. Grab the current branch and git status quickly (`git status --short`,
   `git branch --show-current`)
   - If this is not a git repository / branch lookup fails, set `branch: (none)` in the
     frontmatter. Do not abort on the error

3. **Execution-state checkpoint (primary trigger when ending dirty)**

   handoff save is the **primary trigger** for writing a checkpoint. Follow the shared
   contract [../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md)
   and decide as follows:

   - If the Current Session of `.agents/artifacts/status.md` has an **active plan
     (cycle_id)** and `git status --porcelain=v1` is **non-empty**, generate the checkpoint
     skeleton:
     `python3 {path to checkpoint.py} skeleton --repo {project root} --cycle-id {cycle_id} --owner manual-session --written-at $(date -Iseconds) --output`
     (path and `--repo` conventions per the contract's "CLI 呼び出し規約" — in this
     repository: `skills/shared/scripts/checkpoint.py` + `--repo .`)
   - **Timing**: the decision (active plan + dirty) happens in Phase 1, but run the skeleton
     and fill the narrative **after the Phase 3 handoff file is written** — the checkpoint
     must be the **last write of the session**. Writing any file afterwards (including the
     handoff itself) immediately stales the fingerprint (only `checkpoints/` is excluded).
   - After generating the skeleton, fill only the narrative (`## decision` one deviation
     sentence / `## next` one next move / `## evidence` requires an observed command +
     timestamp). Do not hand-write the machine fields.
   - No active plan / clean tree (empty porcelain) → **do not write** a checkpoint.
   - Checkpoint and handoff are independent (boundary table in the contract). On
     delete/overwrite conflicts, treat as conflict per the contract (if written_at /
     fingerprint differ from what you read, do not overwrite — ask the human).
   - This is separate from saving the handoff file itself (Phases 2–3). Doing both is fine.

### Phase 2: Context Extraction

Look back over the current session and extract all of the following. Do not ask the user —
transcribe autonomously from the conversation history.

Extraction viewpoints:

1. **Original goal** — what the user wanted to achieve
2. **History** — key decisions, attempts, rejected alternatives
3. **Current state** — what is finished, what is mid-flight
4. **Related files** — absolute paths of files read/edited, with their roles
5. **Decisions & constraints** — user instructions, preferences, adopted policies
   (including feedback)
6. **Open issues** — remaining tasks, questions, blockers
7. **Next actions** — what to do first next session (concretely)
8. **Cautions** — pitfalls, things not to do

### Phase 3: File Write

Filename: `.agents/artifacts/handoff/{YYYYMMDD_HHMMSS}_{slug}.md`

- slug: 3-5 kebab-case words describing the work (e.g. `handoff-skill-creation`,
  `auth-refactor-debug`)
- timestamp from `date +%Y%m%d_%H%M%S`

Pick `status` strictly from these 3 values:
- `in-progress` — work continuing (including pauses; any progress counts)
- `blocked` — blocked by external factors (waiting on someone, missing production data, ...)
- `reviewing` — implementation settled; in review/verification

When unsure, use `in-progress`. Do not invent new values.

Template (section headings are part of the artifact format — keep them as-is):

```markdown
---
created: {ISO8601}
branch: {current-branch}
status: {in-progress | blocked | reviewing}
---

# Handoff: {一行サマリ}

## TL;DR
{3-5行。次セッションの Claude が最初に読む部分。目的と現在地を一発で掴ませる}

## 目的 / Why
{ユーザーが達成したいゴールと、その背景}

## これまでの流れ
- {時系列の主要イベント}
- {決定事項と却下した案 + なぜ}

## 現在の状態
### 完了
- {done items}
### 進行中
- {in-progress with具体的にどこまで}
### 未着手
- {todo}

## 関連ファイル
- `/home/user/projects/myapp/src/auth.ts` — {役割・なぜ関連するか}  # 必ず絶対パス（`/` 始まり）。`src/auth.ts` のような相対パスは NG

## 決定事項 / 制約
- {ユーザーの指示・好み・採用方針}

## 未解決の課題
- {open questions, blockers}

## 次のアクション
1. {具体的なステップ}
2. {...}

## 注意点
- {ハマりポイント、やってはいけないこと}
```

### Phase 4: Report

Before the saved path, place a summary block per the
[human-readable summary contract](../shared/references/human-readable-summary.md),
summary-first. State goal / current position / next move in one plain line each (these have
the highest summary value — they drive next-session restore quality). Mark unfillable items
as 「未決定」 and keep secrets out of the summary (defer to the existing handoff-save
confidentiality rule: omit or replace with a category name):

```
📝 つまり:
   ゴール: {何を目指しているか — 1 行}
   現在地: {今どこまで進んだか — 1 行}
   次の一手: {次セッションで最初にやること — 1 行}

保存したよ: .agents/artifacts/handoff/{filename}
次セッションで `/handoff-restore` 叩けばそのまま続きからいけるよ！
```

## Restore Workflow

### Phase 1: File Discovery

- If a path is given in the arguments, use it
- Otherwise pick the newest file under `.agents/artifacts/handoff/` per the ordering rule
  above
- If none exists (including when the directory itself is missing — do not create it;
  restore and list are readers), **try the execution-state checkpoint fallback before
  finishing** (below)

#### Checkpoint fallback (only when there are 0 handoff files)

If even one handoff file exists, behavior is **unchanged** (this fallback does not run).
Only at 0 files:

Follow the shared contract
[../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md).
Here the checkpoint is the **only source of information**, so by caller asymmetry a
`conflict` **stops for human consultation** (unlike plan resume's "ignore and continue"):

- If the Current Session of `.agents/artifacts/status.md` has an active plan (cycle_id) and
  `.agents/artifacts/plans/checkpoints/{cycle_id}.md` exists, run
  `python3 {path to checkpoint.py} classify --repo {project root} --file .agents/artifacts/plans/checkpoints/{cycle_id}.md`
  and branch on the verdict (path and `--repo` conventions per the contract's
  "CLI 呼び出し規約" — in this repository: `skills/shared/scripts/checkpoint.py` +
  `--repo .`). If status.md itself is missing, treat it as no active plan:
  - `valid` / `stale` / `degraded`: present the checkpoint narrative as the restore starting
    point (`evidence` labeled historical; `verify_on_restore` display-only, never
    auto-executed).
  - `superseded`: HEAD has advanced. **Propose** deletion with user confirmation (never
    auto-delete) — the checkpoint stays until the user authorizes deletion. If the
    classify output has a `dirty_overlap:` line, include it (no line = no overlap). The
    narrative (decision / next) may be presented under a "history / reference" label
    (commits are ground truth — say so explicitly, but do not silently drop the context).
  - `conflict` (parse / semantic): **stop for human consultation** (no auto-judgment).
- **Fallback presentation format**: not bound by the Phase 2 fixed template (which is for
  handoff files). A concise structure is fine, led by "this comes from a checkpoint + the
  verdict + next action".
- Even when read via fallback, **never delete** the checkpoint (do not propagate handoff's
  delete-after-read semantics).
- With neither an active plan nor a checkpoint, report 「handoff ファイルが見つからないよ」
  and finish.

### Phase 2: Load & Internalize

1. Read the file
2. Digest it and present a **short summary** to the user, in exactly this Markdown format:

```markdown
## 引き継ぎ内容
- 目的: {1 行}
- 現在地: {branch / status / どこまで進んだか 1-2 行}
- 次のアクション:
  1. {1 行}
  2. {1 行}
  3. {1 行（最大 3 つまで、少なくて OK）}
```

   - `branch` / `status` come from the handoff file's frontmatter (the previous session's
     context), not from the current repository state
   - Synthesize the "どこまで進んだか" line from the TL;DR and 現在の状態 sections
3. Leave the user ready to resume immediately. No extra decoration, no re-listing of
   cautions (they can read the original file if needed)

### Phase 3: Cleanup

**Auto-delete**: as soon as the restore succeeds, delete the file (`rm` or an equivalent
file-deletion operation). No user confirmation.

After deleting, report one line: 「引き継ぎ完了！`{basename}` は削除したよ」
- `{basename}` is the filename only (e.g. `20260421_230133_search-api.md`). No full paths

## List Workflow

List the files under `.agents/artifacts/handoff/` newest first, per the ordering rule
above. Use exactly this numbered Markdown list format:

```markdown
## Handoff 一覧（{件数} 件）

1. **`{filename}`** ({YYYY-MM-DD HH:MM})
   - status: `{status}`
   - TL;DR: {TL;DR 1 行目}
2. **`{filename}`** (...)
   - ...
```

Extraction rules:
- `{TL;DR 1 行目}` = the **first non-empty line** of the `## TL;DR` section after the
  frontmatter (line-based; do not split at punctuation). **Transcribe verbatim** (keep
  punctuation and symbols, including a trailing `。`)
- `{YYYY-MM-DD HH:MM}` is the file's mtime, formatted from the local time shown by
  `ls -lt` (no timezone suffix). Take the year from the first 4 characters of the filename —
  `ls` omits the year for current-year files, so the filename is the stable source
- 0 files → report one line 「handoff ファイルはまだないよ」 and finish
- Do **not** append a how-to-restore hint at the end (answer only if the user asks)

## Design Principles

- **LLM-first**: structured information the next Claude can resume from with minimal
  reading, over human-oriented narrative
- **Autonomous extraction**: never quiz the user during save; transcribe from the
  conversation history
- **Disposable**: delete on restore. Leave no litter in .agents/artifacts/handoff/
- **Absolute paths**: file references are absolute. Do not assume the next session's CWD
