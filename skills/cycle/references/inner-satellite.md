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
  the plan's top-level Status only; suppress singleton/derived writes." Never include
  the raw capability value in any prompt, artifact, or report.
- **Phase 2**: tracked implementation commits remain mandatory — do not skip the
  commit step.
- **Phases 3 and 4**: run normally against the satellite worktree's diff
  (`git diff {cycle_start_sha}..HEAD`); fix commits apply to the satellite worktree.
- **Phase 5**: defer result-artifact composition and issue close to the outer
  orchestrator; return the completion-relay facts listed in
  [completion.md](completion.md) Step 5.
