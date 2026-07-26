# conformance corpus — the clause schema v1 conformance verification corpus

The set of valid / invalid fixtures against [clause-schema.md](../clause-schema.md) (the canonical vocabulary).
Both the hand-rolled validation (`spec_lint`) and
[spec-clause.schema.json](../spec-clause.schema.json) (the external-facing projection) are verified
against the same corpus, preventing the canon and the projection from diverging.

Every fixture is **synthetic data** built around a fictional library lending system and contains no
real credentials or personal information (the "Confidential Information Convention" section of clause-schema.md).

## The expected verdicts

The "schema detects" column says whether JSON Schema alone — which cannot express referential integrity —
can detect that violation (`yes` / `no`). Violations marked `no` are detected only by lint.

### valid/

| fixture | Expected | Elements covered |
|---------|----------|--------------|
| `valid/invariant_minimal.json` | valid | a minimal clause with only the required fields (invariant) |
| `valid/all_kinds.json` | valid | all 4 kinds + the optional fields rationale / examples / counterexamples / refs |
| `valid/predicates_escape_hatch.json` | valid | a use of `predicates` (the escape hatch) + authorization's `context` / `allow` |
| `valid/lifecycle_superseded.json` | valid | uses of the `superseded_by` array (a split tombstone, and an empty array for retirement with no successor), revision > 1 |

### invalid/

| fixture | Expected | Violation type | Schema detects |
|---------|----------|----------|-------------|
| `invalid/unknown_kind.json` | invalid | `unknown-kind` (a kind outside the enum) | yes |
| `invalid/missing_statement.json` | invalid | `missing-required` (a required envelope field is missing) | yes |
| `invalid/payload_missing_required.json` | invalid | `payload-missing-required` (a required key of the kind-specific payload is missing) | yes |
| `invalid/duplicate_id.json` | invalid | `duplicate-id` (a duplicate ID within the file) | no |
| `invalid/dangling_superseded_by.json` | invalid | `dangling-superseded-by` (a reference to a successor ID that does not exist) | no |
| `invalid/self_superseded_by.json` | invalid | `self-superseded-by` (a self reference) | no |
| `invalid/cycle_superseded_by.json` | invalid | `cycle-superseded-by` (an A→B→A cycle) | no |
| `invalid/nonpositive_revision.json` | invalid | `invalid-revision` (a revision that is not a positive integer) | yes |
| `invalid/bad_id_charset.json` | invalid | `invalid-id` (an ID pattern violation, lowercase) | yes |
| `invalid/unknown_schema_version.json` | invalid | `unknown-schema-version` (exit 2 as corrupt input) | yes |
| `invalid/unknown_envelope_key.json` | invalid | `unknown-key` (an unknown envelope key; fail-closed) | yes |
| `invalid/empty_statement.json` | invalid | `empty-required-string` (an empty string in a required string field) | yes |
| `invalid/non_object_toplevel.json` | invalid | `not-an-object` (the top level is not an object; exit 2 as corrupt input) | yes |
| `invalid/missing_clauses_key.json` | invalid | `missing-toplevel-key` (the required top-level key `clauses` is missing; exit 2 as corrupt input) | yes |

Notes:

- Unlike the other invalid cases (violation detection, equivalent to exit 1), `unknown-schema-version` /
  `not-an-object` / `missing-toplevel-key` are classified as **corrupt input (exit 2)**
  (see the file structure section and the exit code contract of [clause-schema.md](../clause-schema.md)).

### Cases that cannot become corpus entries, and why they are excluded

The following corrupt-input cases are not placed as fixture files; they are verified inside `spec_lint`'s
unit tests as string literals or generated inputs:

- **Broken JSON** (a syntax error) and **an empty file**: they cannot be parsed as JSON, so this corpus's own
  application procedure — "load the fixture as JSON and apply the validator" — does not hold
  (it exits 2 in the parsing layer, before schema validation).
  Only inputs parseable as JSON belong in the corpus.
- **A duplicate JSON key**: the violation exists only in the textual representation and disappears after parsing
  in a general JSON parser, so the expected verdict cannot be pinned as a fixture file
  (what gets read depends on the validator implementation).

## The manifest corpus (the evidence manifest)

The set of valid / invalid fixtures against [evidence-manifest.md](../evidence-manifest.md) (the canon of the
evidence manifest format). Applied mechanically in CI to `trace_matrix`'s manifest structure validation.

This corpus verifies **only the structure of the manifest alone**. Detections that require cross-checking against
the clause files (dangling / stale / revision mismatch / assurance level computation) cannot have their expected
verdicts pinned as fixtures, and are verified inside `trace_matrix`'s unit tests paired with clause files.

### manifest/valid/

| fixture | Expected | Elements covered |
|---------|----------|--------------|
| `manifest/valid/empty.json` | valid | empty bindings / observations (a graceful case) |
| `manifest/valid/bound_with_observation.json` | valid | many-to-many bindings (one test to several clauses, one clause to several tests) + property / example observations + the optional fields (cases_discarded / skipped / xfail) |

### manifest/invalid/

| fixture | Expected | Violation type |
|---------|----------|----------|
| `manifest/invalid/bad_test_id.json` | invalid | `invalid-test-id` (a character-set violation in test_id: whitespace, shell metacharacters) |
| `manifest/invalid/missing_observation_key.json` | invalid | `missing-required` (the required observation key payload_digest is missing) |
| `manifest/invalid/unknown_binding_key.json` | invalid | `unknown-key` (an unknown binding key; fail-closed) |
| `manifest/invalid/bad_digest.json` | invalid | `invalid-digest` (a malformed payload_digest) |
| `manifest/invalid/unknown_schema_version.json` | invalid | `unknown-schema-version` (exit 2 as corrupt input) |
| `manifest/invalid/bindings_not_array.json` | invalid | `manifest-key-not-array` (exit 2 as corrupt input) |

Notes:

- Unlike the other invalid cases (entry violations, equivalent to exit 1), `unknown-schema-version` /
  `manifest-key-not-array` are classified as **corrupt input (exit 2)**
  (see the corrupt input section of [evidence-manifest.md](../evidence-manifest.md)).

## How to verify with an external JSON Schema validator

The equivalence of spec-clause.schema.json and this corpus can be checked with any draft-07 capable
JSON Schema validator. For example:

```bash
# Example 1: Python's jsonschema package (requires pip install jsonschema)
python3 - <<'EOF'
import json, pathlib
from jsonschema import Draft7Validator

base = pathlib.Path("skills/spec-verify/references")
schema = json.loads((base / "spec-clause.schema.json").read_text())
validator = Draft7Validator(schema)

for group, expect_valid in (("valid", True), ("invalid", False)):
    for path in sorted((base / "fixtures" / group).glob("*.json")):
        errors = list(validator.iter_errors(json.loads(path.read_text())))
        print(f"{path.name}: {'valid' if not errors else 'invalid'}")
EOF

# Example 2: Node.js's ajv-cli (requires npm install -g ajv-cli)
ajv validate --spec=draft7 -s skills/spec-verify/references/spec-clause.schema.json \
  -d "skills/spec-verify/references/fixtures/valid/*.json"
```

**Expected result**: everything in `valid/` is valid. In `invalid/`, only the fixtures marked "schema detects = yes"
come out invalid, and the 4 marked "schema detects = no"
(duplicate-id / dangling / self / cycle) **are correctly judged valid by the schema alone**
(referential integrity is outside what JSON Schema can express, and only lint verifies it).

## Limits (how this repository's CI handles it)

Because this repository's verification is meant to run on the standard library alone, no external JSON Schema
validator runs in CI. What CI applies this corpus to mechanically is the hand-rolled validation (`spec_lint`)
only; the equivalence on the schema.json side is confirmed by running the procedure above locally.
Structural synchronization (required / enum / ID pattern / required payload keys) is guaranteed in CI by a
synchronization test that cross-checks the three of
(1) the tables of clause-schema.md ⇔ the in-code constants of `spec_lint`, and
(2) the in-code constants ⇔ spec-clause.schema.json
(see the table parsing contract of clause-schema.md).
