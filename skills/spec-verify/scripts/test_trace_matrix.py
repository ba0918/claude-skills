#!/usr/bin/env python3
"""Unit tests for trace_matrix (TDD — written before the implementation).

Covers: clause payload digest rules, many-to-many matrix generation,
unverified / dangling / stale detection, assurance level derivation from
observations (clause-schema.md 保証レベル節), forward-compat handling of
unknown evidence kinds, tombstone / draft / escape-hatch accounting,
manifest entry validation, output safety (markdown escaping + field-aware
masking), --baseline diff, --output containment, the CLI exit-code contract
shared with spec_lint, and the evidence-manifest.md <-> code constants sync.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import spec_lint as sl  # noqa: E402
import test_spec_lint as tsl  # noqa: E402  (md-table parse helpers の再利用)
import trace_matrix as tm  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_MATRIX = os.path.join(SCRIPTS_DIR, "trace_matrix.py")
REFS_DIR = os.path.join(SCRIPTS_DIR, "..", "references")
EVIDENCE_MANIFEST_MD = os.path.join(REFS_DIR, "evidence-manifest.md")
FIXTURES_DIR = os.path.join(REFS_DIR, "fixtures")
FIXTURES_README = os.path.join(FIXTURES_DIR, "README.md")

FAKE_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"

CLAUSE_ID = "LIB-INV-001"
TEST_ID = "tests/test_loans.py::test_loan_limit_holds"


def make_clause(**over):
    clause = {
        "id": CLAUSE_ID,
        "revision": 1,
        "kind": "invariant",
        "statement": "会員の貸出中冊数は貸出上限を超えない",
        "payload": {
            "target": "会員ごとの貸出状態",
            "condition": "貸出中アイテム数 <= 貸出上限",
        },
    }
    clause.update(over)
    return clause


def make_clause_file(clauses):
    return {"schema_version": 1, "clauses": clauses}


def binding(cid=CLAUSE_ID, revision=1, test_id=TEST_ID, **over):
    entry = {"clause_id": cid, "clause_revision": revision,
             "test_id": test_id}
    entry.update(over)
    return entry


def observation(cid=CLAUSE_ID, test_id=TEST_ID, kind="property",
                digest=None, **over):
    entry = {
        "clause_id": cid,
        "test_id": test_id,
        "evidence_kind": kind,
        "command": f"pytest {test_id}",
        "exit_status": 0,
        "cases_valid": 100,
        "failures": 0,
        "payload_digest": digest or tm.clause_digest(make_clause()),
        "recorded_at": "2026-07-17T04:10:34Z",
    }
    entry.update(over)
    return entry


def manifest(bindings=(), observations=()):
    return {"schema_version": 1, "bindings": list(bindings),
            "observations": list(observations)}


def run_trace(clauses, manifest_data, **kw):
    return tm.trace([("clauses.json", make_clause_file(clauses))],
                    manifest_data, manifest_name="manifest.json", **kw)


def row_for(result, cid):
    return next(r for r in result["matrix"] if r["clause"] == cid)


def checks(result, key="findings"):
    return {f["check"] for f in result[key]}


def run_cli(args):
    return subprocess.run(
        [sys.executable, TRACE_MATRIX, *args],
        capture_output=True, text=True)


def write_root(tmp, clauses=None, manifest_data=None):
    if clauses is not None:
        clauses_dir = os.path.join(tmp, "specs", "clauses")
        os.makedirs(clauses_dir, exist_ok=True)
        with open(os.path.join(clauses_dir, "a.json"), "w",
                  encoding="utf-8") as f:
            if isinstance(clauses, str):
                f.write(clauses)
            else:
                json.dump(make_clause_file(clauses), f, ensure_ascii=False)
    if manifest_data is not None:
        evidence_dir = os.path.join(tmp, "specs", "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        with open(os.path.join(evidence_dir, "manifest.json"), "w",
                  encoding="utf-8") as f:
            if isinstance(manifest_data, str):
                f.write(manifest_data)
            else:
                json.dump(manifest_data, f, ensure_ascii=False)
    return tmp


# ---------------------------------------------------------------------------
# Clause payload digest
# ---------------------------------------------------------------------------

class TestClauseDigest(unittest.TestCase):
    def test_digest_has_sha256_prefix_and_64_hex(self):
        digest = tm.clause_digest(make_clause())
        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")

    def test_key_order_does_not_change_digest(self):
        clause = make_clause()
        reordered = dict(reversed(list(clause.items())))
        reordered["payload"] = dict(
            reversed(list(clause["payload"].items())))
        self.assertEqual(tm.clause_digest(clause),
                         tm.clause_digest(reordered))

    def test_statement_only_edit_does_not_change_digest(self):
        before = tm.clause_digest(make_clause())
        after = tm.clause_digest(make_clause(
            statement="文言だけを修正した", rationale="理由も追記した"))
        self.assertEqual(before, after)

    def test_payload_change_changes_digest(self):
        before = tm.clause_digest(make_clause())
        changed = make_clause()
        changed["payload"]["condition"] = "貸出中アイテム数 < 貸出上限"
        self.assertNotEqual(before, tm.clause_digest(changed))

    def test_revision_change_changes_digest(self):
        self.assertNotEqual(tm.clause_digest(make_clause()),
                            tm.clause_digest(make_clause(revision=2)))

    def test_float_in_payload_is_rejected(self):
        clause = make_clause()
        clause["payload"]["condition"] = 1.5
        with self.assertRaises(ValueError):
            tm.clause_digest(clause)


# ---------------------------------------------------------------------------
# Many-to-many matrix generation
# ---------------------------------------------------------------------------

class TestMatrixGeneration(unittest.TestCase):
    def test_one_test_verifying_multiple_clauses_appears_in_each_row(self):
        clauses = [make_clause(id="LIB-INV-001"),
                   make_clause(id="LIB-INV-002")]
        m = manifest(bindings=[binding(cid="LIB-INV-001"),
                               binding(cid="LIB-INV-002")])
        result = run_trace(clauses, m)
        self.assertIn(TEST_ID, row_for(result, "LIB-INV-001")["tests"])
        self.assertIn(TEST_ID, row_for(result, "LIB-INV-002")["tests"])

    def test_one_clause_bound_to_multiple_tests_lists_all_tests(self):
        m = manifest(bindings=[
            binding(test_id="tests/a.py::t1"),
            binding(test_id="tests/b.py::t2"),
        ])
        result = run_trace([make_clause()], m)
        self.assertEqual(row_for(result, CLAUSE_ID)["tests"],
                         ["tests/a.py::t1", "tests/b.py::t2"])

    def test_matrix_rows_are_sorted_by_clause_id(self):
        clauses = [make_clause(id="LIB-INV-002"),
                   make_clause(id="LIB-INV-001")]
        result = run_trace(clauses, manifest())
        self.assertEqual([r["clause"] for r in result["matrix"]],
                         ["LIB-INV-001", "LIB-INV-002"])


# ---------------------------------------------------------------------------
# Detections: unverified / dangling / stale / revision mismatch
# ---------------------------------------------------------------------------

class TestDetections(unittest.TestCase):
    def test_clause_with_binding_but_no_observation_is_unverified(self):
        result = run_trace([make_clause()], manifest(bindings=[binding()]))
        self.assertIn("unverified-clause", checks(result))
        self.assertEqual(row_for(result, CLAUSE_ID)["level"], "unverified")

    def test_clause_without_any_binding_is_unverified(self):
        result = run_trace([make_clause()], manifest())
        self.assertIn("unverified-clause", checks(result))

    def test_dangling_binding_reference_is_detected(self):
        result = run_trace([make_clause()],
                           manifest(bindings=[binding(cid="LIB-INV-999")]))
        self.assertIn("dangling-clause-reference", checks(result))

    def test_dangling_observation_reference_is_detected(self):
        m = manifest(bindings=[binding()],
                     observations=[observation(cid="LIB-INV-999")])
        result = run_trace([make_clause()], m)
        self.assertIn("dangling-clause-reference", checks(result))

    def test_binding_revision_mismatch_is_a_warning_not_a_finding(self):
        clause = make_clause(revision=2)
        m = manifest(
            bindings=[binding(revision=1)],
            observations=[observation(digest=tm.clause_digest(clause))])
        result = run_trace([clause], m)
        self.assertIn("binding-revision-mismatch", checks(result, "warnings"))
        self.assertNotIn("binding-revision-mismatch", checks(result))
        # 警告は昇格を妨げない（digest が一致する限り証拠は有効）
        self.assertEqual(row_for(result, CLAUSE_ID)["level"], "property")

    def test_leading_dash_test_id_is_rejected(self):
        # 先頭 `-` はランナーオプションと誤解釈され得るため構造的に禁止
        result = run_trace([make_clause()],
                           manifest(bindings=[binding(test_id="-rf")]))
        self.assertIn("invalid-test-id", checks(result))

    def test_stale_evidence_is_detected_when_payload_changed(self):
        old_digest = tm.clause_digest(make_clause())
        changed = make_clause()
        changed["payload"]["condition"] = "貸出中アイテム数 < 貸出上限"
        m = manifest(bindings=[binding()],
                     observations=[observation(digest=old_digest)])
        result = run_trace([changed], m)
        self.assertIn("stale-evidence", checks(result))
        self.assertEqual(row_for(result, CLAUSE_ID)["level"], "unverified")

    def test_statement_only_edit_does_not_stale_evidence(self):
        recorded = tm.clause_digest(make_clause())
        edited = make_clause(statement="文言だけを修正した")
        m = manifest(bindings=[binding()],
                     observations=[observation(digest=recorded)])
        result = run_trace([edited], m)
        self.assertNotIn("stale-evidence", checks(result))
        self.assertEqual(row_for(result, CLAUSE_ID)["level"], "property")


# ---------------------------------------------------------------------------
# Assurance level derivation from observations
# ---------------------------------------------------------------------------

class TestAssuranceLevels(unittest.TestCase):
    def _level(self, obs):
        m = manifest(bindings=[binding()], observations=obs)
        result = run_trace([make_clause()], m)
        return row_for(result, CLAUSE_ID)["level"]

    def test_successful_property_run_promotes_to_property(self):
        self.assertEqual(self._level([observation(kind="property")]),
                         "property")

    def test_successful_example_run_yields_example_only(self):
        self.assertEqual(
            self._level([observation(kind="example", cases_valid=3)]),
            "example_only")

    def test_property_wins_over_example_when_both_present(self):
        self.assertEqual(self._level([
            observation(kind="example", cases_valid=3),
            observation(kind="property"),
        ]), "property")

    def test_nonzero_exit_status_is_not_evidence(self):
        self.assertEqual(self._level([observation(exit_status=1)]),
                         "unverified")

    def test_failures_present_is_not_evidence(self):
        self.assertEqual(self._level([observation(failures=2)]),
                         "unverified")

    def test_zero_valid_cases_is_not_evidence(self):
        self.assertEqual(self._level([observation(cases_valid=0)]),
                         "unverified")

    def test_skipped_run_is_not_evidence(self):
        self.assertEqual(self._level([observation(skipped=True)]),
                         "unverified")

    def test_xfail_run_is_not_evidence(self):
        self.assertEqual(self._level([observation(xfail=True)]),
                         "unverified")

    def test_unknown_evidence_kind_warns_and_stays_unverified(self):
        m = manifest(bindings=[binding()],
                     observations=[observation(kind="model_checked")])
        result = run_trace([make_clause()], m)
        self.assertIn("unknown-evidence-kind", checks(result, "warnings"))
        self.assertNotIn("unknown-evidence-kind", checks(result))
        self.assertEqual(row_for(result, CLAUSE_ID)["level"], "unverified")

    def test_observation_without_binding_warns_and_is_not_evidence(self):
        m = manifest(observations=[observation()])
        result = run_trace([make_clause()], m)
        self.assertIn("observation-without-binding",
                      checks(result, "warnings"))
        self.assertEqual(row_for(result, CLAUSE_ID)["level"], "unverified")


# ---------------------------------------------------------------------------
# Undigestable clauses (exist in the index; assurance derivation is skipped)
# ---------------------------------------------------------------------------

def undigestable_clause(cid="LIB-INV-003"):
    # payload が object でない → digest 算出不能（undigestable-clause warning）
    return make_clause(id=cid, payload="not-an-object")


class TestUndigestableClause(unittest.TestCase):
    def test_binding_to_undigestable_clause_is_not_dangling(self):
        m = manifest(bindings=[binding(cid="LIB-INV-003")])
        result = run_trace([make_clause(), undigestable_clause()], m)
        self.assertNotIn("dangling-clause-reference", checks(result))
        self.assertIn("undigestable-clause", checks(result, "warnings"))

    def test_observation_for_undigestable_clause_is_not_dangling_or_stale(self):
        m = manifest(
            bindings=[binding(cid="LIB-INV-003")],
            observations=[observation(cid="LIB-INV-003",
                                      digest="sha256:" + "0" * 64)])
        result = run_trace([make_clause(), undigestable_clause()], m)
        self.assertNotIn("dangling-clause-reference", checks(result))
        self.assertNotIn("stale-evidence", checks(result))

    def test_undigestable_clause_skips_assurance_and_counts(self):
        result = run_trace([make_clause(), undigestable_clause()], manifest())
        # 保証レベル判定はスキップ（matrix にも unverified にも現れない）
        self.assertEqual([r["clause"] for r in result["matrix"]], [CLAUSE_ID])
        self.assertEqual(result["summary"]["clauses_active"], 1)
        self.assertEqual(result["summary"]["tombstones"], 0)


# ---------------------------------------------------------------------------
# Tombstone / escape hatch accounting
# ---------------------------------------------------------------------------

class TestTombstoneAndEscapeHatch(unittest.TestCase):
    def test_tombstone_is_excluded_from_matrix_and_counted_separately(self):
        clauses = [
            make_clause(id="LIB-INV-001", superseded_by=["LIB-INV-002"]),
            make_clause(id="LIB-INV-002"),
        ]
        result = run_trace(clauses, manifest())
        self.assertEqual([r["clause"] for r in result["matrix"]],
                         ["LIB-INV-002"])
        self.assertEqual(result["summary"]["tombstones"], 1)
        # tombstone は unverified を水増ししない
        wheres = [f["where"] for f in result["findings"]
                  if f["check"] == "unverified-clause"]
        self.assertEqual(len(wheres), 1)
        self.assertIn("LIB-INV-002", wheres[0])

    def test_observation_for_tombstone_is_not_dangling(self):
        clauses = [
            make_clause(id="LIB-INV-001", superseded_by=["LIB-INV-002"]),
            make_clause(id="LIB-INV-002"),
        ]
        m = manifest(bindings=[binding(cid="LIB-INV-001")],
                     observations=[observation(cid="LIB-INV-001")])
        result = run_trace(clauses, m)
        self.assertNotIn("dangling-clause-reference", checks(result))

    def test_escape_hatch_usage_rate_is_reported_in_summary(self):
        clauses = [
            make_clause(id="LIB-INV-001",
                        predicates=["loans::invariants::limit_holds"]),
            make_clause(id="LIB-INV-002"),
        ]
        result = run_trace(clauses, manifest())
        hatch = result["summary"]["escape_hatch"]
        self.assertEqual(hatch["used"], 1)
        self.assertEqual(hatch["active"], 2)
        self.assertEqual(hatch["rate_percent"], 50.0)

    def test_escape_hatch_rate_is_null_when_no_active_clauses(self):
        result = tm.trace([], manifest())
        self.assertIsNone(result["summary"]["escape_hatch"]["rate_percent"])


# ---------------------------------------------------------------------------
# Empty / missing manifest (graceful paths)
# ---------------------------------------------------------------------------

class TestEmptyAndMissingManifest(unittest.TestCase):
    def test_zero_clauses_and_empty_manifest_is_graceful(self):
        result = tm.trace([], manifest())
        self.assertFalse(result["corrupt"])
        self.assertFalse(result["findings_present"])
        self.assertEqual(result["matrix"], [])

    def test_missing_manifest_is_zero_evidence_with_note(self):
        result = run_trace([make_clause()], None)
        self.assertFalse(result["corrupt"])
        self.assertIn("unverified-clause", checks(result))
        self.assertTrue(any("マニフェスト" in n for n in result["notes"]))


# ---------------------------------------------------------------------------
# Manifest entry validation (structure findings, exit-1 class)
# ---------------------------------------------------------------------------

class TestManifestEntryValidation(unittest.TestCase):
    def test_unknown_key_in_binding_is_fail_closed(self):
        result = run_trace([make_clause()],
                           manifest(bindings=[binding(note="typo")]))
        self.assertIn("unknown-key", checks(result))

    def test_missing_required_observation_key_is_detected(self):
        obs = observation()
        del obs["payload_digest"]
        result = run_trace([make_clause()],
                           manifest(bindings=[binding()], observations=[obs]))
        self.assertIn("missing-required", checks(result))

    def test_test_id_charset_violation_is_detected(self):
        bad = binding(test_id="tests/x.py::t; rm -rf /")
        result = run_trace([make_clause()], manifest(bindings=[bad]))
        self.assertIn("invalid-test-id", checks(result))

    def test_clause_id_pattern_violation_is_detected(self):
        result = run_trace([make_clause()],
                           manifest(bindings=[binding(cid="lib-inv-001")]))
        self.assertIn("invalid-clause-ref", checks(result))

    def test_digest_format_violation_is_detected(self):
        m = manifest(bindings=[binding()],
                     observations=[observation(digest="md5:abc")])
        result = run_trace([make_clause()], m)
        self.assertIn("invalid-digest", checks(result))

    def test_negative_failures_is_a_value_violation(self):
        m = manifest(bindings=[binding()],
                     observations=[observation(failures=-1)])
        result = run_trace([make_clause()], m)
        self.assertIn("invalid-value", checks(result))

    def test_invalid_observation_is_excluded_from_assurance(self):
        m = manifest(bindings=[binding()],
                     observations=[observation(digest="md5:abc")])
        result = run_trace([make_clause()], m)
        self.assertEqual(row_for(result, CLAUSE_ID)["level"], "unverified")

    def test_every_finding_carries_where_what_why_how(self):
        m = manifest(bindings=[binding(cid="LIB-INV-999", note="typo")],
                     observations=[observation(digest="md5:abc")])
        result = run_trace([make_clause()], m)
        self.assertGreater(len(result["findings"]), 0)
        for f in result["findings"] + result["warnings"]:
            for key in ("where", "what", "why", "how"):
                self.assertIn(key, f)
                self.assertTrue(f[key], f"empty {key} in {f}")


# ---------------------------------------------------------------------------
# Output safety (escaping / field-aware masking / determinism / trust notes)
# ---------------------------------------------------------------------------

class TestOutputSafety(unittest.TestCase):
    def test_markdown_escapes_pipes_and_strips_control_chars(self):
        m = manifest(bindings=[binding()],
                     observations=[observation(kind="bad|kind\x1b[31m")])
        result = run_trace([make_clause()], m)
        rendered = tm.render_markdown(result)
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("bad|kind", rendered)
        self.assertIn("bad\\|kind", rendered)

    def test_free_text_secret_is_masked_but_digest_and_ids_survive(self):
        digest = tm.clause_digest(make_clause())
        m = manifest(bindings=[binding()],
                     observations=[observation(kind=FAKE_AWS)])
        result = run_trace([make_clause()], m)
        md = tm.render_markdown(result)
        js = tm.render_json(result)
        for rendered in (md, js):
            self.assertNotIn(FAKE_AWS, rendered)
            self.assertIn(CLAUSE_ID, rendered)
        # digest（hex 64 桁）はマスクで破壊されない
        self.assertIn(digest, js)

    def test_reports_carry_procedural_trust_and_test_drift_notes(self):
        result = run_trace([make_clause()], manifest())
        md = tm.render_markdown(result)
        js = json.loads(tm.render_json(result))
        for text in (md, " ".join(js["notes"])):
            self.assertIn("手続き信頼", text)
            self.assertIn("test drift", text)

    def test_output_is_deterministic_for_identical_input(self):
        def render():
            m = manifest(bindings=[binding()],
                         observations=[observation()])
            result = run_trace([make_clause()], m)
            return tm.render_json(result), tm.render_markdown(result)
        self.assertEqual(render(), render())


# ---------------------------------------------------------------------------
# CLI contract (exit codes / publish suppression / drafts / baseline)
# ---------------------------------------------------------------------------

class TestCliContract(unittest.TestCase):
    def test_report_only_with_findings_exits_zero_and_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses=[make_clause()], manifest_data=manifest())
            proc = run_cli(["--root", tmp, "--json"])
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertTrue(out["findings_present"])

    def test_strict_with_findings_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses=[make_clause()], manifest_data=manifest())
            proc = run_cli(["--root", tmp, "--strict"])
        self.assertEqual(proc.returncode, 1)

    def test_strict_fully_verified_run_exits_zero(self):
        m = manifest(bindings=[binding()], observations=[observation()])
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses=[make_clause()], manifest_data=m)
            proc = run_cli(["--root", tmp, "--strict", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertFalse(out["findings_present"])

    def test_corrupt_manifest_exits_two_and_publishes_no_matrix(self):
        for mode in ([], ["--strict"]):
            with tempfile.TemporaryDirectory() as tmp:
                write_root(tmp, clauses=[make_clause()],
                           manifest_data="{ broken")
                proc = run_cli(["--root", tmp, "--json", *mode])
            self.assertEqual(proc.returncode, 2, mode)
            self.assertNotIn("Traceback", proc.stdout + proc.stderr)
            out = json.loads(proc.stdout)
            self.assertFalse(out["valid"])
            self.assertEqual(out["matrix"], [])

    def test_corrupt_clause_file_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses="{ broken", manifest_data=manifest())
            proc = run_cli(["--root", tmp])
        self.assertEqual(proc.returncode, 2)

    def test_zero_targets_is_a_graceful_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli(["--root", tmp, "--json"])
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertFalse(out["findings_present"])

    def test_draft_files_are_counted_but_never_parsed(self):
        m = manifest(bindings=[binding()], observations=[observation()])
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses=[make_clause()], manifest_data=m)
            drafts = os.path.join(tmp, ".agents", "artifacts", "spec-verify",
                                  "drafts")
            os.makedirs(drafts)
            with open(os.path.join(drafts, "draft.json"), "w",
                      encoding="utf-8") as f:
                f.write("{ broken draft — パースされないので壊れていてよい")
            proc = run_cli(["--root", tmp, "--json"])
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertEqual(out["summary"]["draft_files"], 1)
        # draft の条項は集計対象外（matrix は specs/ の 1 条項のみ）
        self.assertEqual(len(out["matrix"]), 1)

    def test_explicit_missing_manifest_is_a_usage_error(self):
        # --manifest 明示指定の不存在は「証拠ゼロ続行」でなく exit 2
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses=[make_clause()])
            proc = run_cli(["--root", tmp, "--manifest",
                            os.path.join(tmp, "no-such-manifest.json")])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("manifest-not-found", proc.stderr)

    def test_default_missing_manifest_continues_as_zero_evidence(self):
        # 既定パス（暗黙）の不存在は従来どおり証拠ゼロで続行する
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses=[make_clause()])
            proc = run_cli(["--root", tmp, "--json"])
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertTrue(any("マニフェスト" in n for n in out["notes"]))

    def test_manifest_outside_root_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            os.makedirs(root)
            outside = os.path.join(tmp, "manifest.json")
            with open(outside, "w", encoding="utf-8") as f:
                json.dump(manifest(), f)
            proc = run_cli(["--root", root, "--manifest", outside])
        self.assertEqual(proc.returncode, 2)


class TestBaselineDiff(unittest.TestCase):
    def _root_with_unverified(self, tmp):
        return write_root(tmp, clauses=[make_clause()],
                          manifest_data=manifest())

    def test_baseline_suppresses_known_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root_with_unverified(tmp)
            first = run_cli(["--root", tmp, "--json"])
            baseline_path = os.path.join(tmp, "baseline.json")
            with open(baseline_path, "w", encoding="utf-8") as f:
                f.write(first.stdout)
            second = run_cli(["--root", tmp, "--json",
                              "--baseline", baseline_path])
        out = json.loads(second.stdout)
        self.assertEqual(out["findings"], [])
        self.assertFalse(out["findings_present"])
        self.assertGreater(out["summary"]["baseline_suppressed"], 0)

    def test_by_check_is_recomputed_after_baseline_suppression(self):
        # by_check が抑制前の全件を数えたままだと summary.findings と矛盾する
        with tempfile.TemporaryDirectory() as tmp:
            self._root_with_unverified(tmp)
            first = run_cli(["--root", tmp, "--json"])
            baseline_path = os.path.join(tmp, "baseline.json")
            with open(baseline_path, "w", encoding="utf-8") as f:
                f.write(first.stdout)
            second = run_cli(["--root", tmp, "--json",
                              "--baseline", baseline_path])
        out = json.loads(second.stdout)
        s = out["summary"]
        self.assertEqual(s["findings"], 0)
        finding_total = sum(count for check, count in s["by_check"].items()
                            if check in tm.FINDING_CHECKS)
        self.assertEqual(finding_total, s["findings"])
        warning_total = sum(count for check, count in s["by_check"].items()
                            if check in tm.WARNING_CHECKS)
        self.assertEqual(warning_total, s["warnings"])

    def test_new_finding_survives_baseline_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root_with_unverified(tmp)
            first = run_cli(["--root", tmp, "--json"])
            baseline_path = os.path.join(tmp, "baseline.json")
            with open(baseline_path, "w", encoding="utf-8") as f:
                f.write(first.stdout)
            write_root(tmp, clauses=[make_clause(),
                                     make_clause(id="LIB-INV-002")])
            second = run_cli(["--root", tmp, "--json",
                              "--baseline", baseline_path])
        out = json.loads(second.stdout)
        wheres = [f["where"] for f in out["findings"]]
        self.assertTrue(any("LIB-INV-002" in w for w in wheres))
        self.assertFalse(any("LIB-INV-001" in w for w in wheres))

    def test_missing_baseline_falls_back_to_full_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root_with_unverified(tmp)
            proc = run_cli(["--root", tmp, "--json", "--baseline",
                            os.path.join(tmp, "no-such-baseline.json")])
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertTrue(out["findings_present"])
        self.assertTrue(any("baseline" in n for n in out["notes"]))

    def test_unreadable_baseline_falls_back_to_full_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root_with_unverified(tmp)
            baseline_path = os.path.join(tmp, "baseline.json")
            with open(baseline_path, "w", encoding="utf-8") as f:
                f.write("{ broken baseline")
            proc = run_cli(["--root", tmp, "--json",
                            "--baseline", baseline_path])
        out = json.loads(proc.stdout)
        self.assertTrue(out["findings_present"])
        self.assertTrue(any("baseline" in n for n in out["notes"]))


class TestOutputOption(unittest.TestCase):
    def _run_with_output(self, tmp, out_name, extra=()):
        write_root(tmp, clauses=[make_clause()], manifest_data=manifest())
        out_path = os.path.join(tmp, out_name)
        proc = run_cli(["--root", tmp, "--output", out_path, *extra])
        return proc, out_path

    def test_output_writes_report_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, out_path = self._run_with_output(tmp, "report.md")
            self.assertEqual(proc.returncode, 0)
            with open(out_path, encoding="utf-8") as f:
                self.assertIn("手続き信頼", f.read())

    def test_output_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = os.path.join(tmp, "report.md")
            with open(existing, "w", encoding="utf-8") as f:
                f.write("previous")
            proc, _ = self._run_with_output(tmp, "report.md")
            self.assertEqual(proc.returncode, 2)
            with open(existing, encoding="utf-8") as f:
                self.assertEqual(f.read(), "previous")

    def test_output_overwrites_with_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = os.path.join(tmp, "report.md")
            with open(existing, "w", encoding="utf-8") as f:
                f.write("previous")
            proc, out_path = self._run_with_output(tmp, "report.md",
                                                   ["--force"])
            self.assertEqual(proc.returncode, 0)
            with open(out_path, encoding="utf-8") as f:
                self.assertNotEqual(f.read(), "previous")

    def test_output_under_specs_or_git_is_rejected(self):
        for target in (os.path.join("specs", "report.md"),
                       os.path.join(".git", "report.md")):
            with tempfile.TemporaryDirectory() as tmp:
                os.makedirs(os.path.join(tmp, os.path.dirname(target)),
                            exist_ok=True)
                proc, out_path = self._run_with_output(tmp, target)
                self.assertEqual(proc.returncode, 2, target)
                self.assertFalse(os.path.exists(out_path), target)

    def test_output_outside_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            os.makedirs(root)
            write_root(root, clauses=[make_clause()],
                       manifest_data=manifest())
            out_path = os.path.join(tmp, "escape.md")
            proc = run_cli(["--root", root, "--output", out_path])
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(os.path.exists(out_path))

    def test_no_output_file_is_written_on_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_root(tmp, clauses=[make_clause()],
                       manifest_data="{ broken")
            out_path = os.path.join(tmp, "report.md")
            proc = run_cli(["--root", tmp, "--output", out_path])
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(os.path.exists(out_path))


# ---------------------------------------------------------------------------
# Sync: evidence-manifest.md tables <-> trace_matrix code constants
# ---------------------------------------------------------------------------

class TestManifestSchemaSyncMdToCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = tsl._md_sections(EVIDENCE_MANIFEST_MD)

    def test_toplevel_table_matches_code_constants(self):
        rows = tsl._table_rows(self.sections["マニフェストのファイル構造"])
        self.assertEqual(tsl._field_table(rows), tm.MANIFEST_TOPLEVEL_FIELDS)

    def test_binding_table_matches_code_constants(self):
        rows = tsl._table_rows(self.sections["binding 宣言"])
        self.assertEqual(tsl._field_table(rows), tm.BINDING_FIELDS)

    def test_observation_table_matches_code_constants(self):
        rows = tsl._table_rows(self.sections["実行 observation"])
        self.assertEqual(tsl._field_table(rows), tm.OBSERVATION_FIELDS)

    def test_evidence_kind_enum_in_md_matches_code(self):
        rows = tsl._table_rows(self.sections["実行 observation"])
        desc = next(cells[3] for cells in rows
                    if tsl._BACKTICK_TOKEN.match(cells[0]).group(1)
                    == "evidence_kind")
        self.assertIn("enum:", desc)
        self.assertEqual(tuple(tsl._BACKTICK_TOKEN.findall(
            desc.split("enum:")[1])), tm.EVIDENCE_KINDS)

    def test_test_id_and_digest_patterns_in_md_match_code(self):
        rows = tsl._table_rows(self.sections["識別子・digest の形式規則"])
        patterns = {cells[0]: tsl._BACKTICK_TOKEN.match(cells[1]).group(1)
                    for cells in rows}
        self.assertEqual(
            patterns["`test_id` パターン"], tm.TEST_ID_PATTERN)
        self.assertEqual(
            patterns["`payload_digest` 形式"], tm.DIGEST_PATTERN)

    def test_detection_table_matches_code_check_lists(self):
        rows = tsl._table_rows(self.sections["検出項目"])
        md = {tsl._BACKTICK_TOKEN.match(cells[0]).group(1):
              tsl._BACKTICK_TOKEN.match(cells[1]).group(1)
              for cells in rows}
        self.assertEqual(
            {slug for slug, sev in md.items() if sev == "error"},
            set(tm.FINDING_CHECKS))
        self.assertEqual(
            {slug for slug, sev in md.items() if sev == "warning"},
            set(tm.WARNING_CHECKS))

    def test_corruption_slugs_raised_in_code_are_documented(self):
        with open(TRACE_MATRIX, encoding="utf-8") as f:
            source = f.read()
        raised = set(re.findall(r'SpecLintError\(\s*"([a-z-]+)"', source))
        with open(EVIDENCE_MANIFEST_MD, encoding="utf-8") as f:
            documented = set(re.findall(r"`([a-z-]+)`", f.read()))
        self.assertLessEqual(raised, documented,
                             raised - documented)


# ---------------------------------------------------------------------------
# Manifest conformance corpus (driven by fixtures/README.md)
# ---------------------------------------------------------------------------

_M_VALID_ROW = re.compile(r"^\|\s*`manifest/valid/([^`]+)`\s*\|\s*valid\s*\|")
_M_INVALID_ROW = re.compile(
    r"^\|\s*`manifest/invalid/([^`]+)`\s*\|\s*invalid\s*\|\s*`([^`]+)`")

MANIFEST_CORRUPTION_SLUGS = {"unknown-schema-version",
                             "manifest-key-not-array"}


def _manifest_readme_expectations():
    valid, invalid = [], {}
    with open(FIXTURES_README, encoding="utf-8") as f:
        for line in f:
            m = _M_VALID_ROW.match(line)
            if m:
                valid.append(m.group(1))
                continue
            m = _M_INVALID_ROW.match(line)
            if m:
                invalid[m.group(1)] = m.group(2)
    return valid, invalid


class TestManifestConformanceCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid, cls.invalid = _manifest_readme_expectations()

    def _load(self, group, name):
        path = os.path.join(FIXTURES_DIR, "manifest", group, name)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_readme_lists_every_manifest_fixture_and_vice_versa(self):
        on_disk_valid = sorted(
            os.listdir(os.path.join(FIXTURES_DIR, "manifest", "valid")))
        on_disk_invalid = sorted(
            os.listdir(os.path.join(FIXTURES_DIR, "manifest", "invalid")))
        self.assertEqual(sorted(self.valid), on_disk_valid)
        self.assertEqual(sorted(self.invalid), on_disk_invalid)

    def test_all_valid_manifest_fixtures_have_no_structure_findings(self):
        self.assertTrue(self.valid)
        for name in self.valid:
            _b, _o, findings = tm.validate_manifest(
                self._load("valid", name), name)
            self.assertEqual(findings, [], name)

    def test_all_invalid_manifest_fixtures_are_detected_as_expected(self):
        self.assertTrue(self.invalid)
        for name, slug in self.invalid.items():
            data = self._load("invalid", name)
            if slug in MANIFEST_CORRUPTION_SLUGS:
                with self.assertRaises(sl.SpecLintError) as ctx:
                    tm.validate_manifest(data, name)
                self.assertEqual(ctx.exception.category, slug, name)
            else:
                _b, _o, findings = tm.validate_manifest(data, name)
                self.assertIn(slug, {f["check"] for f in findings}, name)


if __name__ == "__main__":
    unittest.main()
