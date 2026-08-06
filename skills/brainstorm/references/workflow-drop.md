# Drop Workflow

1. Read `.agents/artifacts/ideas/idea-status.md`; if absent, reply "No ideas yet." and stop.
2. Have the user select the target idea. Run the explicit selection step even when only one entry exists (present the table; never silently proceed).
3. Confirm the drop with the user before acting. Dropping is a human decision: when
   interaction is impossible, do not drop — report that dropping requires explicit
   confirmation and stop.
4. Ensure `.agents/artifacts/ideas/archives/` exists (`mkdir -p`).
5. Move `.agents/artifacts/ideas/{slug}.md` to `.agents/artifacts/ideas/archives/{slug}.md`.
6. In the archived file, change the status line to `**Status:** 🗑️ Dropped`.
7. Delete the row from idea-status.md and set **Last Updated** to the newest remaining
   entry's Created timestamp (the deterministic value rebuild-index produces; with no
   entries left, leave it empty).
8. Show the completion message:
   ```
   🗑️ Idea dropped.
   📦 Archived: .agents/artifacts/ideas/archives/{slug}.md
   ```

The memo itself is preserved in archives/ — a drop removes the idea from the active
index, it does not destroy the record. Restoring is manual: move the file back and set
its status line to the pre-drop value (rebuild-index regenerates the index row).
