# The fixtures.json schema and design guidelines

The contract of `skills/<skill>/fixtures.json`. A fixture is a regression asset that pins "the behavior this skill must
preserve" in re-runnable form, and it is committed in the same repository as the skill itself.

## Schema

```json
{
  "skill": "sweep-fix",
  "scenarios": [
    {
      "id": "sf-001",
      "title": "Sweeping outward from a single-file finding",
      "source": ".agents/artifacts/plans/20260702143000_sweep-fix.md",
      "executor_tier": "standard",
      "isolation": "worktree",
      "setup": {
        "files": {
          "src/example.py": "def f(x):\n    return eval(x)\n"
        },
        "mtimes": { "src/example.py": -3600 },
        "git": { "init": true, "commit": true },
        "env": { "XDG_STATE_HOME": "./xdg-state" }
      },
      "prompt": "The use of eval in src/example.py was flagged as dangerous. I want to find and fix the same class of problem across the whole codebase.",
      "requirements": [
        { "text": "Turns the finding into a pattern before searching outward", "critical": true },
        { "text": "Judges each detected site with the 3 values CONFIRMED/FALSE_POSITIVE/UNCERTAIN", "critical": true },
        { "text": "Does not include UNCERTAIN sites among the fix targets", "critical": true },
        { "text": "Presents the output of a verification command after fixing", "critical": false }
      ]
    }
  ]
}
```

The CONFIRMED / FALSE_POSITIVE / UNCERTAIN in the example are the vocabulary of
"Three-valued context verification" in [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md)
(when a requirement sentence uses shared vocabulary, write it with the meaning from its definition).

| Field | Required | Meaning |
|-----------|------|------|
| `skill` | ✓ | the target skill name (matching the directory name) |
| `scenarios[].id` | ✓ | a short ID unique within the skill. Keep it stable (it is the tracking key across reports and history) |
| `scenarios[].title` | ✓ | a one-line scenario name |
| `scenarios[].source` | ✓ | where this acceptance criterion came from (the plan doc of a tuning session, or `manual` if hand-designed). A fixture whose provenance cannot be traced cannot be judged stale |
| `scenarios[].executor_tier` | - | `standard` when omitted. `high` = judgment-heavy skill, raise only when standard accuracy falls short and pin the reason in `notes`. `economy` = the scenario's critical requirements are machine-judged (`assert`), so their verdicts are decoupled from the executor's self-report quality — an economy-class executor still has to do the work, but the critical score no longer depends on its judgement; declared only on such scenarios, with the reason in `notes` |
| `scenarios[].isolation` | - | `worktree` (involves creating or editing files) / `none` (read-only or dialogue only). `worktree` when omitted (the safe side) |
| `scenarios[].setup.files` | - | files placed into the worktree before running the scenario (relative path → contents). Effective only when isolation is `worktree` |
| `scenarios[].setup.mtimes` | - | file mtimes (a path from `files` → seconds relative to the reference time; negative is in the past). Needed for skills that use ordering as evidence. They are relative because absolute times go stale as time passes |
| `scenarios[].setup.git` | - | the git state of the isolated area. The keys are in the table below |
| `scenarios[].setup.env` | - | environment variables given to the executor as a premise (name → value). They are not set during materialization; the caller injects them into the prompt |
| `scenarios[].prompt` | ✓ | the situation handed to the executor. Write it as a natural user utterance (never name the skill directly — firing is trigger-eval's domain, and what is measured here is only the quality of body execution) |
| `scenarios[].requirements[]` | ✓ | the requirements the artifact must satisfy. 3-7 items, with at least one `critical: true`. The only keys are `text` / `critical` / `assert` |
| `scenarios[].requirements[].assert` | - | typed predicate objects for machine judgement (see § Machine-judged requirements). When present, the machine verdict replaces the executor's self-report for that requirement |
| `scenarios[].exercises` | - | the behavior-surface files this scenario touches, as a **complete claim** (`SKILL.md` and `fixtures.json` are implicit). Declaring narrows reruns to the scenarios a change actually reaches; omitting it keeps the safe side (always rerun). Semantics, fallbacks, and the guarantee boundary are in [partial-rerun.md](partial-rerun.md) |
| `scenarios[].notes` | - | notes on design decisions (the intent of an edge case, the reason for a tier change, etc.) |

Unknown keys are rejected by validation (at every level: top level, scenario, `requirements`, `setup`, `setup.git`).
Silently ignoring them would skew what is measured in the hardest way to notice — "a premise you believed you declared is
never materialized" — so typos included, they fail as violations.

## Machine-judged requirements (`assert`)

A requirement whose satisfaction is a **post-state property** (file contents, git shape, text
patterns) may declare `assert`: a non-empty list of typed predicate objects. The grader
evaluates them against the unit's staged tree, and the machine verdict is authoritative for
that requirement — the executor's self-report is not consulted, in either direction (#241,
ruling: typed predicate objects; a DSL and per-scenario checker scripts were rejected).

```json
{ "text": ".env is absent from every commit", "critical": true,
  "assert": [ { "type": "git_path_committed", "path": ".env", "expect": false } ] }
```

| Predicate `type` | Required keys | Holds when |
|---|---|---|
| `file_exists` | `path` | the file exists (`expect: false` inverts, here and below) |
| `file_regex` | `path`, `pattern` | the file exists and the regex matches its contents |
| `report_regex` | `pattern` | the executor's report (`report.json` `artifact` field) contains the regex — mechanical judgement of a report-side requirement (`#258`) |
| `git_clean` | — | `git status --porcelain` is empty |
| `git_commit_count` | one of `equals` / `min` / `max` | `git rev-list HEAD --count` satisfies the bound(s) |
| `git_head_equals_baseline` | — | `HEAD` exactly equals the baseline commit SHA captured when the fixture was materialized; a missing baseline fails |
| `git_subject_regex` | `rev`, `pattern` | the regex matches the subject of commit `rev` |
| `git_subjects_regex` | `pattern` (opt. `skip_oldest`) | every commit subject matches, excluding the `skip_oldest` oldest (baseline) commits |
| `git_path_committed` | `path` | the path appears in some commit reachable from HEAD |
| `git_no_commit_touches_both` | `path_a`, `path_b` | no single commit touches both paths |

Rules:

- **Assertion is a change of judgement means, not a relaxation.** The no-easier-editing rule
  above applies unchanged: converting a requirement to `assert` must preserve what it demands,
  and dropping a requirement because it cannot be asserted *is* a relaxation and is forbidden.
  Requirements that are partly semantic (a report must explain something) stay LLM-judged.
- **Asserts are withheld from the executor prompt**, for the same reason as the `critical`
  flags: an executor that can see the predicates optimises for the predicates instead of
  following the skill. The executor still self-reports every requirement.
- **Predicate implementations are fixed code** in the grader (`regression_queue.py`), never
  fixture-supplied: fixtures stay declaration-only and never gain execution rights. Adding a
  predicate type is a code change and passes review like any other guarantee.

## The `economy` executor tier (#258)

A scenario may declare `executor_tier: "economy"` when **every critical requirement is
machine-judged** (an `assert` predicate covers it). The rationale for allowing a cheaper
executor class is that the machine verdict replaces the executor's self-report for those
requirements: the executor still has to do the work, but the critical score no longer
depends on its judgement quality. This is a **decoupling of judgement from self-report**,
not a guarantee of equal task-execution success — a cheaper executor that fails at the
work itself still drops the pass rate, because the machine verdict then judges a missing
artifact.

Measurement to date (2026-08-11): economy-class executors were run on two skills —
`commit` (cm-002/003 are economy-eligible; cm-001 remains `standard`) and
`test-driven-development` (td-001/002/003) — with both Haiku-class and
deepseek-v4-flash executors, all `pass`.
Token-consumption comparison across tiers is not recorded (the runs used different launch
paths with no comparable token accounting). The tier is accepted as generalised to the
`report_regex`-judged scenario shape; a skill whose critical requirements cannot be fully
asserted stays on `standard`.

Rules:

- **Eligibility is per-scenario and mechanical**: every `critical: true` requirement must
  carry an `assert`. Non-critical requirements may stay LLM-judged — the economy tier must
  not be chosen when a critical requirement still depends on executor judgement.
- **`notes` must state the reason** (same rule as `high`): which tier the scenario was
  measured on and when, so a tier change is auditable.
- **The executor contract does not change**: the executor still self-reports every
  requirement and the artifact still has to exist. Economy lowers the *launch* tier, not
  the guarantees a scenario demands.

## Relation to the quality gate contract

The regression ledger (`ledger.json`) is an **internal input to the repository's
canonical verification entry point**, not a review ledger in the sense of the
[quality-gate-contract.md](../../shared/references/quality-gate-contract.md) §4.3
(adjudicated 2026-08-04, issue #243). Its entries bind to skill surface content hashes,
not to a target version × contract version pair; the contract-level verification is the
fact that the canonical entry point (run_checks) passed in full against the exact target
version, and that state is re-earned in full on every run. The ledger's internal
freshness rules (which skills or scenarios need re-running) are therefore the ledger's
own policy, and refining their granularity does not touch §5's convergence accounting.

### The keys of `setup.git`

| Key | Meaning |
|------|------|
| `init` | make the isolated area a git repository. Every other git key requires this |
| `branch` | the initial branch name. `master` when omitted (a fixed value, because leaving it to git's own default makes materialization environment-dependent). Always declare it for skills that branch on the branch name (e.g. commit's ban on committing directly to main/master) |
| `commit` | `true` = create a baseline commit containing every file and leave the working tree clean / an array of paths = commit only those files and leave the rest untracked (declaring "a baseline exists but the working changes are uncommitted") |
| `message` | the message of the baseline commit. `fixture baseline` when omitted. In a scenario measuring "match the style of the existing history", the history's language and form are themselves the premise, so declare it |
| `remote` | the URL of origin |
| `commits` | an array of **further commits stacked after the baseline**, in declared order. Each element is `{ "files": {path: contents}, "message": "..." }`: the files are written into the worktree and committed together under that message. Requires `init` and a baseline `commit`. This is what makes seeded history declarable — see § Seeded history and SHA placeholders |

### Seeded history and SHA placeholders

A fixture that starts a skill **mid-workflow** needs history that already exists: work
committed after the baseline, plus a document pointing at the baseline as the scope
boundary (a plan's `**Implementation Base SHA:**`, a review range, a revert target).
`setup.files` cannot express it, because the SHA only exists once materialization has
run — and "let the executor look the SHA up and write it in" is exactly the
discretion design guideline 8 forbids: when the filling changes, so does the path
being measured.

```json
"setup": {
  "files": {
    ".agents/artifacts/plans/20260801040000_add-normalize.md":
      "...\n**Implementation Base SHA:** {{fixture:sha:baseline}}\n..."
  },
  "git": {
    "init": true,
    "commit": true,
    "commits": [
      { "files": { "app.py": "...", "tests/test_app.py": "..." },
        "message": "feat: implement normalize (TDD)" }
    ]
  }
}
```

| Placeholder | Resolves to |
|---|---|
| `{{fixture:sha:baseline}}` | the 40-hex SHA of the baseline commit (`setup.git.commit`) |
| `{{fixture:sha:commits[N]}}` | the SHA of the `N`-th element of `setup.git.commits`, 0-based |

Substitution runs over the contents of `setup.files` **after every commit is made**,
which fixes the rules around it:

- A file carrying a placeholder must not be part of any commit — neither the baseline
  (`commit: true` commits everything, so such a scenario needs a path list or the file
  under a gitignored root) nor any `commits` element. Rewriting a tracked file after
  committing it would leave the working tree dirty, destroying the very premise the
  seed exists to create. Validation rejects the combination.
- An unresolved placeholder (a typo, an out-of-range index) is a materialization
  error, never a silently literal string: a plan carrying `{{fixture:sha:baseline}}`
  verbatim sends the skill down its "unresolvable base SHA" path instead of the one
  under test.
- The `baseline` hashes returned by materialize are taken from the **substituted**
  file on disk, keeping the "corroborate zero edits against reality, not the
  declaration" rule intact.
- Materialization is **reproducible**: the same declaration always yields the same
  seeded SHAs, and therefore the same substituted contents and `baseline` hashes.
  `regression_queue.py rerun` demands an exact match between the manifest's baseline
  and a re-materialized one, so any wall-clock dependence would make every seeded
  scenario impossible to re-run.
- Reproducibility is bought with a **fixed** author/committer date on every seeded
  commit (`2026-01-01T00:00:00+00:00`), so a scenario must never assume elapsed time
  or a relative period ("committed three days ago", "the last week of history") — the
  seed cannot express it. When a premise genuinely needs time, declare it with
  `setup.mtimes`, which is relative to materialization time by design.

`setup` is materialized by [scripts/fixture_setup.py](../scripts/fixture_setup.py).
Never assemble the isolated area by hand during run / capture — hand assembly is precisely the path by which premises leak
outside the declaration, and the same fixture then runs under different premises each time.

```bash
python3 {skill_dir}/scripts/fixture_setup.py --materialize \
  skills/<skill>/fixtures.json <scenario_id> <dest>
```

The output's `baseline` (relative path → sha256) is used directly for "corroborating zero edits". Take the hashes from
**the reality after writing**, not from the declaration. Transcribe `env` into the environment setup section of the executor prompt.

If the output's `unmaterialized` is non-empty, the declaration and the reality diverge for those paths
(when the execution platform overlays a device file onto `.env` and the like, the write is silently discarded).
A requirement that depends on the contents cannot be written into that scenario — record it in the run report, and if a
requirement assumed the contents, fix the fixture side.

Schema conformance can be checked with `--validate`, and check 17 of `scripts/validate_repo.py` enforces the same validation
in CI over every `skills/*/fixtures.json`.

## Guarantee boundaries: which layer proves what

A multi-stage skill can be measured without re-running every stage. Replacing the
earlier stages with seeded artifacts (a **phase-terminal** fixture: the scenario
starts where the phase under test starts, and ends there) removes the dominant cost —
nested delegation, which stalls and burns the caller's watchdog — but it also moves a
guarantee. Declare where it moved (#242):

| Layer | Proven by | Why there |
|---|---|---|
| workspace lock / worktree isolation / publication transitions / evidence checking | unit tests (`test_workspace_lock.py` and siblings) | mechanism defects are pinned by code plus tests, not by prose or by an LLM run |
| that the phases actually chain into one another | a **through-run smoke, one per skill** | the only live proof of what the seeds skipped |
| phase routing decisions, verdict interpretation, abort conditions, inline fallback | phase-terminal fixtures | LLM judgement itself, which no unit test can pin |

Rules:

- For a multi-stage delegating skill, phase-terminal is the **default** shape, and
  exactly one through-run smoke stays. Do not remove the smoke: phase chaining,
  the delegation relay, and result relay have no substitute in either unit tests or
  terminal fixtures.
- Seeding is a change of *where the scenario starts*, not of what it demands. The
  no-easier-editing rule (guideline 5) applies unchanged: when a rewrite retires a
  requirement because the seed now covers that ground, the requirement moves to a
  named owner and the move is recorded in `notes`, with `source` updated to the
  adjudicating document. Silently dropping it is a relaxation.

## Design guidelines

1. **2-3 scenarios**: 1 at the median of real usage + 1-2 edge cases.
   One overfits, and 4 or more do not pay for the cost of a run
2. **Write requirements in observable form**: not "works correctly" but "the three-valued verdict appears in the output".
   Bring them down to a granularity where ○/× can be decided mechanically from the executor's artifact and report
3. **The criterion for critical**: attach it only to items whose × would collapse the skill's reason to exist.
   Making everything critical means "everything matters = nothing matters" and loses regression resolution
4. **Fix them in advance**: requirements settled in capture are never moved after seeing a run's result.
   Move them only when "the skill specification itself changed deliberately", and in that case
   fix the fixture and redo the capture (updating `source` as well)
5. **Never edit in the direction of making a scenario easier**: simplifying the prompt or dropping a critical because it failed
   is hiding a regression. Separating the cause of the failure (a skill regression or a spec change) comes first
6. **No secrets**: fixtures get committed. Never put real credentials, internal URLs, or personal information into
   setup / prompt
7. **Verify requirement reachability before fixing them**: not only process reachability (is it before the stopping point) but
   also **environment reachability** (does this `setup` actually reach that step) and **contract consistency** (does the
   behavior satisfying the requirement violate another clause of the skill body). The procedure is in
   [requirement-reachability.md](../../empirical-prompt-tuning/references/requirement-reachability.md)
8. **Never depend on a premise `setup.files` cannot express**: `setup.files` holds only "path → contents".
   Premises such as mtime, git state, the **number** of files, and environment variables live outside the schema and get
   filled in at the executor's discretion on every run. When the filling changes, so does the path being measured

### Premises outside `setup.files` (pitfalls found by measurement)

In the batch run of 2026-07-25 (10 skills / 21 scenarios), 5 scenarios failed to take the intended branch. The cause was the
same in every case: **premises other than contents cannot be declared**.

| The premise depended on | What happens | Where to declare it |
|---|---|---|
| mtime ordering of files | generating the setup in one go gives identical mtimes, so even a skill whose primary rule is "mtime descending" only takes the rare tie-break branch | `setup.mtimes` |
| the displayed mtime value | the timestamp column of a listing disagrees with the date in the filename, making the requirement ambiguous | never put displayed values in a requirement. Assert only the ordering |
| the number of target files | early truncation by a cap (e.g. `max_parallel=4`) never fires for lack of files, and passes as ○ while unverified | `setup.files` (place enough files to hit the cap) |
| git state (initial commit / remote) | a requirement of "the working tree is clean" starts out dirty because of untracked files. In a skill assuming a remote, the executor invents a fictitious one | `setup.git` |
| the branch name | `git init`'s default branch becomes main/master, and a skill that stops on the branch name (commit) aborts before reaching the actual subject | `setup.git.branch` |
| the contents of the existing history | "match the style of the existing history" cannot be measured (the history is empty, or is a single harness-default English message) | `setup.git.message` |
| which work is uncommitted | `commit: true` commits every file, so the premise "there are N uncommitted changes" cannot be built | an array of paths in `setup.git.commit` |
| the contents of a file with a sensitive name | the execution platform overlays `/dev/null` onto `.env` and the like, so the declared contents are never materialized (using the declared hash as the baseline judges "zero edits" while it diverges from reality) | cannot be declared. Detect it via `unmaterialized` from `materialize` and make the requirement name/kind-based |
| session debris created by the platform | `.claude/` and `__pycache__` dirty the working tree, and whether the "clean" requirement passes is decided at the executor's discretion (invent an ignore file, or judge it out of scope) | a `.gitignore` in `setup.files` |
| environment variables | the executor guesses the values and fills them in, running under different premises each time | `setup.env` |
| an execution environment where nested delegation works | a multi-stage delegation skill stalls because the delegate's completion notification never reaches the parent | cannot be declared. Follow the environment constraints of [executor-contract.md](executor-contract.md) and build on the assumption of an upper watchdog |

**Guidance when writing a requirement**: confirm that the requirement is determined by the `setup` declarations alone. If it is
not, either reshape the premise into something declarable, or rewrite the requirement so it does not depend on that premise.
"The executor kindly filled it in" also means what you were measuring drifted.

**Unmaterializable premises** (#54): do not disguise an unmaterializable premise as a `setup` declaration.
When a premise can only be conveyed via prompt injection (e.g. "web search is unavailable"), document the
injection contract in `notes` and write requirements that are judgeable regardless of whether the injection
succeeds. A requirement that can only pass when the injected condition holds — but the condition cannot be
enforced — produces a structurally unjudgeable scenario.
For capability constraints (e.g. "Codex is unavailable"), write requirements in branch-tolerant form:
"if available, use real output; if unavailable, show a warning; in either case, do not fabricate".

## Conversion guide by source material

- **From [empirical tuning](../../empirical-prompt-tuning/SKILL.md) measurements**: copy the `scenarios` / `requirements` of the
  `fixture.json` emitted at convergence (`.agents/tmp/empirical/{ts}/fixture.json`) directly into this schema's scenarios /
  requirements. Set `source` to `"empirical-tuning:{ts}"`.
  The checklist at the moment of convergence is the best regression asset (for items moved during tuning, take only the final version)
- **From a plan's acceptance criteria**: convert the "completion conditions" and "verification" sections of the plan document
  into requirements. Take only the items describing properties of the artifact, not the implementation steps
- **Hand-designed**: turn what the skill's description promises into requirements.
  When the description and the body diverge, fix the skill itself before turning it into a fixture

## Coverage tiers

Not every skill is meant to carry a `fixtures.json`. The ledger counts four buckets, and the
distinction between the last two is a declaration, not an accident (#244):

| Tier | Meaning | Where it is declared |
|---|---|---|
| **covered** | Behavioral: fixtures exist and the ledger tracks their verification | `skills/<name>/fixtures.json` |
| **exempt** | The concept of behavioral verification does not apply (shared library, one-shot migration) | `ledger.py COVERAGE_EXEMPT` |
| **static-only** | Deliberately held at static verification: skill-interface-audit + structural sha + trigger-eval | `ledger.py COVERAGE_STATIC_ONLY` |
| **uncovered** | Behavioral verification is intended but not yet built | (the remainder) |

Assignment rules:

- A static-only declaration carries a mandatory reason — an unreasoned entry is the same as
  silently dropping the skill from the count (the coverage-ledger Iron Law).
- A skill that is *planned* to become behavioral but has no fixtures yet stays **uncovered**;
  parking it under static-only would hide a gap behind the word "deliberate".
- Gaining a `fixtures.json` promotes the skill to covered; remove it from
  `COVERAGE_STATIC_ONLY` at that point (a unit test detects stale entries mechanically).
- Tier assignment changes are adjudicated by a human, not inferred by the tooling.
