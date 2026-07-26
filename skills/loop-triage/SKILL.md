---
name: loop-triage
description: リポジトリの問題をセンサー（validate_repo / ledger --check / context-audit 等）で検出し、finding を冪等化・admission 分類して .agents/artifacts/issues/ready/ キューに自動投入するループ中枢スキル。AUTO_FIX 級のみ enqueue し、ループ定義ファイルに触れる変更は fixture 非保有なら inbox に降格する自己修飾ゲートを持つ。「loop-triage」「ループトリアージ」「センサー実行して issue 化」「finding をキューに積んで」「ループ中枢」「自己修飾ゲート」で起動。issue polling（消化側）の上流に位置する供給側。本リポジトリ専用。
---

# Loop Triage

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Supply the findings detected by the sensors into the polling queue safely and without human intervention.
**Shared contract (required reading, direct link):** [../shared/references/loop-engineering.md](../shared/references/loop-engineering.md)

- The Finding Schema, Identity, the Admission table, and the definition of the self-modification gate all live in the contract.
  This SKILL.md is a thin orchestrator and never duplicates the contract
- Where the classification axes are defined: [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md) /
  [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
- The consuming side of the queue is [issue polling](../issue/SKILL.md) (conforming to [polling-pattern.md](../shared/references/polling-pattern.md))

## Invariants (contract §1 / §6)

1. **Triage never fixes anything.** All it produces are issue files, inbox appends, and digests
2. `REPORT_ONLY` is never enqueued under any condition
3. One run enqueues at most `--max-enqueue` (default 5). The excess is demoted to the inbox and reported explicitly (a silent cap is forbidden)
4. Routing follows the judgment of a pure function (`admission.py`). Never promote at the LLM's discretion

## Execution contract

- Call the scripts by absolute path: `python3 {skill_dir}/scripts/<name>.py`. `{skill_dir}` is this SKILL.md's directory and `{repo_root}` is the repository root (usually the cwd)
- Put intermediate JSON under `.claude/tmp/loop-triage/{datetime}/` (git-ignored)
- The baseline is `.claude/loop-baseline.json` (committed; opaque IDs only, contract §3.3)

## Workflow selection

| Input | Workflow |
|------|-------------|
| 「トリアージして」「センサー回して」 (no argument / `run`) | run |
| `--dry-run` | run (skips Step 5 onward and presents only the decisions) |
| `--context-audit PATH` | an option of run (additionally ingests a context-audit findings JSON) |
| `--max-enqueue N` | an option of run (the enqueue cap, default 5) |
| `baseline` (「現状を意図的差分として確定して」) | baseline |
| `status` (「inbox 見せて」「キュー状況は」) | status |

run always executes the machine sensors (validate_repo / ledger --check). `--context-audit` is an
**additional** ingestion; there is no restricted mode that targets only the findings of context-audit.

## run — sensors → triage → enqueue

### Step 1: Preparation

```bash
TS=$(date +%Y%m%d%H%M%S)
OUT=.claude/tmp/loop-triage/$TS
mkdir -p $OUT
```

### Step 2: Run the machine sensors

```bash
python3 {skill_dir}/scripts/sensors.py --repo-root {repo_root} --out $OUT/findings-mech.json
```

Ingesting LLM sensors (opt-in): when `--context-audit PATH` is given, map the context-audit
findings JSON through `sensors.py`'s `map_context_audit` and merge it. **loop-triage never launches
context-audit or the like automatically** (when a sensor runs is up to a human or to each skill's operation).

### Step 3: Triage decision

```bash
python3 {skill_dir}/scripts/triage.py $OUT/findings-*.json \
  --repo-root {repo_root} --baseline .claude/loop-baseline.json \
  --out $OUT/decisions.json [--max-enqueue 5]
```

`triage.py` is a thin composition layer; every judgment is made by pure functions (`finding_identity.py` / `admission.py`).
Resolving the affected skills for the self-modification gate is delegated to `skills/skill-regression/scripts/ledger.py --impact`.

### Step 4: Review the decisions

Each entry of `decisions.json`: `{finding, finding_id, route, reason?, gate?, affected_skills?, missing_fixtures?}`.
With `--dry-run`, present a per-route summary here and stop.

### Step 5: enqueue (route = "enqueue" only)

For each enqueue target, generate an issue following [the Slug definition of issue](../issue/SKILL.md#slug-definition):

1. slug: `{yyyymmddhhmmss}_{suggested_title の英語 kebab 化}` (non-ASCII is translated to English by meaning)
2. Create `.agents/artifacts/issues/ready/{slug}.md` conforming to [issue-template](../issue/references/issue-template.md), with
   the frontmatter as follows:
   ```yaml
   finding_id: {finding_id}          # 新規キーとして追加
   tags: loop-triage,{sensor}        # テンプレート既存の tags: 行に値として設定（行を重複追加しない）
   gate: skill-regression            # decisions に gate がある場合のみ新規キーとして追加
   ```
   The body's overview = what + why, and the notes = the acceptance condition (a way to confirm mechanically that the finding is resolved; for example, that the finding_id disappears when the sensor is re-run)
3. Add a row to `.agents/artifacts/issues/issue-status.md` (create it from the issue skill's template if it does not exist.
   Match the Issue column's link to the real file location, `ready/{slug}.md`, rather than leaving the template's example path.
   Use the finding's what (its first sentence) for the Summary column. The escaping rules for pipes and newlines follow
   [issue SKILL.md](../issue/SKILL.md) Create Workflow Step 7).

Run the whole text through a secret check before writing it out — `skills/shared/scripts/secret_detect.py` is
a module without a CLI, so import `detect_secrets` and apply it
(for example: `python3 -c "import sys; sys.path.insert(0, 'skills/shared/scripts'); from secret_detect import detect_secrets; ..."`).
On a detection, do not enqueue that finding and demote it to the inbox (reason: "secret-suspect").

### Step 6: inbox (route = "inbox")

Append to `.agents/artifacts/loop/inbox.md` (creating it with the heading `# Loop Inbox` if absent):

```markdown
## {YYYY-MM-DD HH:MM} {finding_id} [{sensor}/{rule}] {suggested_title}
- severity: {severity} / fix_action: {fix_action} / 降格理由: {reason または "-"}
- where: {where.path}
- what: {what}
- 対応方法: 人間が判断 → 対応するなら `/claude-skills:issue-create` で issue 化、意図的差分なら loop-triage baseline へ
```

### Step 7: Report (summary-first)

```
## Loop Triage 結果
| route | 件数 |
|-------|------|
| enqueue（ready/ へ投入） | N |
| inbox（人間判断待ち） | N |
| digest | N |
| duplicate / suppressed | N / N |

- enqueue した issue: {slug のリスト（gate 付きは明示）}
- budget 超過による降格: {あれば件数}
- 次の一手: enqueue 分は issue polling が消化する（/claude-skills:issue-polling）
```

## baseline — fixing the intentional differences

Fix the current findings into the suppress list (contract §3.3; opaque IDs only, intended for a bulk accept on the first run):

```bash
python3 {skill_dir}/scripts/triage.py $OUT/findings-*.json \
  --repo-root {repo_root} --update-baseline .claude/loop-baseline.json
```

Before running it, always confirm with the user and obtain approval for how many findings are to be baselined (never baseline in a self-driving context).

## status — taking stock

- Present the number of unprocessed entries in `.agents/artifacts/loop/inbox.md` (a `## ` heading = one entry; treat all of them as unprocessed) together with
  the counts under `.agents/artifacts/issues/ready|running|failed` (a directory that does not exist counts as 0)
- Count issues carrying a `finding_id` (those originating from loop-triage) separately from the rest
- Read-only (never create, change, or delete a file). The report format conforms to the same
  summary-first shape as run Step 7 (a table plus a one-line summary)

## Preventing rationalization

| Excuse | Reality |
|--------|------|
| "This finding is obviously fixable, so let us enqueue it even though it is NEEDS_JUDGMENT" | Promotion is forbidden (contract §4, invariant 2). If judgment is required, the inbox is the right place |
| "The skill has no fixture, but the change is minor, so let it through" | The gate demotion is decided mechanically by whether a net exists. Judging whether something is minor is exactly a human's job |
| "It is all digests and there are no results, so let us loosen the threshold" | The result is not the number of queue insertions but a supply with zero false positives. If you loosen it, do so explicitly as a revision of the contract |
| "It looks like a duplicate but differs slightly, so let us insert it" | If the finding_id differs it gets inserted. The same ID is a duplicate — there is no room to hesitate |
