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
| `scenarios[].executor_tier` | - | `standard` when omitted. When raised to `high`, write the reason in `notes` |
| `scenarios[].isolation` | - | `worktree` (involves creating or editing files) / `none` (read-only or dialogue only). `worktree` when omitted (the safe side) |
| `scenarios[].setup.files` | - | files placed into the worktree before running the scenario (relative path → contents). Effective only when isolation is `worktree` |
| `scenarios[].setup.mtimes` | - | file mtimes (a path from `files` → seconds relative to the reference time; negative is in the past). Needed for skills that use ordering as evidence. They are relative because absolute times go stale as time passes |
| `scenarios[].setup.git` | - | the git state of the isolated area. The keys are in the table below |
| `scenarios[].setup.env` | - | environment variables given to the executor as a premise (name → value). They are not set during materialization; the caller injects them into the prompt |
| `scenarios[].prompt` | ✓ | the situation handed to the executor. Write it as a natural user utterance (never name the skill directly — firing is trigger-eval's domain, and what is measured here is only the quality of body execution) |
| `scenarios[].requirements[]` | ✓ | the requirements the artifact must satisfy. 3-7 items, with at least one `critical: true`. The only keys are `text` / `critical` |
| `scenarios[].notes` | - | notes on design decisions (the intent of an edge case, the reason for a tier change, etc.) |

Unknown keys are rejected by validation (at every level: top level, scenario, `requirements`, `setup`, `setup.git`).
Silently ignoring them would skew what is measured in the hardest way to notice — "a premise you believed you declared is
never materialized" — so typos included, they fail as violations.

### The keys of `setup.git`

| Key | Meaning |
|------|------|
| `init` | make the isolated area a git repository. Every other git key requires this |
| `branch` | the initial branch name. `master` when omitted (a fixed value, because leaving it to git's own default makes materialization environment-dependent). Always declare it for skills that branch on the branch name (e.g. commit's ban on committing directly to main/master) |
| `commit` | `true` = create a baseline commit containing every file and leave the working tree clean / an array of paths = commit only those files and leave the rest untracked (declaring "a baseline exists but the working changes are uncommitted") |
| `message` | the message of the baseline commit. `fixture baseline` when omitted. In a scenario measuring "match the style of the existing history", the history's language and form are themselves the premise, so declare it |
| `remote` | the URL of origin |

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

## Conversion guide by source material

- **From [empirical tuning](../../empirical-prompt-tuning/SKILL.md) measurements**: copy the `scenarios` / `requirements` of the
  `fixture.json` emitted at convergence (`.claude/tmp/empirical/{ts}/fixture.json`) directly into this schema's scenarios /
  requirements. Set `source` to `"empirical-tuning:{ts}"`.
  The checklist at the moment of convergence is the best regression asset (for items moved during tuning, take only the final version)
- **From a plan's acceptance criteria**: convert the "completion conditions" and "verification" sections of the plan document
  into requirements. Take only the items describing properties of the artifact, not the implementation steps
- **Hand-designed**: turn what the skill's description promises into requirements.
  When the description and the body diverge, fix the skill itself before turning it into a fixture
