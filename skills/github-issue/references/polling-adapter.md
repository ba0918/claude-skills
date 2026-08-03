# Polling Adapter (Label-based)

The implementation specification of the Label state adapter of `skills/github-issue/`. It implements the state adapter interface of the shared contract [`skills/shared/references/polling-pattern.md`](../../shared/references/polling-pattern.md) with GitHub labels.

> **Heading Convention:** major sections use H2 (`##`), and subsections such as Interface methods use H3 (`###`), in this file and in every split reference file below. Section anchors elsewhere in the repository depend on these heading strings — do not rephrase them.

---

## Assumptions

This adapter presumes **a single host, a single process, a Ralph loop**.

- **Why a single host is presumed**:
  - A claim spans a mixed consistency domain of "a local lockfile + a GitHub label", and exclusion across several hosts grounded only in GitHub labels leaves a post-verify race
  - Because retry state is persisted on the FS (`<state_root>/retry/{N}.json`), polling the same repo from several hosts makes the state inconsistent
- **Unsupported**: distributed polling from several hosts, Windows native (WSL is unsupported over a DrvFs mount)
- **Supported**: the local filesystems of Linux / macOS (ext4, btrfs, xfs, apfs)

If multi-host support becomes necessary, perform "a redesign that moves the source of truth to the GitHub side" in Phase C.

---

## Interface Table

All 13 methods of the shared contract [§3 Interface Table](../../shared/references/polling-pattern.md#3-interface-table-the-state-adapter-contract) are implemented. The table below is the detailed implementation mapping of the Label adapter.

| Interface (§3) | The Label adapter implementation |
|---|---|
| `list_ready(limit)` | §`list_ready(limit)` |
| `claim(slug)` | §`claim(slug)` |
| `release(slug)` | §`release(slug)` |
| `mark_done(slug)` | §`mark_done(slug)` |
| `mark_failed(slug, kind)` | §`mark_failed(slug, kind)` |
| `retry_count(slug)` | §`retry_count(slug)` |
| `increment_retry(slug)` | §`increment_retry(slug)` |
| `kill_file_path()` | §`kill_file_path()` |
| `archive_month_boundary()` | §`archive_month_boundary()` |
| `rollback_orphans(now)` | §`rollback_orphans(now)` |
| `sanitize_slug(raw)` | §`sanitize_slug(raw)` |
| `load_session()` | §`load_session() / save_session(session)` |
| `save_session(session)` | §`load_session() / save_session(session)` |

### list_ready(limit)

The `list_ready(limit)` requirement of shared contract §3 mandates **early termination** (a full scan is forbidden; return as soon as `limit` entries are found). The Label adapter satisfies the early-termination contract with a server-side limit in one `list_issues` operation and a client-side filter (no re-fetch).

Fetch with one `list_issues` operation: label `claude-auto`, state open, fields number/title/labels/author/authorAssociation/body/stateReason, limit `{limit}`.

`body` and `stateReason` ride along in the **same single call** — they add no API round trip. `body` feeds the Gate 0a / Gate 1 filters below; `stateReason` is carried through to the plan builder for Gate 2 (§Self-Drive Gates).

1. The client-side filter, applied in this order (cheap and local first, the external oracle last):
   - Carries `claude-running` → exclude
   - Carries `claude-review` → exclude (a running substate)
   - `state_of_failure(labels) is not None` → exclude (see §Label Mapping)
   - `authorAssociation` is not contained in `require_author_association` → exclude
   - **Gate 1**: `parse_self_drive_verdict(body) != ALLOWED` → exclude (§Self-Drive Gates)
   - **Gate 0a**: `parse_change_targets(body)` is `MISSING`, or `gate_0_decision(...)` is `REJECT` → exclude (§Self-Drive Gates)
2. Every exclusion above is a **quiet skip**: no label is written, no failure is recorded, and `failed_streak` is not incremented. A Gate 0 / Gate 1 exclusion says the issue body does not meet the self-driving contract — that is a defect in how the issue is written, not a failure of this run
3. **Do not re-fetch even when the post-filter count is below `limit`** (re-fetch on the next tick. This prevents a fetch storm from repeated fetching. Propagation of stale state stays bounded by `tick_interval_loop_mode = 30s`)
4. The return value is a `list[Slug]` in the form `slug = f"issue-{number}"`

### claim(slug)

The 3 layers of defense are hidden as **an internal implementation detail of the adapter**. SKILL.md only calls `claim(slug)`.

For details see §`claim() 3 Layers of Defense`. On failure it returns `ClaimFailed{reason}` and quietly aborts (no retry).

**Input validation**: the part of the slug after `issue-` must match the regular expression `^[1-9][0-9]*$` **as a raw string**. Anything else (non-numeric, negative, zero-padded, `0`) is `fail_closed("invalid issue_number")`. Applying the pattern after `int()` would not do: the conversion normalizes `007` to `7`, so a zero-padded slug would pass a check placed downstream of it. `invalid issue_number` is the single failure identifier for this gate — the same string appears in [SKILL.md](../SKILL.md)'s pre-check so that one search finds every occurrence.

### release(slug)

Call `edit_issue_labels(${N}, add=[], remove=["claude-running"])`, then
`remove_issue_actor(${N})`.

Executed best-effort. Even on failure, only a warning is logged and processing continues (the next tick's `rollback_orphans()` reclaims it).

### mark_done(slug)

Execute the 3 steps **in this order**. A failure at any step is recovered by the next tick's `rollback_orphans()` step ⑤ (cleaning up leftover labels on closed issues).

1. `merge_pr(<PR>, strategy="squash", delete_branch=true)`
2. `close_issue(${N})`
3. `edit_issue_labels(${N}, add=[], remove=["claude-auto", "claude-review", "claude-failed-transient", "claude-failed-permanent", "claude-failed"])`

A partial failure (for example, close succeeded and the label cleanup failed) is detected as "a closed issue with a `claude-*` label" by the next tick's `rollback_orphans()` step ⑤ and cleaned up.

### mark_failed(slug, kind)

**An atomic dual-write of the new and old labels in one `edit_issue_labels` operation, plus verification, plus a recovery marker.**

```
mark_failed(slug, kind) -> Result:
  labels_add = ["claude-failed-transient", "claude-failed"] if kind == TRANSIENT
               else ["claude-failed-permanent", "claude-failed"]

  for attempt in [1, 2, 3]:  # up to 3 times, backoff intervals 0s/1s/2s
    try:
      edit_issue_labels(${N}, add=labels_add, remove=[])
      labels_now = get_issue(${N}, fields=["labels"]).labels
      if all(L in labels_now for L in labels_add):
        record_fs_state(slug, kind)  # completes in the same tick as the FS retry state update
        return Ok
    except GhApiError as e:
      if attempt == 3: break
      sleep(attempt - 1)  # 0s, 1s, 2s

  # every attempt failed — return the claim to ready with a compensating action
  # Crash-safe ordering invariant:
  #   CA-1: persist the recovery marker to the FS with write_atomic (before release)
  #   CA-2: release(slug) removes claude-running / the assignee
  # With this order, even a crash between CA-1 and CA-2 is always reclaimed via the marker.
  # In the reverse order (release → marker), a failed marker write after release leaves
  # 0 labels and no marker, making it untraceable.
  warn_log(f"[mark_failed] verification failed after 3 attempts: {slug}")
  try:
    record_recovery_marker(slug)   # CA-1: persist the FS marker with write_atomic
  except FsError:
    fail_closed("cannot write recovery marker — polling abort")
  release(slug)                    # CA-2: remove the label/assignee on GitHub (best-effort)
  return Err("dual_write_failed")  # picked up by rollback_orphans() step ④ on the next tick
```

**The permitted intermediate states**:
- On the adding side: 0 labels (everything failed, with a recovery marker) or 2 labels (normal). A 1-label state is detected by the verification and retried
- **Never leave 0 labels unattended**: when the verification ultimately does not pass, always place a `<state_root>/recovery/{N}` marker so the next tick's `rollback_orphans()` re-evaluates it

### retry_count(slug)

**Reads the FS state**: read `<state_root>/retry/{issue_number}.json` and return `{retry_count, last_failed_at, run_id}`.

- No file → `0` (treated as the first time)
- JSON parse failure → a warning log, quarantine the file by renaming it to `<issue_number>.json.corrupt.{ts}`, and `0` (recreated)
- On **2 consecutive parse failures** (a new write after quarantine also fails to parse), `fail_closed("retry state corruption")` aborts polling
- The `run_id` field is in UUID v4 form; on read it is strictly validated against the regular expression `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`, and on a mismatch it is warned about and ignored (reading the other fields continues)
- **`retry_count` type/range validation**: it must be `int >= 0` and `< 10000`. A non-integer, a negative value, or 10000 and above produces a warning log and `0` (recreated, preventing a maliciously large written value from falsely triggering `should_promote_to_permanent`)
- **`last_failed_at` format validation**: an ISO8601 form (`YYYY-MM-DDTHH:MM:SSZ` and the like). On a parse failure it is warned about and treated as `null` (retry_count is retained)

### increment_retry(slug)

**Updates the FS state**: follow the `write_atomic` procedure of `.tmp` → fsync → rename → parent fsync. On the single-process premise, the atomicity of the read-modify-write is protected by flock.

- Posting a comment is **abolished** (eliminating both the race condition and the trust-boundary bypass)
- Returns the new count value

### kill_file_path()

Returns the absolute path pair `(<state_root>/.STOP.hard, <state_root>/.STOP)` (**the return order is the check order**, hard takes priority. Conforms to shared contract §3). For resolving `state_root`, see §`state_root Resolution`.

### load_session() / save_session(session)

The tick session of shared contract §6.5. Read and write `<state_root>/session.json` with the `write_atomic` procedure (§Platform Assumptions). A parse failure follows the same quarantine-rename convention as the FS Retry State (`.corrupt.{ts}`) and is treated as `None`.

### archive_month_boundary()

**A no-op on GitHub** (close is equivalent to archiving). The `<state_root>/.last_archive_month` cache is still updated (preserving the unchanged invariant of shared contract §9).

### rollback_orphans(now)

Executed in 5 stages. Each stage is decomposed into a `_check_*()` private submethod. For details see §`rollback_orphans Sub-Steps`.

### sanitize_slug(raw)

Merely calls `sanitize_slug` from the shared contract [§4 Pure Function Signatures](../../shared/references/polling-pattern.md#4-pure-function-signatures).

The Label-adapter-specific `sanitize_repo_slug` coexists with it, dedicated to the `nameWithOwner → path segment` conversion. **The canonical description of the responsibility split is placed in exactly one location, [`cleanup-spec.md`](cleanup-spec.md#sanitize_slug-vs-sanitize_repo_slug-responsibility-separation)**, and this file holds only a link reference to it (preventing a DRY violation).

---


## Split Reference Files

The remaining sections live in one file per concern. Load only the file the current step
names — never this whole set. Heading strings are moved verbatim, so every existing
section anchor resolves inside its new file.

| File | Sections | Read by |
|---|---|---|
| [label-mapping.md](label-mapping.md) | Label Mapping (canonical SSOT), state_of_failure precedence | list workflow, label-spec |
| [self-drive-gates.md](self-drive-gates.md) | Self-Drive Gates, verdict/targets parsing, Gate 0b | polling step 7, cycle step 3, create (via label-spec) |
| [state-root.md](state-root.md) | state_root resolution, platform assumptions, `.polling-initialized` | polling step 2 |
| [error-kinds.md](error-kinds.md) | FS retry state, error_kind enum and handling rules | polling step 11, cycle, codex-review-loop |
| [adapter-internals.md](adapter-internals.md) | claim() 3 layers of defense, rollback_orphans sub-steps, parallel precedence pointer | polling steps 4 and 8 |
