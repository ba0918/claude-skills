---
name: issue
description: Issue management for tracking out-of-scope problems discovered during plan execution. Supports create, list, plan, cycle, and close workflows. Use when user wants to record issues, view issue list, create a plan from an issue, convert issues to plan/cycle, or close resolved issues.
---

# Issue Management

Provides a flow to record out-of-scope problems discovered during plan execution as local files in `docs/issues/`, and later connect them to plan → cycle.

## Slug Definition

The **slug** is the canonical identifier for an issue. It always includes the timestamp prefix:

```
{yyyymmddhhmmss}_{kebab-title}
```

Generate the timestamp with: `date +%Y%m%d%H%M%S`

Example: `20260323143000_fix-login-timeout`

All workflows use this full slug (with timestamp prefix) when referencing issues. Partial matches (without timestamp prefix) are not supported — always use the complete slug.

## Workflow Selection

The first keyword in the argument determines the workflow:

- `create` → **Create Workflow**
- `list` → **List Workflow**
- `plan` → **Plan Workflow**
- `cycle` → **Cycle Workflow**
- `close` → **Close Workflow**

Text after the keyword becomes the argument for each workflow.

---

## Create Workflow

Record a new issue.

### Argument Format

```
create "Title" [--summary "Description"] [--tags "tag1,tag2"] [--source "path"]
```

- **Title** (required): The first argument. Quotes are optional for single-word titles.
- **--summary** (optional): Detailed description. Defaults to the same as title if omitted.
- **--tags** (optional): Comma-separated tags.
- **--source** (optional): Source plan file path, etc.

If arguments are given as free-form text without flags, extract title from the first phrase, and infer summary, tags, and source from context.

### Steps

1. Parse title, summary, tags, and source from the arguments
2. **Preview & confirmation** — Use AskUserQuestion to present the following and obtain user approval before proceeding:
   - Parsed fields: title, summary, tags, source
   - `docs/issues/` directory existence check result
   - If `docs/issues/issue-status.md` exists, check for existing issues with similar titles and list them (if any)
   - Options: "Create" (proceed) / "Cancel" (abort)
   - If the user selects "Cancel", display "Issue creation cancelled." and exit
3. Create the `docs/issues/` directory (if it doesn't exist, use `mkdir -p`)
4. If `docs/issues/issue-status.md` does not exist, create it with the following template:
   ```markdown
   # Issue Status

   **Last Updated:** {YYYY-MM-DD HH:MM:SS}

   | Issue | Tags | Created | Summary |
   |-------|------|---------|---------|
   ```
5. Generate the slug:
   - Timestamp: `yyyymmddhhmmss` format (`date +%Y%m%d%H%M%S`)
   - Remove path separator characters and special characters from the title: slashes (`/`), double dots (`..`), backslashes (`\`), etc.
   - Convert the remaining characters to kebab-case (spaces → hyphens, lowercase, keep only alphanumeric characters and hyphens)
   - Final slug: `{yyyymmddhhmmss}_{kebab-title}`
6. Read [references/issue-template.md](references/issue-template.md), replace placeholders, and write to `docs/issues/{slug}.md`
7. Add a row to the end of the table in `docs/issues/issue-status.md`:
   ```
   | [{slug}]({slug}.md) | `{tags}` | {YYYY-MM-DD HH:MM:SS} | {summary} |
   ```
8. Update **Last Updated** to today's date
9. Display the creation result:
   ```
   ✅ Issue created!
   📄 File: docs/issues/{slug}.md
   📋 Index: docs/issues/issue-status.md
   💡 Tip: `/claude-skills:issue-list` で現在の issue 一覧を確認できます
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
4. If open issue count exceeds 10, display a warning:
   ```
   ⚠️ Open issues: {N} — 未使用の issue がないか確認してください。`/claude-skills:issue-close` で不要な issue をアーカイブできます。
   ```

---

## Issue → Plan Conversion (shared procedure)

This procedure is used by both Plan Workflow and Cycle Workflow. Do NOT duplicate this logic — always refer here.

### Steps

1. Read `docs/issues/issue-status.md`
   - If it doesn't exist: Display "No issues have been registered yet" and exit
2. **Issue selection** — behavior depends on the number of open issues:
   - **0 issues**: Display "No open issues found" and exit
   - **1 issue**: Use AskUserQuestion to confirm with the user. Present the issue details and offer two options: the issue slug (to proceed) and "Cancel" (to abort).
   - **2+ issues**: Use AskUserQuestion to present all issue slugs as options plus "Cancel". Ask the user to select the target issue.
3. Read the selected issue file (`docs/issues/{slug}.md`)
   - If not found: Display the file list in `docs/issues/` and exit with an error message
4. Execute `claude-skills:plan-create` via the Skill tool based on the issue content (title and summary)
   - Arguments: Pass the issue's title and summary
   - **CRITICAL**: The plan file MUST be created at `docs/plans/{timestamp}_{slug}.md`. Do NOT use `docs/cycles/` or any other directory. Verify the file was created in `docs/plans/` before proceeding.
   - **IMPORTANT**: Include `**Issue:** {slug}` in the plan header (no underscores, no markdown emphasis — just the raw slug). This field is used by `cycle` to auto-close the issue upon completion. See `plan/SKILL.md` "Optional `Issue` field" for the authoritative format.

---

## Plan Workflow

Create a plan from an issue without running cycle. Use when you want to review/discuss the plan before executing.

### Steps

1. Execute the **Issue → Plan Conversion** procedure above
2. Display completion message:
   ```
   ✅ Plan created from issue!
   📄 Plan: docs/plans/{timestamp}_{slug}.md
   📋 Issue: docs/issues/{slug}.md

   ## Next Steps
   1. Review and discuss the plan
   2. Run `/claude-skills:issue-team-cycle` for team-reviewed implementation (recommended)
   3. Run `/claude-skills:issue-cycle` for lightweight implementation
   4. Issue will be auto-closed when cycle completes 🚀
   ```

---

## Cycle Workflow

Connect an issue to plan → cycle for resolution.

> **Tip:** チームレビュー付きの `/claude-skills:issue-team-cycle` が推奨経路です。軽量な実装のみ必要な場合に issue-cycle を使用してください。

### Steps

1. Execute the **Issue → Plan Conversion** procedure above
2. **Preflight check** — Read the selected issue file and verify the「備考」(Notes) section has meaningful content (not just the placeholder text):
   - If the section is empty or contains only the default placeholder: Use AskUserQuestion to prompt the user for acceptance criteria or additional context. Update the issue file with the provided information before proceeding.
   - Options: provide text input, or "Skip" to proceed without additional context
3. Execute cycle:
   - If `--team` is present in the arguments:
     1. **Intake** — Use AskUserQuestion to collect discussion focus before starting team-cycle:
        - 期待する議論の焦点（スコープ）
        - 優先的に検討すべき観点（e.g., セキュリティ、パフォーマンス、アーキテクチャ）
        - 禁止事項や制約（任意）
        - Options: provide text input, or "Skip" to use defaults
     2. Remove `--team` from arguments, then execute `claude-skills:team-cycle` via the Skill tool with the created plan. Include the intake information in the arguments if provided.
   - Otherwise: Execute `claude-skills:cycle` via the Skill tool with the created plan
4. Error handling:
   - If plan creation fails: Display the error and exit. The issue remains open.
   - If cycle fails or is interrupted: Display the error and the path to the created plan file. The issue remains open. Inform the user they can retry with `/claude-skills:cycle` using the existing plan — no need to re-run issue-cycle.
   - Note: Issue auto-close is handled by cycle's Phase 3 via the `**Issue:**` field in the plan. No explicit close call is needed here.

---

## Close Workflow

Close (archive) an issue.

> **Note:** 通常、cycle/team-cycle 完了時に `**Issue:**` フィールド経由で自動クローズされるため手動クローズは不要です。手動クローズが必要なケース: cycle を経由しない解決、誤登録の取り消し、重複 issue の整理など。

### Arguments

- Issue slug (required — the full slug including timestamp prefix, e.g. `20260323143000_fix-login-timeout`)
- If omitted: Use AskUserQuestion to confirm. Follow the same selection logic as the **Issue → Plan Conversion** procedure Step 2.

### Steps

1. Get the issue slug from arguments. If omitted, use AskUserQuestion following the selection logic in **Issue → Plan Conversion** Step 2.
2. Verify the issue file `docs/issues/{slug}.md` exists
   - If not found: List files in `docs/issues/` and display an error message showing available slugs. Exit.
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
  yyyymmddhhmmss_<kebab-title>.md - Individual issue files
  archives/                   - Storage for closed issues
```

## issue-status.md Format

```markdown
# Issue Status

**Last Updated:** YYYY-MM-DD HH:MM:SS

| Issue | Tags | Created | Summary |
|-------|------|---------|---------|
| [20260323143000_fix-login](20260323143000_fix-login.md) | `auth` | 2026-03-23 14:30:00 | Login timeout issue |
```

## Template

- **Individual issue:** [references/issue-template.md](references/issue-template.md)

## Notes

- issue-status.md serves as the index. LLMs can understand the situation by reading just this file without opening all issues
- close = archive. On close, immediately move to `archives/` + remove row from `issue-status.md`
- Do not include sensitive information in issues
- The slug always includes the timestamp prefix (`yyyymmddhhmmss_{kebab-title}`). Use the full slug in all operations.
