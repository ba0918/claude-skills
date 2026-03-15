---
name: issue
description: Issue management for tracking out-of-scope problems discovered during plan execution. Supports create, list, cycle, and close workflows. Use when user wants to record issues, view issue list, convert issues to plan/cycle, or close resolved issues.
---

# Issue Management

Provides a flow to record out-of-scope problems discovered during plan execution as local files in `docs/issues/`, and later connect them to plan → cycle.

## Workflow Selection

The first keyword in the argument determines the workflow:

- `create` → **Create Workflow**
- `list` → **List Workflow**
- `cycle` → **Cycle Workflow**
- `close` → **Close Workflow**

Text after the keyword becomes the argument for each workflow.

---

## Create Workflow

Record a new issue.

### Arguments

- Title (required)
- Summary (optional — defaults to the same as title)
- Tags (optional — comma-separated)
- Source (optional — source plan file path, etc.)

### Steps

1. Parse title, summary, tags, and source from the arguments
2. Create the `docs/issues/` directory (if it doesn't exist, use `mkdir -p`)
3. If `docs/issues/issue-status.md` does not exist, create it with the following template:
   ```markdown
   # Issue Status

   **Last Updated:** {YYYY-MM-DD}

   | Issue | Tags | Created | Summary |
   |-------|------|---------|---------|
   ```
4. Generate the slug:
   - Date: `YYYY-MM-DD` format
   - Remove path separator characters and special characters from the title: slashes (`/`), double dots (`..`), backslashes (`\`), etc.
   - Convert the remaining characters to kebab-case (spaces → hyphens, lowercase, keep only alphanumeric characters and hyphens)
   - Final slug: `{YYYY-MM-DD}_{kebab-title}`
5. Read [references/issue-template.md](references/issue-template.md), replace placeholders, and write to `docs/issues/{slug}.md`
6. Add a row to the end of the table in `docs/issues/issue-status.md`:
   ```
   | [{kebab-title}]({slug}.md) | `{tags}` | {YYYY-MM-DD} | {summary} |
   ```
7. Update **Last Updated** to today's date
8. Display the creation result:
   ```
   ✅ Issue created!
   📄 File: docs/issues/{slug}.md
   📋 Index: docs/issues/issue-status.md
   ```

---

## List Workflow

Display a list of open issues.

### Steps

1. Read `docs/issues/issue-status.md`
   - If it doesn't exist: Display "No issues have been registered yet" and exit
2. Display the table contents as-is
3. Count the table rows and display a summary:
   ```
   📊 Open issues: {N}
   ```

---

## Cycle Workflow

Connect an issue to plan → cycle for resolution.

### Steps

1. Read `docs/issues/issue-status.md`
   - If it doesn't exist: Display "No issues have been registered yet" and exit
2. Use AskUserQuestion to have the user select the target issue (present table contents and ask for slug input)
3. Read the selected issue file (`docs/issues/{slug}.md`)
4. Execute `plan-create` via the Skill tool based on the issue content (title and summary)
   - Arguments: Pass the issue's title and summary
   - **CRITICAL**: The plan file MUST be created at `docs/cycles/{timestamp}_{slug}.md`. Do NOT use `docs/plans/` or any other directory. Verify the file was created in `docs/cycles/` before proceeding.
5. Execute `cycle` via the Skill tool with the created plan
6. If `plan-create` or `cycle` fails, display the error and exit while keeping the issue open
7. After cycle completion, execute `issue` via the Skill tool with `close {slug}` as the argument

---

## Close Workflow

Close (archive) an issue.

### Arguments

- Issue slug (required — if omitted, confirm via AskUserQuestion)

### Steps

1. Get the issue slug from arguments (if omitted, confirm via AskUserQuestion)
2. Verify the issue file `docs/issues/{slug}.md` exists
   - If not found: Display the file list in `docs/issues/` and exit with an error message
3. Create the `docs/issues/archives/` directory (if it doesn't exist, use `mkdir -p`)
4. Move the issue file to `docs/issues/archives/` (using `mv` command)
5. Remove the row containing the slug from `docs/issues/issue-status.md` using the Edit tool
6. Update **Last Updated** to today's date
7. Display the result:
   ```
   ✅ Issue closed!
   📦 Archived: docs/issues/archives/{slug}.md
   📋 Index updated: docs/issues/issue-status.md
   ```

---

## File Structure (generated in the project using this skill)

```
docs/issues/
  issue-status.md             - Index file (LLM reads this first)
  YYYY-MM-DD_<slug>.md        - Individual issue files
  archives/                   - Storage for closed issues
```

## issue-status.md Format

```markdown
# Issue Status

**Last Updated:** YYYY-MM-DD

| Issue | Tags | Created | Summary |
|-------|------|---------|---------|
| [slug](YYYY-MM-DD_slug.md) | `tag` | YYYY-MM-DD | Summary |
```

## Template

- **Individual issue:** [references/issue-template.md](references/issue-template.md)

## Notes

- issue-status.md serves as the index. LLMs can understand the situation by reading just this file without opening all issues
- close = archive. On close, immediately move to `archives/` + remove row from `issue-status.md`
- Do not include sensitive information in issues
