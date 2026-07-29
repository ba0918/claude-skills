# GitHub issue worktree transport

This workflow is a GitHub-specific adapter around the
[workspace-isolation contract](../../shared/references/workspace-isolation.md) and
[artifact-store contract](../../shared/references/artifact-store.md). It uses the shared ingress,
capability, collect, publish, and cleanup gate; it does not implement a second copy or cleanup
protocol.

The issue workflow chooses the branch point and worktree name. The shared facade then ingresses the
store-relative pinned plan, supplies a capability-file path to the inner cycle, and validates
all returned artifact bytes. The raw capability is never placed in a prompt, artifact, or report.

For every success, implementation failure, cancellation, and verification failure, harvest
precedes cleanup. Collection occurs before merge. Publication occurs only after the existing
post-merge verification and GitHub safety gates pass. Singleton artifact state is composed in the
main tree after publication.

Cleanup is allowed only with transport evidence for published staging, or staging discarded after
explicit human authorization, and a revoked capability. Failure, cancellation, rejection,
reversion, and failed verification never discard automatically and are not cleanup-eligible.
Any conflict, interrupted harvest, failed publication CAS, or missing cleanup evidence preserves
the worktree and invokes the shared exact six-line formatter with a closed reason code. Its final
line is:

```text
/claude-skills:artifacts recover --run-id {satellite_run_id}
```

Recovery never selects a conflict winner and orphan cleanup never overrides this gate.
