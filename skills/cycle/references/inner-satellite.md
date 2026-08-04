# Inner Satellite Mode (per-phase deltas)

Read this file when all four inner satellite fields (`pinned_plan`,
`resolved_isolation=worktree`, `satellite_run_id`, `satellite_capability_file`) are
present and validated. Apply these deltas; every phase otherwise runs normally.

- **Phase 0**: skip workspace claim and release, and the branch precondition. Use
  the validated `pinned_plan` directly — do not auto-select or re-resolve the plan;
  do not create or switch branches or create a nested worktree; the outer
  orchestrator owns the isolation boundary.
- **All phases**: suppress `status.md`, `session-history.md`, and derived-index
  writes. Implementation updates the runtime progress file and the plan's top-level
  Status only; singleton composition belongs to the outer main-tree orchestrator.
- **Phase 1**: append the complete resolved context to the implementation prompt —
  pass the complete satellite context unchanged to `plan-implement`, capability file
  path rather than contents. No delegate may infer, shorten, or re-resolve it.
  Replace "update the runtime
  progress file" in the implement prompt with "update the runtime progress file and
  the plan's top-level Status only; suppress singleton/derived writes; do not claim
  or release a workspace lock and do not resolve isolation — the outer orchestrator
  owns the isolation boundary." (A rule stated only here reaches no delegate: it
  takes effect through this prompt replacement.) Never include
  the raw capability value in any prompt, artifact, or report.
- **Phase 2**: tracked implementation commits remain mandatory — do not skip the
  commit step.
- **Phases 3 and 4**: run normally against the satellite worktree's diff
  (`git diff {cycle_start_sha}..HEAD`); fix commits apply to the satellite worktree.
- **Phase 4 stop paths**: when the final gate stops the cycle (BLOCK / UNVERIFIED,
  or WARN in headless mode), the plan-status revert and the `⛔ CYCLE STOPPED`
  display run as usual, and the inner cycle still returns **stop facts** to the
  outer orchestrator: the stop reason, each arrived review's verdict
  (holistic / independent), and a summary of unresolved findings. Result artifact
  and issue close stay deferred and are never composed on a stop.
- **Phase 5**: defer result-artifact composition and issue close to the outer
  orchestrator; return the completion-relay facts listed in
  [completion.md](completion.md) Step 5.
