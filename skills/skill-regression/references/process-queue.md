# Running a Regression Batch as Processes

An alternative dispatch path for the `run` workflow. Scenarios are executed by separate
agent-CLI processes instead of subagents, so a batch spends **no subagent launches** — the
budget that a fan-out regression run otherwise exhausts mid-batch.

The judgement rules are unchanged: [executor-contract.md](executor-contract.md) remains
authoritative for what the executor is told, what it is not told, and how a scenario is
decided. The runner and its schemas are [process-delegation.md](../../shared/references/process-delegation.md).

## When to prefer this path

- The subagent launch budget is exhausted, or the batch is large enough to exhaust it.
- The batch should run unattended, or under Continuous Integration.
- An interrupted batch needs to resume without reconstructing what already finished.

Keep using subagents for a one- or two-scenario check. Building a batch costs more setup than
it saves at that size.

## Workflow

```bash
# 1. Materialise scenarios into a batch (prompts + work queue + manifest)
python3 {skill_dir}/scripts/regression_queue.py build \
  --fixture skills/<skill>/fixtures.json --batch <batch_dir> --repo-root {repo_root}

# 2. Drain the queue
python3 skills/shared/scripts/process_runner.py run \
  --work <batch_dir>/work.jsonl --backends <backends.json> --backend <name> \
  --root <batch_dir> --runtime-root <batch_dir>/runtime

# 3. Reduce the returned reports to a tally
python3 {skill_dir}/scripts/regression_queue.py grade --batch <batch_dir>
```

`--fixture` and `--scenario` are repeatable, so one batch can cover the whole impact list from
`ledger.py --impact`.

## Batch layout

```text
<batch_dir>/
├── work.jsonl              queue consumed by the runner
├── manifest.json           grading key — holds the critical flags and baseline hashes
├── prompts/<unit>.md       one executor prompt per scenario
├── work/<unit>/            the unit's working directory
│   ├── repo/               the materialised scenario (setup.files, git state, mtimes)
│   └── report.json         the artifact
└── runtime/                kill files and child logs
```

Unit id is `<skill>-<scenario_id>`.

The artifact sits **inside** the unit's working directory, not in a shared results directory.
An agent CLI commonly confines writes to its working directory, and a report placed outside it
is unreachable: measured, that cost a full run that exited 0 having delivered nothing. Keeping
the staged tree one level down (`repo/`) stops the report from landing in the tree under
evaluation, where it could break a "clean working tree" requirement.

## What the backend has to grant

The executor reads the target `SKILL.md` and its references from the repository, which is
outside its working directory. That read access is granted in the **backend registry**, not per
unit — it is a permission, and permissions are the operator's (process-delegation.md §5).

`build` cannot verify the grant, and a unit that cannot read the skill fails exactly like a unit
that read it and did badly. Run one unit first and confirm it, before spending a batch.

## What `grade` decides, and what it does not

`grade` reports one of three verdicts per scenario:

| Verdict | Meaning |
|---|---|
| `fail` | A `critical` requirement was self-reported `no` or `partial` |
| `needs_rerun` | The report is missing, unparsable, or does not cover every requirement |
| `unadjudicated_pass` | Nothing mechanical contradicts a pass |

`unadjudicated_pass` is **not** a pass, and the script will not say the word. executor-contract
requires the caller to re-judge any self-report the artifacts fail to corroborate, and a script
cannot read an artifact and decide whether it earns the `yes` the executor gave itself. Before
`ledger.py --update`, corroborate the self-reports against what the unit actually produced.

`needs_rerun` is deliberately distinct from `fail`: a broken harness is not evidence of a broken
skill, and merging the two makes a misconfigured batch look like a regression.

`baseline_drift` lists staged files whose contents changed. It is evidence, never a verdict —
whether an edit is a violation depends on the requirement, not on the scenario. A worktree
scenario may legitimately rewrite everything; a read-only requirement inside one is contradicted
by a single byte. Read the drift against the requirements before accepting a `yes`.

## Comparability

This is a **second execution path**, not a reimplementation of the first. The prompt scaffolding
differs from the subagent path, and the report is JSON rather than prose. Results from the two
paths are not interchangeable evidence about a skill.

When a ledger entry rests on a process-path run, say so in `--note`. A later run on the other
path that disagrees is then a path difference to investigate, not an unexplained regression.

## Limitations

- **Containment is not a sandbox.** The runner keeps queue-supplied paths inside the batch root;
  it does not stop an executor from wandering into a sibling unit's directory. Real confinement
  is whatever the backend's own flags provide.
- **No retries.** A `needs_rerun` scenario is re-run by restoring its working directory
  first, then running the queue again; everything already finished is skipped:

  ```bash
  python3 {skill_dir}/scripts/regression_queue.py rerun --batch <batch_dir> [--unit <id>]
  ```

  `rerun` wipes and re-materialises every unit that has no `report.json` (plus any unit
  named with `--unit`, finished or not), and refuses when the fixture changed since
  `build` — that is a rebuild, not a rerun. Deleting `report.json` by hand is not enough:
  the first run's edits survive in `work/<unit>/`, and re-running on top of them evaluates
  the skill against a contaminated premise (measured: a rerun executor found the previous
  run's implementation already sitting in the seed tree).
