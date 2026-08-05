# Resume Workflow

Reload an existing idea memo and restart the sparring session with it as context. The Session Workflow constraints ([workflow-session.md](workflow-session.md)) apply unchanged (no file edits, no implementation, no choice UI).

## Steps

1. Take the slug from $ARGUMENTS after the `resume` keyword.
   - No slug → read idea-status.md, show the table, and have the user select (if idea-status.md is absent, reply "No ideas yet." and stop).
2. Read `.agents/artifacts/ideas/{slug}.md`; if missing, list `.agents/artifacts/ideas/` and stop with an error.
3. Show the recap and enter the loop:
   ```
   📄 Loaded the idea "{title}".

   ## Previous summary
   {contents of the Summary section}

   ## Open questions
   {contents of the Open Questions section}

   Resuming the sparring session from here!
   ```
4. Initialize `codex_available = true` and `stuck_hint_shown = false`, then run the same sparring loop as Flow steps 3a–3g of [workflow-session.md](workflow-session.md) (stuck detection, Codex second opinion, the failure fallback, and pre-wrap self-review all included), using the previous Open Questions as the primary starting points.
5. On exit, point to Wrap in update mode:
   ```
   Ending the sparring session.
   Run `/claude-skills:brainstorm-wrap` to update the idea memo.
   ```

Wrap after Resume updates the existing memo in place — see "Wrap after Resume" in [workflow-wrap.md](workflow-wrap.md).
