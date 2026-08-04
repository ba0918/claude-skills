---
name: loop-triage
description: The loop hub skill that detects repository problems with sensors (validate_repo / ledger --check / context-audit and others), makes findings idempotent, classifies them for admission, and pushes them automatically into the .agents/artifacts/issues/ready/ queue. Only AUTO_FIX-class findings are enqueued, and it carries a self-modification gate that demotes changes touching loop definition files to the inbox when they hold no fixture. Use when the user says "loop-triage", "loop triage", "run the sensors and file issues", "push the findings into the queue", "the loop hub", or "the self-modification gate". It sits upstream of issue polling (the consuming side) as the supplying side. For this repository only.
---

# Loop Triage

Artifact paths follow the [Artifact Store consumer contract](../shared/references/artifact-paths.md). Resolve and validate the store before reading or writing artifacts.

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
- Put intermediate JSON under `.agents/tmp/loop-triage/{datetime}/` (git-ignored)
- The baseline is `.agents/config/loop-baseline.json` (committed; opaque IDs only, contract §3.3)

## Workflow selection

| Input | Workflow |
|------|-------------|
| "triage this" / "run the sensors" (no argument / `run`) | run |
| `--dry-run` | run (skips Step 5 onward and presents only the decisions) |
| `--context-audit PATH` | an option of run (additionally ingests a context-audit findings JSON) |
| `--max-enqueue N` | an option of run (the enqueue cap, default 5) |
| `baseline` ("lock in the current state as an intentional difference") | baseline |
| `status` ("show me the inbox" / "what is the queue like") | status |

run always executes the machine sensors (validate_repo / ledger --check). `--context-audit` is an
**additional** ingestion; there is no restricted mode that targets only the findings of context-audit.

## run — sensors → triage → enqueue

### Step 1: Preparation

```bash
TS=$(date +%Y%m%d%H%M%S)
OUT=.agents/tmp/loop-triage/$TS
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
  --repo-root {repo_root} --baseline .agents/config/loop-baseline.json \
  --out $OUT/decisions.json [--max-enqueue 5]
```

`triage.py` is a thin composition layer; every judgment is made by pure functions (`finding_identity.py` / `admission.py`).
Resolving the affected skills for the self-modification gate is delegated to `skills/skill-regression/scripts/ledger.py --impact`.

### Step 4: Review the decisions

Each entry of `decisions.json`: `{finding, finding_id, route, reason?, gate?, affected_skills?, missing_fixtures?}`.
With `--dry-run`, present a per-route summary here and stop.

### Step 5: enqueue (route = "enqueue" only)

For each enqueue target, generate an issue:

1. slug: `{yyyymmddhhmmss}_{kebab-title}` from suggested_title (timestamp via `date +%Y%m%d%H%M%S`).
   Strip path separators and special characters (`/`, `..`, `\`), then kebab-case (spaces → hyphens,
   lowercase, keep only `[a-z0-9-]`). For a non-ASCII title produce a meaning-based English kebab-title
   (transliteration or translation, whichever yields a readable identifier — never romanize
   character-by-character), then apply the ASCII rules above; if the result is empty use
   `untitled-{short_hash}` (first 8 hex of `echo -n "$title" | sha1sum`). The conversion applies to the
   slug only — the template's title field keeps the original wording. (Provenance:
   [the Slug definition of issue](../issue/SKILL.md#slug-definition) and its Create Workflow step 5,
   quoted in full here; not re-read at runtime for this rule.)
2. Create `.agents/artifacts/issues/ready/{slug}.md` conforming to [issue-template](../issue/references/issue-template.md), with
   the frontmatter as follows:
   ```yaml
   finding_id: {finding_id}          # added as a new key
   tags: loop-triage,{sensor}        # set as the value on the template's existing tags: line (do not add a duplicate line)
   gate: skill-regression            # added as a new key only when decisions carries a gate
   ```
   The body's overview = what + why, and the notes = the acceptance condition (a way to confirm mechanically that the finding is resolved; for example, that the finding_id disappears when the sensor is re-run)
3. Add a row to `.agents/artifacts/issues/issue-status.md` (create it from the issue skill's template if it does not exist.
   Match the Issue column's link to the real file location, `ready/{slug}.md`, rather than leaving the template's example path.
   Use the finding's what (its first sentence) for the Summary column. Escape it: replace every literal `|` with `\|`
   and every newline with a single space; do not truncate (provenance: [issue SKILL.md](../issue/SKILL.md)
   Create Workflow Step 7, stated in full here; not read at runtime).

Run the whole text through a secret check before writing it out — `secret_detect.py` in `{shared_scripts}`
(the `shared/scripts` directory where the skills are installed, as an absolute path; in this repository
`skills/shared/scripts/`) is a module without a CLI, so import `detect_secrets` and apply it
(for example: `python3 -c "import sys; sys.path.insert(0, '{shared_scripts}'); from secret_detect import detect_secrets; ..."`).
On a detection, do not enqueue that finding and demote it to the inbox (reason: "secret-suspect").

### Step 6: inbox (route = "inbox")

Append to `.agents/artifacts/loop/inbox.md` (creating it with the heading `# Loop Inbox` if absent):

```markdown
## {YYYY-MM-DD HH:MM} {finding_id} [{sensor}/{rule}] {suggested_title}
- severity: {severity} / fix_action: {fix_action} / demotion reason: {reason, or "-"}
- where: {where.path}
- what: {what}
- How to handle: a human decides → if it should be handled, file it with `/claude-skills:issue-create`; if it is an intentional difference, send it to loop-triage baseline
```

### Step 7: Report (summary-first)

```
## Loop Triage results
| route | count |
|-------|-------|
| enqueue (pushed into ready/) | N |
| inbox (awaiting human judgment) | N |
| digest | N |
| duplicate / suppressed | N / N |

- Issues enqueued: {list of slugs (state gated ones explicitly)}
- Demoted for exceeding budget: {count, if any}
- Next move: issue polling consumes what was enqueued (/claude-skills:issue-polling)
```

## baseline — fixing the intentional differences

Fix the current findings into the suppress list (contract §3.3; opaque IDs only, intended for a bulk accept on the first run):

```bash
python3 {skill_dir}/scripts/triage.py $OUT/findings-*.json \
  --repo-root {repo_root} --update-baseline .agents/config/loop-baseline.json
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
