---
name: design-lint
description: プロジェクトのコードベースを .design/tokens.json に基づいて lint し、デザイントークン違反（直書きカラー・フォント・spacing等）を機械的に検出するスキル。CI にも組み込み可能。「デザインリント」「design lint」「トークン検証」で起動。
---

# Design Lint

Lint the project's codebase against `.design/tokens.json` and detect design-token violations mechanically.

**Shared contract:** see [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md).
**Lint rule specification:** see [references/lint-contract.md](references/lint-contract.md).

## Prerequisites

1. `.design/tokens.json` must exist
   - If it does not, print "tokens.json not found. Generate it with `/claude-skills:design-scaffold`." and stop
2. `.design/lint-config.json` must exist (the default configuration is used when it is omitted)

## Workflow

The lint itself is implemented in the executable script `scripts/design_lint.py`. The agent only
runs the script and interprets its result; it never reproduces the rule-application logic itself
(reproducing it introduces drift against lint-contract).

### Step 1: Check the prerequisites

1. Confirm that `.design/tokens.json` exists (if not, guide the user to design-scaffold and stop)
2. `.design/lint-config.json` is optional (the script uses the default configuration when it is absent)

### Step 2: Run the script

Run this skill's `scripts/design_lint.py` in a shell:

```bash
python3 {skill_base_dir}/scripts/design_lint.py \
  --root {project_root} \
  --output .design/lint-report.json --json
```

- `{skill_base_dir}` is this skill's base directory (presented at invocation time)
- Exit codes: `0` = PASS / `1` = FAIL (errors present) / `2` = tokens.json absent
- The script decides on its own which rules apply:
  - DL001-006 always (valid with tokens.json alone)
  - DL101-103 when `.design/component-catalog.json` exists
  - DL201-203 when `.design/pages/` exists, and DL204 when `.design/layout-rules.json` exists

### Step 3: Report the result

Interpret `summary` and `violations` in the JSON output and report them.

**When everything passes:**
```
✅ Design Lint: PASS
Every file complies with the design tokens!
```

**On FAIL:**
```
❌ Design Lint: FAIL
{errors} errors detected.

📄 Detailed report: .design/lint-report.json

Places that need fixing:
{show the top 5 violations}

Replace the hard-coded values with CSS variables (var(--*)).
```

- With 20 violations or fewer, show the file name, line number, value, and suggested fix
- With more than 20, show only the per-rule summary and point at `.design/lint-report.json`
- When a violation carries a `suggestion` (the nearest token: RGB distance for colors, numeric
  difference for spacing/radius), present it as the suggested fix

### CI integration

The script is self-contained (standard library only, no dependencies), so it can go into CI as-is:

```yaml
- name: Design lint
  run: python3 path/to/design_lint.py --root . && echo PASS
```

## Absolute Constraints

- The lint **only reads** files. It performs no fixes (the script writes nothing other than
  saving the report to `--output`)
- Detection is regex-based; no AST parser is used (this keeps it language-independent)
- The agent never reproduces the rule logic in its head. Always run the script
- Values inside comments are ignored (the script handles this)
- `node_modules/` is always excluded
- `.design/` itself is out of lint scope

## References

- **Lint rule specification:** [references/lint-contract.md](references/lint-contract.md)
- **Shared contract:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
