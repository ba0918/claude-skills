# Checkpoint Pattern — Shared Contract

A checkpoint is not a backup of the worktree contents; it is a restore guide used by collating it against the current git state. What it restores are "the details of execution state that reloading the plan does not fill in" — the meaning of the uncommitted dirty state, the judgment of deviation from the plan, and the next move. The bodies of dirty files are already in the worktree, so the checkpoint does not duplicate them.

## Scope and premises

- **Single host, single writer** (the same declaration as polling-pattern). A situation in which several processes write the
  same checkpoint concurrently is out of scope for v1. Writing is done with `mkdir -p` + a temp file → atomic rename.
- **v1 has no hooks; skill discipline only**. For a session that ends without going through an explicit workflow
  (handoff save / plan status update) — a sudden interruption, /clear — no checkpoint is written. This is a known limitation (the v2 scope below).
- The only thing actually emitted in v1 is `owner: manual-session`. For `precompact`, only the classifier is implemented and frozen by a fixture.

## Location and ID grammar

- Path: `.agents/artifacts/plans/checkpoints/{cycle_id}.md` (one file per plan, overwritten in place).
- The checkpoint file itself and everything under `.agents/artifacts/plans/checkpoints/` are **excluded** from the dirty set and the fingerprint calculation (to prevent self-noise).
- v1 accepts only `[0-9]{14}` for `cycle_id` (`re.fullmatch`).
- The contract **reserves only** the `checkpoint_id` grammar `[0-9]{14}(-[a-z0-9-]+)?` for a future parallel-cycle.
  v1 rejects a suffixed form (`-branch` and the like).

## Format (fixed by the contract)

```markdown
---
cycle_id: "20260708012132"
owner: manual-session        # manual-session | precompact (v1 emits manual-session only)
mode: normal                 # normal | degraded (must agree with owner: precompact)
written_at: 2026-07-08T01:30:00+09:00
base_head: abc1234...        # the HEAD sha at the time of writing (hex)
dirty_fingerprint: sha256:...  # porcelain=v1 -z + the full text of diff HEAD + untracked content hash
dirty_files:
  - path/to/file1.py         # machine-generated from porcelain (after passing through secret_detect.mask_secrets)
verify_on_restore:           # a structured array only. The restore side displays it; automatic execution is forbidden
  - cmd: python3
    args: ["-m", "unittest", "skills/shared/scripts/test_checkpoint.py"]
---
## decision
{One sentence on the judgment of deviation from the plan. "none" if there was no deviation}

## evidence
{An observed command plus a timestamp is required. e.g. "Observed 01:25: python3 -m unittest ... exited 0"}

## next
{Exactly one next move}
```

- Free-form md is not adopted, because staleness cannot then be judged mechanically. Fixed keys plus short text only.
- **Mechanical judgment depends on the frontmatter alone**. For the body sections it goes only as far as checking that the headings (`## decision` and so on) exist —
  it does not depend on semantic analysis of the body.
- The degraded variant states `mode: degraded` / `decision: unknown` / `next: reconstruct_from_diff` explicitly
  (blocking the misreading in which a list from git status looks like a record of judgment).

## Pure-function signatures (canonical — SKILL.md only references them)

Every decision routine in `checkpoint.py` is a pure function over string/bytes input. git invocation lives only in the CLI layer (following the DI principle).

| Function | Signature | Role |
|------|-----------|------|
| `compute_fingerprint` | `(porcelain_z: bytes, diff_text: str, untracked_hashes: dict[str,str]) -> str` | Returns `sha256:...`. Excludes everything under `.agents/artifacts/plans/checkpoints/` and sorts entries so it is order-independent |
| `parse_checkpoint` | `(text: str, filename_cycle_id: str) -> CheckpointMeta` (strict) | Detects duplicate keys, list syntax, a malformed delimiter, an unknown owner/mode, a mismatch, or a cycle_id format violation and raises `ParseError` |
| `classify` | `(meta, current_head, current_fingerprint, *, current_dirty_files=None, conflict_marker=False) -> Verdict` | The semantic five-way classification over parsed meta. `conflict_marker` is the input for traces of an overwrite race (in v1 the caller does not set it — see the §trust model below) |
| `build_skeleton` | `(porcelain_z, head, fingerprint, owner, cycle_id, written_at) -> str` | Generates the skeleton of the machine fields (dirty_files already masked). The narrative is filled in afterwards by the LLM |
| `verdict_exit_code` | `(verdict: str) -> int` | The per-verdict exit code the CLI returns to the skill |

- git invocation lives only in the CLI layer, via `subprocess.run([...], capture_output=True, timeout=...)`
  (the timeout is required as a countermeasure to an index-lock hang). **Receive the output as bytes and decode it with `surrogateescape`**
  (do not set `text=True` — it would break the NUL separators of `-z` and non-UTF-8 paths). File I/O uses `with open()`.
- Sibling collection is a **flat listing of `.agents/artifacts/plans/checkpoints/` only** (no recursive walk of all of `.agents/artifacts/plans/`).

### CLI invocation conventions (the discipline on the skill side)

- **Always state `--repo` explicitly** (including `--repo .`). Do not implicitly assume cwd = the target project —
  the script itself lives where the skill is distributed (in this repository `skills/shared/scripts/checkpoint.py`,
  or the plugin cache when used as a plugin), which is not necessarily alongside the target project.
- When the target project differs from cwd, launch the script by **absolute path** and pass
  `--repo {target project root}`. The path given to `--file` must also point into the target project.
- **Generating the checkpoint is the last write of the session**: run the skeleton after every other file write
  (status.md, the handoff body, and so on, tracked or untracked) has been finalized.
  Writing a file after generating it immediately makes the fingerprint stale (the only exclusion is everything under `.agents/artifacts/plans/checkpoints/`).
- classify emits the `dirty_overlap:` line only when there is an overlap (no line means no overlap).

## Normalization of the fingerprint (contract)

- Input: `LC_ALL=C git status --porcelain=v1 -z` (NUL-separated, independent of quoting and locale)
  + the **full text** of `LC_ALL=C git diff HEAD` + a per-file content sha256 for untracked files.
- `--stat` is not used as hash input, because line counts collide (identical stats from different edits give a false valid).
- The **stored** fields are only paths and stats (the diff body is not stored). "No diff body" is a constraint on storage,
  not on hash input.
- Renames (the two-path `-z` form of `R old -> new`), and whitespace / Unicode / newlines inside paths, are handled correctly by the `-z` parse.
- For untracked files, a per-file content sha256 is included in the input (so a content change to an untracked file also falls to stale).
- Sort the entries and exclude everything under `.agents/artifacts/plans/checkpoints/` before hashing (order-independent).

## The restore decision — a parse gate plus a five-way classification

### Phase 0 (the parse gate, always run before classify)

If `parse_checkpoint` detects any of the following, the result is a terminal **conflict** regardless of the HEAD state (it never enters the semantic classification):
frontmatter that does not hold / a missing required key or a duplicate key / an unknown owner or mode / an owner⇔mode mismatch /
a cycle_id format violation / a cycle_id mismatch between the filename and the frontmatter / a malformed hash /
a `verify_on_restore` that is not of `{cmd, args}` structure (a free-form shell string).

The `superseded > conflict` precedence applies only to a parsed checkpoint — a checkpoint whose `base_head` cannot be read
cannot be judged superseded, so this layer separation is a logical necessity.

### Phase 1 (the semantic five-way classification, over parsed content)

| verdict | Condition | Behavior of restore |
|---------|------|-------------------|
| `superseded` | `base_head` ≠ the current HEAD (HEAD moved forward) | Discard the checkpoint and **propose** deletion (with user confirmation; never delete automatically). The commits are ground truth. However, when the current dirty set overlaps `dirty_files`, note that as well (do not silently throw away the context, even right after an amend / rebase / unrelated commit) |
| `conflict` (semantic) | A state that parses but is inconsistent, such as traces of an overwrite race (a written_at / fingerprint different from what was read) | No automatic judgment; consult a human (fail-safe) |
| `degraded` | `owner: precompact` (`mode: degraded`) | Trust nothing but the dirty set and HEAD. State `decision: unknown` / `next: reconstruct_from_diff` explicitly. Not emitted in v1 (only the classifier is implemented, frozen by a fixture) |
| `stale` | HEAD matches & `dirty_fingerprint` ≠ the current value | Treat the narrative as reference material. Reconstruct the state from the current diff |
| `valid` | HEAD matches & the fingerprint matches | Use the narrative as the starting point for restoring. Note that the fingerprint is **change detection, not tamper detection** (anyone with write access to the repo can recompute it), so even at valid the verification-gate is not skipped. verify_on_restore is displayed only |

**Decision precedence (over parsed content)**: `superseded > conflict > degraded > stale > valid`.

### The asymmetry of the callers (contract)

- **plan resume**: the checkpoint is auxiliary information — a parse conflict means "warn, ignore, and continue the normal resume"
  (a broken auxiliary file must not block a healthy resume).
- **handoff restore fallback**: the checkpoint is the only source of information, so a conflict stops for human consultation.

This asymmetry must not be broken.

## The boundary between checkpoint and handoff

| Axis | checkpoint | handoff |
|----|-----------|---------|
| Trigger | Only when ending while dirty (an exit condition) | An explicit save when context is under pressure |
| Lifecycle | One file per plan, overwritten; expires naturally when HEAD advances; restore is read-only | Several per session; deleted after being read on restore |
| Key | cycle_id (a plan sidecar) | A timestamp (per session) |
| Verification | Mechanical staleness judgment via the fingerprint | None (narrative only) |

Even when a checkpoint is read through the handoff restore fallback, **do not delete it** (do not propagate handoff's deletion
semantics to checkpoints). This boundary table is kept as material for the judgment if "integration into the handoff frontmatter" is ever chosen.

## Ownership boundary (four items only)

A checkpoint holds only four things:

1. The uncommitted dirty state (machine-generated `dirty_files` + `dirty_fingerprint`)
2. The judgment of deviation from the plan (`decision`, one sentence)
3. evidence (facts observed in the past — an observed command plus a timestamp is required)
4. next (exactly one next move)

**Do not duplicate** the plan Progress / status.md / result.

### Prohibitions (stated in the contract)

- Transcribing the list of completed steps
- A final result summary
- Transcribing long test logs
- Storing the diff body (it is used as hash input only)

### Separating evidence from verify_on_restore

- `evidence` (facts observed in the past) **requires an observed command plus a timestamp**
  (e.g. `Observed 01:25: python3 -m unittest ... exited 0`).
- `verify_on_restore` (commands that must be re-run after restoring) is a structured array (`{cmd, args}`).
- The restore output labels all evidence **historical** until it is re-verified (preventing a verification-gate violation by structure plus presentation).

## Security conventions (enforced in code, proven by tests)

Following §9 of [design-principles.md](design-principles.md) (single canonical validator, reused everywhere), the following are enforced inside
`checkpoint.py` and proven by `test_checkpoint.py`:

- **Execution**: `verify_on_restore` is structured `{cmd, args}` only; a free-form shell string is forbidden (rejected at parse).
  restore **never executes automatically** at any verdict (display only). In headless environments
  (cycle and polling), not even a confirmation prompt appears — display only. A relaxation premised on "human confirmation"
  is nullified in an unattended loop, so **execution itself is removed from the specification**.
- **Parsing**: PyYAML is not used (structurally eliminating deserialization RCE via `yaml.load` and friends). The strict parser
  does not interpret tags or anchors (every field is strictly validated by an enum or a regex, so a payload is inert and rejected).
  The shared `frontmatter.py` silently overwrites duplicate keys, so it **is not used**.
- **Paths**: `re.fullmatch(r"[0-9]{14}", cycle_id)` is enforced inside parse, and the checkpoint path and the sibling glob are
  confined to `.agents/artifacts/plans/checkpoints/` by realpath containment (rejecting symlinks), following the containment technique of dossier_lint.
- **Secrets**: **the machine field `dirty_files` that `build_skeleton` generates is always passed through `secret_detect.mask_secrets`**
  (a path itself can be a secret — home paths, email patterns). This is enforced in code.
  By contrast, the **narrative bodies of `decision` / `next` / `evidence` are written by the LLM editing directly after skeleton generation**,
  so masking the narrative is **skill discipline, not code enforcement** (SKILL.md instructs the masking) — keep that distinction honest
  (the skeleton masks only the machine fields and the placeholders). The diff body is not stored.
- **Overwrite race**: the anti-overwrite discipline "if the existing checkpoint's written_at / fingerprint differ from what you read,
  do not overwrite — conflict" is, in v1, **skill discipline that leans on the single-writer, single-host premise, not code enforcement**
  (`build_skeleton --output` unconditionally atomic-renames over an existing file).
  `classify`'s `conflict_marker` is the v2 wire point for encoding that detection later; in v1 the caller does not set it
  (only the unittests exercise it, to freeze the classifier's precedence). Extending to multiple writers is a contract-revision-level change (v2).
- **Trust model**: the fingerprint and base_head are **change detection, not tamper detection**. Even at valid, the narrative is
  "the starting point for restoring" and not a substitute for the verification-gate.

## The owner enum (contract)

- The v1 enum has two values: `manual-session` | `precompact`.
- `precompact` is reserved because its verdict semantics (degraded) are already defined (v1 writes only manual-session and does not emit it).
- `cycle-phase2` will be added in v2, when the writer and the verdict behavior arrive together (no pre-reservation of a bare token).
- An unknown owner is a conflict at the parse stage. `mode: degraded` ⇔ `owner: precompact` must agree; a mismatch is a parse conflict.
