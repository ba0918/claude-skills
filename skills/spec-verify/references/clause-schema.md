# Clause Schema v1 (the canonical vocabulary)

The schema definition for the clause files spec-verify handles. **This document is the sole
source of truth**, and [spec-clause.schema.json](spec-clause.schema.json) is merely a projection
for external editors and target projects (the scripts do not read schema.json at runtime).
Drift between the source of truth, the code, and the projection is mechanically prevented by
the sync tests. The sync tests reconcile **(1) the tables in this document ⇔ the in-code
constants of `spec_lint`, and (2) the in-code constants ⇔ the required / enum / pattern /
payload required keys of [spec-clause.schema.json](spec-clause.schema.json)** (2 edges — table ⇔
constants and constants ⇔ schema.json — close the loop over all 3).

**Table parse contract**: the sync tests locate tables by heading (section name). The sections
parsed are: "File Structure", "Common envelope", "kind-specific discriminated payload",
"ID and revision Rules", "exit code contract (shared by spec_lint / trace_matrix)".
**If you change a section name, update the sync tests at the same time.**
A data row is decided by "a line starting with `|` whose first cell (or second cell) is a
backticked token".
**If you change the column order of any table, update the sync tests at the same time** as well.
The type tokens are fixed to `string` / `integer` / `object` / `array[string]` /
`array[object]`, and the required tokens to `required` / `optional`.
In "kind-specific discriminated payload", the prose form
"`from` / `event` / `to` (required, string) and `guard` (optional, string)" in the description
cells of `transitions` / `forbidden` is also reconciled by the sync tests (the nested rule's
field names and required/optional are read out of that form).
In the "exit code contract" section, the input-limit table (second cell is the value, third cell
is the corruption category) and the bullet list of corruption categories (lines starting with
`- ` plus a backticked slug) are the reconciliation targets.

## File Structure

The top level of a clause file is an object with exactly these 2 keys:

| Field | Type | Required | Description |
|-----------|-----|------|------|
| `schema_version` | `integer` | `required` | File-level schema version. Fixed at `1` for v1. An unknown value is treated as input corruption (exit 2) |
| `clauses` | `array[object]` | `required` | The array of clauses (common envelopes) |

`schema_version` is placed at the **file level** rather than per clause in order to structurally
prohibit a state where versions are mixed within one file.

Input whose top level is not an object, and input missing a top-level required key, is a
corruption of the file structure and is **treated as input corruption (exit 2)**, the same as an
unknown `schema_version`. It does not proceed to per-clause violation detection (the exit-1
class).

## Common Verification Rules (unknown keys, non-empty)

Rules applied uniformly to every object in this schema (top level, envelope, payload, and each
element of `transitions` / `forbidden`). They are not repeated in individual table cells (a
fixed note):

- **Unknown keys are fail-closed (a violation)**: for both envelope and payload, input carrying
  a key not enumerated in the respective table is detected as a violation (equivalent to
  `additionalProperties: false` in the projection). This prevents the accident where a typo'd
  key is silently ignored and "the contract you thought you wrote does not exist".
- **strings are non-empty**: the non-empty requirement (equivalent to `minLength 1`) applies to
  every field whose type token is `string` in any table, and to every element of an
  `array[string]`. It holds regardless of required or optional. "No value" is expressed by
  **omitting the key itself**, not by an empty string (permitted for optional fields only; an
  empty string in a required field is the same violation as a missing one).

## Common envelope

The fields every clause carries. Everything but `payload` is independent of kind.

| Field | Type | Required | Description |
|-----------|-----|------|------|
| `id` | `string` | `required` | Clause ID. A namespaced ASCII identifier following the pattern in "ID and revision Rules". Unique within the file |
| `revision` | `integer` | `required` | A positive integer (1 or greater). A monotonically increasing counter incremented by 1 on every semantic change |
| `kind` | `string` | `required` | The kind of verification semantics. enum: `invariant` / `pre_post` / `transition` / `authorization` |
| `statement` | `string` | `required` | The human-facing declarative sentence (natural language). Excluded from digest computation (evidence does not expire from wording fixes) |
| `payload` | `object` | `required` | The kind-specific discriminated payload (next section). Test generation and digest computation are based on this payload and do not depend on a natural-language reinterpretation of statement |
| `rationale` | `string` | `optional` | The reason and background for why this contract is needed |
| `examples` | `array[string]` | `optional` | Concrete examples satisfying the clause. **Synthetic and anonymized data only** (see the "Confidential Information Convention" section) |
| `counterexamples` | `array[string]` | `optional` | Concrete examples violating the clause. Same as above |
| `refs` | `array[string]` | `optional` | References to external specifications (OpenAPI / JSON Schema, etc.). **Stored as opaque identifiers/URIs; the scripts do not dereference them** (they neither open, fetch, nor check for existence) |
| `superseded_by` | `array[string]` | `optional` | An array of successor clause IDs. **A clause carrying this key is a tombstone** (see the lifecycle section). An empty array means "retired with no successor" |
| `predicates` | `array[string]` | `optional` | Escape hatch: references to host-language predicates. **Opaque strings**; the scripts do not import, eval, execute, or check them for existence. A predicate reference contributes nothing to evidence on its own, and the assurance level is computed from observations only, as usual |

Each element of `examples` / `counterexamples` is recommended to take the form
"input → expected output" (a counterexample being "input → wrong output (reason for the
violation)"). The format is not machine-verified, but since a human is expected to read them
side by side during reverse-generation review, keep the form consistent within a clause.

## kind-specific discriminated payload

The required keys of `payload` are determined by `kind`. The bind workflow generates tests from
this payload (it does not reinterpret statement).

| kind | Field | Type | Required | Description |
|------|-----------|-----|------|------|
| `invariant` | `target` | `string` | `required` | A declarative description of the data shape the invariant applies to |
| `invariant` | `condition` | `string` | `required` | A declarative description of the invariant predicate that must always hold for the target |
| `pre_post` | `input_domain` | `string` | `required` | A description of the input domain (the basis for generator design) |
| `pre_post` | `precondition` | `string` | `required` | The precondition |
| `pre_post` | `operation` | `string` | `required` | Identification and description of the target operation |
| `pre_post` | `postcondition` | `string` | `required` | The postcondition |
| `transition` | `states` | `array[string]` | `required` | The state set (1 element or more) |
| `transition` | `events` | `array[string]` | `required` | The event set (1 element or more) |
| `transition` | `transitions` | `array[object]` | `required` | Permitted transitions. Each element carries `from` / `event` / `to` (required, string) and `guard` (optional, string) |
| `transition` | `forbidden` | `array[object]` | `optional` | Forbidden transitions. Each element carries `from` / `event` (required, string) |
| `authorization` | `subject` | `string` | `required` | The subject (a description of the role or attributes) |
| `authorization` | `action` | `string` | `required` | The operation |
| `authorization` | `resource` | `string` | `required` | The target resource |
| `authorization` | `context` | `string` | `optional` | Contextual conditions (time window, ownership relation, etc.) |
| `authorization` | `effect` | `string` | `required` | enum: `allow` / `deny` |

**Conflict resolution rule for authorization**: when both `allow` and `deny` are applicable to
the same (subject, action, resource) triple, **deny wins**. This rule is not something written
into a clause file; it is semantics fixed by the v1 schema itself.

## ID and revision Rules

| Item | Rule |
|------|------|
| `id` pattern | `^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-[0-9]{3,}$` |
| `id` composition | Uppercase alphanumeric namespace segments (1 or more, `-` separated) plus a trailing sequence number of 3 or more digits. **The leading segment starts with a letter** (`[A-Z][A-Z0-9]*`), and **intermediate segments are alphanumeric** (`[A-Z0-9]+`; an all-digit segment is allowed). Examples: `LIB-INV-001`, `CHAT-USAGE-042` |
| `id` uniqueness | Duplicates within the same file are prohibited (detected by lint). Cross-project uniqueness is an operational convention |
| `revision` | A positive integer (1 or greater). Incremented by 1 on every semantic change (a change to payload). Monotonically increasing; rollback is prohibited |

An ID is a namespaced opaque identifier, and the scripts do not interpret its internal structure
(the meaning of its segments). The sequence number is nothing more than a human numbering
convention.

## Lifecycle (classification of changes)

A table classifying which edit constitutes which operation:

| Kind of change | id | revision | How it is expressed |
|-----------|-----|----------|----------|
| Wording fix (an edit outside payload — `statement` / `rationale` / `examples`, etc.) | Keep | Keep | Edit it in place |
| Semantic change (a change to `payload`) | Keep | +1 | Edit it as a revision of the same clause |
| Retirement (no successor) | Keep | Keep | Add `superseded_by: []` to turn it into a tombstone |
| Split | Keep | Keep | Add `superseded_by: [newID1, newID2, ...]` to the old clause and add the new clauses |
| Merge | Keep | Keep | Add `superseded_by: [mergeTargetID]` to each old clause being merged |

### tombstone Rules

- A clause carrying the `superseded_by` key is a tombstone. **Deleting a tombstone is a
  violation** (a break in history). However, lint can only detect it when a reference to the
  deleted ID remains in another clause's `superseded_by` or in an evidence manifest.
- The reference-integrity violations lint detects mechanically: **self-reference** in
  `superseded_by`, a **cycle** (A→B→A), and a **reference to a non-existent successor ID**.
- **Relation to aggregation**: tombstone clauses (clauses carrying the `superseded_by` key) are
  **excluded from assurance-level computation and unverified-clause detection**, and are listed
  **by count only, separately** in the traceability summary (not included in the unverified
  count). This keeps retired contracts from padding `unverified` and burying the "not looked at"
  of active clauses.

### Limits of Single-snapshot lint (v1)

Lint sees only a single snapshot — the current set of files. Therefore **reuse of a deleted ID**
and **rollback of a revision** cannot be detected mechanically. "No ID reuse" and "revision is
monotonically increasing" are **conventions in v1, not machine guarantees**. Machine guarantees
via a history registry or VCS comparison are handled in v2.

## Assurance Levels

A clause's assurance level is **computed from evidence (observations). Self-declaration is
prohibited** (hand-adding a binding alone does not promote it). The philosophy of making
"zero evidence = not looked at" visible is identical to
[coverage-ledger](../../shared/references/coverage-ledger.md).

| Level | v1 computation | Definition / computation rule |
|--------|---------|-----------------|
| `unverified` | Computable (default) | Zero valid evidence. It means "not looked at", not "no problems" |
| `example_only` | Computable | 1 or more successful observations from example-based tests |
| `property` | Computable | An observation from a property test with **valid (excluding discards) executed case count ≥ 1, failures 0, and exit 0** |
| `model_checked` | Reserved | Not accepted in v1 because there is no corresponding verifiable evidence kind (warning + treated as `unverified`) |
| `proved` | Reserved | Same as above |

- "Executed case count" refers to the **valid case count** (excluding discards). Observations
  that are skip / xfail / have 0 valid cases / have a non-zero exit / have failures > 0 do not
  count as successful evidence.
- **Forward-compatibility rule**: an observation with an unknown or unsupported evidence kind
  produces a warning and is treated as the lowest level (`unverified`), and **is not an error**.
  This keeps older scripts from breaking when new evidence kinds are added in the future.

## Placement Conventions (target project side)

| Target | Path | Handling |
|------|------|------|
| Clause files | `specs/clauses/*.json` | Committed (the source of truth) |
| Evidence manifest | `specs/evidence/manifest.json` | Committed |
| Generated matrix | stdout / temporary area | Ephemeral. Not committed |
| draft (unapproved clauses) | `.agents/artifacts/spec-verify/drafts/` | Isolated from the canonical tree (conforms to the [artifact-store consumer contract](../../shared/references/artifact-paths.md)). Outside the search scope of lint / trace. Moved to `specs/clauses/` on approval (apply) |

Drafts are kept out of the canonical tree to structurally prevent the accident where an
unapproved clause slips into lint / traceability aggregation and gets treated as "an approved
contract".

## exit code contract (shared by spec_lint / trace_matrix)

Both scripts share this contract. This table is the single source of truth for the definition.

| exit | report-only (default) | strict (`--strict`) | Mode dependent |
|------|---------------------|----------------------|-----------|
| `0` | Ran successfully. **0 even when there are detections** (a zero-target notice is also 0) | Ran successfully with no detections | Yes |
| `1` | Does not occur | There are violations / detections | Yes |
| `2` | Input corruption / usage error | Input corruption / usage error | **No (mode independent)** |

- Warnings (the file-local warning on revision monotonicity, the warning on unsupported evidence
  kinds, etc.) **do not affect** the exit code.
- Whether there were detections is expressed separately from the exit code, in the
  `findings_present` field of the machine output (JSON). CI can decide by exit code, and tools by
  the JSON.
- On exit 2, assurance-level computation and matrix publication are not performed (diagnostic
  output only — do not let partial results be consumed as canonical).

### Input Limits and Corruption Categories (the breakdown of exit 2)

The input limits are as follows. Exceeding one is treated as input corruption (exit 2) and does
not proceed to per-clause verification (the exit-1-class violation detection). The values are
reconciled with the lint implementation's in-code constants by the sync tests:

| Limit item | Value | Corruption category |
|---------|-----|-------------|
| File size (per file) | `1000000` bytes | `file-too-large` |
| Clause count (per file) | `10000` clauses | `too-many-clauses` |
| Nesting depth | `16` levels | `too-deep` |

The corruption categories for exit 2 (the slugs of `diagnostics[].category` in the machine
output) have the following list as their source of truth (the sync tests reconcile it against
the raise sites in the lint implementation):

- `invalid-json` — Cannot be parsed as JSON (including an empty file or corrupted encoding)
- `duplicate-json-key` — A duplicated JSON key within the same object
- `not-an-object` — The top level is not an object
- `missing-toplevel-key` — A top-level required key is missing
- `clauses-not-array` — `clauses` is not an array
- `unknown-schema-version` — `schema_version` is unknown (fixed at `1` for v1)
- `file-too-large` — The file size limit was exceeded
- `too-many-clauses` — The clause count limit was exceeded
- `too-deep` — The nesting depth limit was exceeded
- `unreadable` — The file cannot be read
- `path-escape` — The target is outside root (including escape via a symlink)

## Confidential Information Convention

`examples` / `counterexamples` / `statement` / `rationale` are **restricted to synthetic and
anonymized data**. Do not write real credentials, API keys, or personal information in them.
Lint applies secret detection to free-text fields, and on a hit it does not silently rewrite
them but reports and demands a fix (because unauthorized alteration of the canonical
specification is drift itself).

## why-not (options not taken)

- **YAML not taken**: the runtime environment's standard library has no YAML parser, which is
  incompatible with the zero-external-dependency policy. JSON can be parsed strictly with the
  standard library (down to rejecting duplicate keys).
- **Markdown + frontmatter not taken**: frontmatter lacks the expressive power for the nested
  and list structures of kind-specific payloads (the from/event/to of `transitions`, etc.), and
  would end up embedding a JSON-equivalent structure anyway. Readability is secured by statement
  / rationale and the reverse-generated documentation.
