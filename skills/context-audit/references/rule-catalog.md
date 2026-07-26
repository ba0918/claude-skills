# CA-* Rule Catalog

The definitions of every context-audit rule. **This table and the `RULES` registry of `scripts/static_checks.py` form a dual source of truth**, and `scripts/test_catalog_sync.py` machine-verifies that ID / Category / Severity / Action agree (preventing drift).

- **Severity** (BLOCK / WARN / INFO / PASS) is the seriousness of the problem. Its definition conforms to
  [../../shared/references/severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md).
- **Action** (AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY) is whether the fix can be automated. It is an axis orthogonal to severity, and its definition conforms to
  [../../shared/references/fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md).
- The v1 judgments are centered on "pure functions (deterministic)". Only for CA-C001 is candidate extraction a pure function, with the judgment of contradiction/intentional difference done by an LLM (Phase 2, REPORT_ONLY).

## The ID band convention

The band is fixed by the last 3 digits, so that future rules never land on arbitrary numbers:

| band | Meaning |
|------|------|
| `0xx` | schema / stale (structure and obsolescence) |
| `1xx` | reference existence (checking that the referent exists) |
| `2xx` | Reserved (unused) |
| `3xx` | security (secrets / credentials) |

Category prefixes: `S`=stale, `U`=unsafe, `D`=drift, `C`=contradiction, `M`=memory.

## The rule list

| ID | Category | Severity | Action | Verification | Content |
|----|----------|----------|--------|------|------|
| CA-S001 | stale | WARN | AUTO_FIX / NEEDS_JUDGMENT | Pure function | A reference to a nonexistent file/directory. Extraction covers only path notation containing `/` (a bare filename is out of scope, for precision). AUTO_FIX only when the edit distance is ≤1 and the candidate is unique; otherwise NEEDS_JUDGMENT |
| CA-S002 | stale | WARN | NEEDS_JUDGMENT | Pure function | A reference to a nonexistent `skills/<name>/` directory |
| CA-U001 | unsafe | WARN | REPORT_ONLY | Pure function | Vocabulary permitting skipped confirmation or destructive operations (regex-based) |
| CA-D001 | drift | INFO | REPORT_ONLY | Pure function | Claude-only tool vocabulary (Edit/Write and the like, including the Japanese 「〜ツール」 notation) leaking into AGENTS.md. Findings are made per line, and even when one line holds several such terms it is reported with a single representative term |
| CA-D002 | drift | WARN | NEEDS_JUDGMENT | Pure function | The coverage gap in the skill list (the real directories vs what the instruction file records). Automatically skipped when `validate_repo.py` is detected |
| CA-C001 | contradiction | WARN | REPORT_ONLY | Hybrid | A forbid/permit conflict over the same subject. Candidate extraction is a pure function (favoring recall), and the judgment is by an LLM |
| CA-M001 | memory | WARN | AUTO_FIX / NEEDS_JUDGMENT | Pure function | The memory frontmatter schema. Formatting drift is AUTO_FIX (normalization, body unchanged); a missing required key or an unknown type is NEEDS_JUDGMENT |
| CA-M101 | memory | WARN | NEEDS_JUDGMENT | Pure function | Checking the existence of the files/skills that memory references |
| CA-M301 | memory | BLOCK / WARN | REPORT_ONLY | Pure function (reusing the existing detect_secrets) | Pattern detection of suspected secrets/credentials (credential=BLOCK / PII (email, home_path)=WARN). Values are neither transcribed nor auto-masked |

## Ownership rules (the boundary against existing skills)

- **CA-S001 / CA-S002** superficially overlap doc-check's structural check, but the owned territory differs:
  - **context-audit**: owns instruction-bearing files (CLAUDE.md / AGENTS.md / rules / memory) as "instruction quality".
  - **doc-check**: owns arbitrary docs as "code accuracy (code ⇔ docs)".
- **CA-D002** is automatically skipped in a repository where `scripts/validate_repo.py` is detected (suppressed mechanically rather than as a prose "treat it as complementary"). validate_repo's check 6 owns coverage.

## Implementation notes

- **CA-D002** is a set-based lookup (the set difference between the skill directory set and the set recorded in the instruction file). It does not do a per-skill full-file scan.
- **CA-C001** candidate extraction buckets by subject token first and then pairs only same-subject pairs (Jaccard ≥ 0.5, opposite polarity). This avoids a naive O(S²) sweep over all pairs.
- Each rule is registered in `RULES` as the pure fn `check(targets, ctx) -> list[Finding]`. Adding a rule = adding a function + registering it + adding tests, and nothing else (Open-Closed).
- Every finding carries `id / severity / action / where(file:line) / what / why / how / fix_action(old→new|null)`, and secret redaction is applied to every line-context before serialization.

## v2 candidates (out of scope for v1)

- CLAUDE.md / AGENTS.md in nested subdirectories.
- A normalized claim hash + expiry for the baseline (v1 is a plain list of opaque finding IDs).
- The `2xx` band (additional drift rules).
- Support for additional runtime-specific memory formats.
