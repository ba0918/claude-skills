# SI-* Rule Catalog

Definitions of every skill-interface-audit rule.
The authoring principles of [skill-authoring.md](../../shared/references/skill-authoring.md) are the canon,
and this audits compliance with them mechanically.

- **Severity** (BLOCK / WARN / INFO / PASS) is the seriousness of the problem. The definitions follow
  [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md).
- **Action** (AUTO\_FIX / NEEDS\_JUDGMENT / REPORT\_ONLY) is whether the fix can be automated. It is an axis
  orthogonal to severity, and the definitions follow [fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md).
- Phase 1 (SI-S\*) decides deterministically with pure functions. Phase 2 (SI-C\*) is semantic judgment by the LLM, all REPORT\_ONLY.

## ID band convention

| prefix | band | Meaning |
|--------|------|------|
| `S` | `0xx` | structural — mechanical verification of structure and form |
| `C` | `1xx` | contract — semantic completeness of the API contract elements |

Update this table when a band is added in v2.

## Finding ID numbering rule

When one rule matches in several places, add a suffix to the finding ID:
- single match: `SI-S004`
- multiple matches: `SI-S004-1`, `SI-S004-2`, ... (in detection order)

Because the `where` field (`skill:file:line`) identifies findings uniquely in the report,
the suffix is an aid to readability only — use `where` for matching against a baseline.

## Phase 1: Structural Rules (pure functions)

These do not duplicate the checks validate\_repo.py already enforces in CI (frontmatter, description trigger
words, link existence, shared contract vocabulary). This phase owns the structural quality validate\_repo.py does not look at.

| ID | Severity | Action | Canon | Verification | Content |
|----|----------|--------|------|------|------|
| SI-S001 | WARN | REPORT\_ONLY | skill-authoring #4 | pure function | **Reference chain depth exceeded**: SKILL.md → a file in references/ → an md link to yet another file (depth > 1). Progressive disclosure goes one level only |
| SI-S002 | WARN | REPORT\_ONLY | skill-authoring frontmatter | pure function | **A workflow summary leaked into the description**: detects numbered lists, phase keywords (Phase/Step/まず/次に), and procedure description patterns. A description stays at "what it does + when to use it" |
| SI-S003 | INFO | REPORT\_ONLY | skill-authoring #1 | pure function | **Prose bloat**: sections in SKILL.md without a `Workflow` / `Phase` / `Step` style heading exceed 60% of the whole. An indicator of deviation from the process-over-prose principle |
| SI-S004 | WARN | NEEDS\_JUDGMENT | AGENTS.md editing rules | pure function | **Platform-specific tool vocabulary leaked in**: SKILL.md or references/ contains a platform-specific tool API name (`Edit`, `Write`, `Read`, `Bash`, `Agent`, `Workflow`, etc.) or a model-specific name. Code blocks and quotes are excluded |

### SI-S001 detail: reference chain depth

Detection method:
1. Extract the relative md links in SKILL.md and treat the links into references/ as primary references
2. Extract the relative md links inside the primary reference files
3. If a primary reference links to md outside shared/references/, that is a finding (shared is allowed, being the shared contract)

### SI-S002 detail: workflow summary in the description

Detection patterns (regex-based):
- `\d+[.)]\s` — a numbered list
- `Phase\s*\d` / `Step\s*\d` — phase and step numbers
- `まず.*次に` / `最初に.*その後` — a chain of procedural connectives
- 2 or more `→` — a chain of flow arrows

### SI-S003 detail: prose bloat verdict

Heuristic:
1. Classify the `##` headings of SKILL.md: workflow-type (`Workflow` / `Phase` / `Step` / フロー / ワークフロー) vs prose-type (everything else). Subheadings at `###` and below inherit the classification of their parent `##`. A standalone `###` with no parent `##` is classified as prose-type
2. The denominator is **the total line count of SKILL.md excluding the frontmatter** (blank lines included). If the total lines of prose-type sections / the denominator > 0.6, it is a finding
3. A pile of knowledge should be moved out into references/ (skill-authoring #1 + #4)

### SI-S004 detail: platform-specific vocabulary

Vocabulary detected (the same list as context-audit CA-D001, over a different file set):
- tool API names: `Edit`, `Write`, `Read`, `Bash`, `Agent`, `Workflow`, `WebFetch`, `WebSearch`, `Grep`, `Glob`, `LSP`, `NotebookEdit`
- the Japanese 「〜ツール」 form: `Edit ツール`, `Bash ツール`, etc.
- model-specific names: `claude-opus-*`, `claude-sonnet-*`, `claude-haiku-*`, `gpt-*`, `o1-*`

**Case rules (to prevent false positives in an English SKILL.md)**:
- A PascalCase tool name (`Edit`, `Read`, `Write`, etc.) is detected only when it appears standalone **outside sentence-initial position**
- A capital at the start of a sentence (line start, or right after a period) is ordinary English orthography and is excluded
- Lowercase `edit`, `read`, `write`, etc. are excluded as ordinary verbs (they are also used as Unix commands)
- Because `LSP` is also an industry-standard protocol name, detect only tool usages such as 「`LSP` ツール」 or 「`LSP` を使う」, and exclude mentions of the protocol name (「`LSP` 準拠」, 「`LSP` サポート」, etc.)

Exclusion conditions:
- code blocks (inside `` ``` `` / `` ` ``)
- quote blocks (`> ` lines)
- words inside file paths (`scripts/test_*.py`, etc.)
- capitalized words in sentence-initial position (line start, or right after a period)
- words inside Markdown headings (`## Workflow`, etc. A heading starts with `#` at line start, so it also falls under the sentence-initial exclusion, but exclude it explicitly)
- words right after a numbered list marker (the `Write` in `3. Write ...`, etc. The period in `N. ` is not a sentence-final period, but treat it as sentence-initial and exclude it)

## Phase 2: Contract Rules (LLM semantic judgment)

The fix action of every rule is **REPORT\_ONLY** (the ceiling is NEEDS\_JUDGMENT; AUTO\_FIX is forbidden).
A finding includes a patch candidate (`fix_draft`: a draft of the text that should be added).

**"Not applicable" is a legitimate state**: given a skill's nature, a particular contract element may be
unnecessary. The LLM reads the skill's purpose and workflow and decides on "could an LLM misunderstand and
cause an accident if this element is missing". If it judges the element unnecessary, that is a PASS.

| ID | Severity | Canon | Content | Typical N/A case |
|----|----------|------|------|----------------|
| SI-C001 | WARN | skill-authoring #2, #3 | **Undeclared side effects**: file creation, modification, or deletion, external communication, or state change is not stated. When missing, the LLM adds side effects "while it is at it" | A read-only skill (investigate, etc.) that already states "does not change anything" |
| SI-C002 | WARN | verification-gate.md | **Missing or unverifiable completion condition**: what counts as done is unclear, or is written in a form that cannot be verified | An interactive skill (brainstorm, etc.) where the user decides when to stop |
| SI-C003 | WARN | skill-authoring #2 | **Undefined failure handling**: how to behave on an error or interruption is not written. The LLM swallows the failure and reports completion | A skill with no failure path (a thinking tool such as problem-solving) |
| SI-C004 | INFO | — | **Missing input/argument contract**: the list of arguments, their defaults, and the behavior with no argument are unclear | A skill that takes no arguments |
| SI-C005 | INFO | skill-authoring #2 | **Undefined output/artifact**: what it produces (a file, a report, a diff) is unclear | A skill that is complete within the dialogue |
| SI-C006 | INFO | — | **Undocumented delegation condition**: the boundary against similar skills and when to use which is not written | A skill with a single purpose that cannot be confused with another |

### The discipline behind these severities

Why SI-C001-C003 are WARN and SI-C004-C006 are INFO:

- **WARN (C001-C003)**: the LLM accident mode on omission has been observed in skill-improve's friction data
  and in empirical-prompt-tuning's measurements (runaway side effects, misjudging completion, swallowing failures).
  Promote or demote the severity as evidence accumulates
- **INFO (C004-C006)**: even when missing, the context tends to fill them in, and there is no measured data yet
  tying them directly to an accident. Promote to WARN once skill-improve logs confirm a correlation with accidents

## v2 candidates (out of scope for v1)

- SI-C007: idempotency / re-entrancy — safety of re-running after an interruption
- SI-C008: non-interactive fallback — behavior under headless execution
- SI-C009: preconditions — requirements on the execution environment
- SI-S005: missing rationalization guard table — recommended for skills that modify files
- claim normalization hash + expiry for the baseline
- promotion of stable SI-S\* rules into validate\_repo.py
