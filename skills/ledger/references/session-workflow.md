# Session workflow

session takes dialogue as its entrance and a ledger state transition as its exit. Assume the human has not read the canon, and present the situation and the recommendation in plain terms. Silence, no reaction to a recommendation, and an LLM's interpretation are not approval.

## 1. Prepare the session

Present in risk order in on-the-spot recording mode, and in narrative order in archaeology mode. In archaeology mode, recover the context with orient and the current-spec reference before adjudicating individual rows.

Open with 3-5 lines explaining the target theme, the number of adjudications, how it will proceed, and that it can be interrupted. Group rows that share the same basis for judgment into one theme, and ask the human only about the next unfilled slot.

- Purpose: the behavior the user observes
- Verdict: adopt or reject
- Scope of application
- Exceptions
- Delegation conditions

Answers are the 4 choices `OK` / `違う` / `任せる` / `保留`. Do not put a default answer on a high-risk row. Save the reason for `違う` in the same answer event, and treat a counterproposal as a new unadjudicated claim. `保留` changes no state.

## 2. Interpret before recording

Only an explicit, direct answer that names the target row goes straight to the recording stage. Use the interpretation confirmation gate for an answer spanning multiple rows, a conditional answer, an ambiguous attitude, a demonstrative, or a delegation answer whose target is not unique.

Before confirmation, all you may present is an "interpretation proposal" for each row and the confirming question. At this stage, do not generate or display the following.

- state transitions, transition arrows, or the post-settlement state
- approval objects, digests, or batch manifests
- expressions that read as already settled, such as "recording it" or "marking it agreed"
- planned records whose value is `AGREED` / `REJECTED` / `DELEGATED`

Instead, state the meaning of the candidate in natural language, as in "is it correct to read UI-042 as OK?". When there is an ambiguous demonstrative or a `任せる`, state explicitly that what it refers to is ambiguous, and only then offer the interpretation proposal. Keep every target row in its current state until the human explicitly confirms the interpretation proposal.

When `任せる` is involved, present once a minimal delegation proposal covering the subject, the target operation, the scope (the current plan by default), the deadline, and revocation, and confirm which row or part of the judgment the delegation applies to.

## 3. Record only after confirmation

Only after the human has confirmed the interpretation proposal, record the confirmed answers into the session artifact. The artifact carries `schema_version`, `session_id`, `responses[{row_id, revision, answer}]`, and, when needed, `reason` and `batch_summary`. Even for answers awaiting confirmation, state in one sentence that the next steps are "human confirmation → generating the session artifact → recording with `ledger_write`".

Pass that artifact to `approve` / `reject` / `batch-approve` of `ledger_write.py`. The CLI never approves on anyone's behalf; it only records the confirmed human answers. Never hand-write a digest or an approval object. Read the structural contract in [agreement-ledger.md](../../shared/references/agreement-ledger.md) only when writing, and verify with `ledger_lint.py` after recording.

At the end of a theme, check for contradictions among the new agreements and against the existing ones. Never mix high-risk rows or rows that drew objections into a batch. On detecting fatigue, interrupt, leave the remainder unadjudicated, and indicate the resumption point.

## Completion

Report the write and lint commands you ran, the exit codes, the detection counts, the state changes, and anything unresolved or on hold. If human confirmation has not happened yet, state explicitly that it is awaiting confirmation and that 0 states changed.
