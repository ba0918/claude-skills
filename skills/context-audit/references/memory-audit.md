# Memory Audit (the details of auditing memory)

> The AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY of this file follow the shared contract
> [fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md).

Project memory (`~/.claude/projects/{cwd-slug}/memory/*.md`) can decay over long-term operation, yet it falls within the reach of no existing skill. context-audit brings it into scope, but **narrows that scope strictly to prevent a privacy incident**.

## Scope (the default = only the project corresponding to cwd)

- **Default**: only the `*.md` under `~/.claude/projects/{slugify(cwd)}/memory/`.
- **Only when `--include-global` is given**: additionally `~/.claude/CLAUDE.md` and `~/.claude/rules/*.md`.
- Spanning every project is **not supported** (reading another project's memory is an incident).

## Resolving cwd → the memory slug

The real Claude Code slugification **replaces every non-alphanumeric character with `-`** (not just `/`).

```
slugify("/home/mizumi/develop/claude-skills") == "-home-mizumi-develop-claude-skills"
slugify("/x/.claude")                          == "-x--claude"   # '.' becomes '-' too
```

The implementation is `collect_targets.slugify_cwd` (`re.sub(r"[^A-Za-z0-9]", "-", path)`). It is verified by a unittest against a real-directory fixture (`test_collect_targets.py`).

### reverse-verify + fail-safe skip

A resolved memory directory is **skipped without being read** unless it satisfies the following (`resolve_memory_dir`):

1. The directory really exists (`is_dir()`).
2. The entity obtained by resolving symlinks sits **exactly 2 levels** inside `~/.claude/projects/<slug>/memory`
   (eliminating symlink escape. Note that a true collision, where different cwds collapse onto the same slug, is structurally undetectable; in that case too, visibility comes from stating the absolute path that was read in the report).

When it is ambiguous, return `None` and skip. **State the resolved absolute path of the audited memory in the report**, making "which project was read" visible.

## The checks by type (CA-M001 / M101 / M301)

### CA-M001: frontmatter schema

The observed frontmatter (`name` / `description` / `type` / `originSessionId`) is
**a Claude Code runtime convention, not owned by the repository**. Treat it conservatively to avoid false positives from harness drift:

- A missing required key (`name` / `description`) → **NEEDS_JUDGMENT** (do not auto-complete it).
- An unknown value of `type` → **NEEDS_JUDGMENT** (do not make it a hard violation). The observed known values:
  `user` / `feedback` / `reference` / `project` / `session`.
- Formatting drift in a frontmatter key (`name:note` → `name: note`) → **AUTO_FIX**. However,
  rewrite **only inside the frontmatter block**; the body after `---` is byte-for-byte unchanged
  (guaranteed by `test_body_bytes_unchanged` in `test_apply_fixes.py`).

### CA-M101: reference existence

Check whether the repo-relative paths (markdown links / backticks) referenced by the memory body really exist.
If they do not, **NEEDS_JUDGMENT** (memory is never auto-rewritten).

### CA-M301: secret detection

Reuse `skills/shared/scripts/secret_detect.py` (originating in skill-improve, already tested) to detect suspected secrets/credentials line by line. **REPORT_ONLY / severity=BLOCK**.

## Privacy constraints (invariants)

- A detected secret value is **never transcribed into the report or the intermediate JSON**. Only the pattern name and `file:line`.
  The redaction is applied by `static_checks.finalize_findings` to every line-context of every finding (`mask_secrets`).
- **Never hand raw memory lines or PII** to the Phase 2 LLM or the Phase 4 user confirmation.
  Hand over only the normalized minimal claim text (already redacted).
- The only AUTO_FIX against memory is normalizing frontmatter formatting. **Deletion and semantic rewriting of the body are forbidden.**
