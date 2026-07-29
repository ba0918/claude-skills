# Execution Context Contract

The rule for determining whether a skill is running in interactive or headless mode.
Several skills branch on this distinction — presenting choices vs aborting, generating
probes vs dropping to UNCERTAIN, requesting confirmation vs continuing silently.
This contract defines the determination once; each skill links here instead of
inventing its own.

> **Consuming skills**: context-audit, plan, refactor, sweep-fix,
> test-driven-development
> (any skill whose workflow branches on interactive vs headless)

## Determination

**A skill runs in headless mode when a confirmation or question to the user would
get no response.** This is the sole criterion. Everything else — who called you,
what flags are set — is evidence toward answering that question, not the question
itself.

Determine the execution context once, at the start of the workflow (Phase 0 or
equivalent), and let every subsequent branch refer to that single determination.

### Observable evidence (non-exhaustive)

The following are common signals. When multiple signals conflict, the one that
most directly answers "will a confirmation get a response?" wins.

| Signal | Points toward |
|--------|---------------|
| Running inside a subagent spawned by cycle, issue-cycle, parallel-cycle, or a polling loop | headless |
| The caller's prompt states that responses will not be delivered | headless |
| The deliverable is specified as a file only (no conversational output expected) | headless |
| Running in a direct user conversation with visible turn-taking | interactive |
| The caller explicitly passes an interactivity flag or parameter | whichever is specified |

### User override

A user may say "don't ask for confirmation" or "just do it" in an otherwise
interactive session. This is **not** a switch to headless mode. The session remains
interactive — confirmation is merely waived for the current request. The
distinction matters: headless-only behaviors (aborting on missing scope, dropping
to report-only, skipping probe generation) should not activate just because the
user asked to skip one confirmation.

Conversely, when a headless caller provides a channel for the agent to ask
questions (e.g. a parent agent that relays queries), the session is interactive
despite being invoked programmatically.

## How skills use this contract

Each consuming skill:

1. Links to this contract from its Phase 0 (or equivalent entry point)
2. States which branches depend on the determination
3. Does **not** redefine the criterion — only applies it

The contract tells you *how to determine the mode*. Each skill's own SKILL.md
tells you *what to do in each mode*.
