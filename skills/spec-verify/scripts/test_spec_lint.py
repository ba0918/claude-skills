#!/usr/bin/env python3
"""Unit tests for spec_lint (TDD — written before the implementation).

Covers: hand-rolled clause validation (envelope / payload / references),
fail-closed parsing (exit-2 corruption paths), path containment, the
where/what/why/how finding contract, CLI exit-code contract, the
clause-schema.md <-> code constants <-> spec-clause.schema.json three-way
sync, and the conformance fixture corpus driven by fixtures/README.md.
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

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC_LINT = os.path.join(SCRIPTS_DIR, "spec_lint.py")
REFS_DIR = os.path.join(SCRIPTS_DIR, "..", "references")
CLAUSE_SCHEMA_MD = os.path.join(REFS_DIR, "clause-schema.md")
SCHEMA_JSON = os.path.join(REFS_DIR, "spec-clause.schema.json")
FIXTURES_DIR = os.path.join(REFS_DIR, "fixtures")
FIXTURES_README = os.path.join(FIXTURES_DIR, "README.md")

# 破損カテゴリ（exit 2）— fixtures/README.md の補足と同じ分類。
CORRUPTION_SLUGS = {"unknown-schema-version", "not-an-object", "missing-toplevel-key"}

# Built at runtime so the literal AWS-key pattern never appears in this source
# file (the repo's secret-detection hook would otherwise flag the fixture).
FAKE_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"


def make_clause(**over):
    clause = {
        "id": "LIB-INV-001",
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


def make_file(clauses):
    return {"schema_version": 1, "clauses": clauses}


def lint_obj(data, name="test.json"):
    return sl.lint_data([(name, data)])


def checks(result):
    return {f["check"] for f in result["findings"]}


def run_cli(args):
    return subprocess.run(
        [sys.executable, SPEC_LINT, *args],
        capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Valid inputs
# ---------------------------------------------------------------------------

class TestValidClauseFiles(unittest.TestCase):
    def test_minimal_invariant_file_passes_with_no_findings(self):
        result = lint_obj(make_file([make_clause()]))
        self.assertEqual(result["findings"], [])
        self.assertFalse(result["corrupt"])
        self.assertFalse(result["findings_present"])

    def test_tombstone_with_existing_successors_passes(self):
        clauses = [
            make_clause(id="LIB-INV-001", superseded_by=["LIB-INV-002"]),
            make_clause(id="LIB-INV-002"),
        ]
        result = lint_obj(make_file(clauses))
        self.assertEqual(result["findings"], [])

    def test_tombstone_with_empty_successor_list_passes(self):
        result = lint_obj(make_file([make_clause(superseded_by=[])]))
        self.assertEqual(result["findings"], [])

    def test_successor_defined_in_another_file_of_same_run_is_not_dangling(self):
        a = make_file([make_clause(id="LIB-INV-001", superseded_by=["LIB-INV-002"])])
        b = make_file([make_clause(id="LIB-INV-002")])
        result = sl.lint_data([("a.json", a), ("b.json", b)])
        self.assertEqual(result["findings"], [])

    def test_same_id_in_different_files_is_not_a_duplicate(self):
        a = make_file([make_clause(id="LIB-INV-001")])
        b = make_file([make_clause(id="LIB-INV-001")])
        result = sl.lint_data([("a.json", a), ("b.json", b)])
        self.assertNotIn("duplicate-id", checks(result))


# ---------------------------------------------------------------------------
# Envelope violations
# ---------------------------------------------------------------------------

class TestEnvelopeViolations(unittest.TestCase):
    def test_unknown_kind_is_detected(self):
        result = lint_obj(make_file([make_clause(kind="performance")]))
        self.assertIn("unknown-kind", checks(result))

    def test_missing_required_envelope_field_is_detected(self):
        clause = make_clause()
        del clause["statement"]
        result = lint_obj(make_file([clause]))
        self.assertIn("missing-required", checks(result))

    def test_unknown_envelope_key_is_fail_closed(self):
        result = lint_obj(make_file([make_clause(note="typo key")]))
        self.assertIn("unknown-key", checks(result))

    def test_empty_required_string_is_detected(self):
        result = lint_obj(make_file([make_clause(statement="")]))
        self.assertIn("empty-required-string", checks(result))

    def test_empty_optional_string_field_is_detected(self):
        result = lint_obj(make_file([make_clause(rationale="")]))
        self.assertIn("empty-string", checks(result))

    def test_empty_element_in_string_array_is_detected(self):
        result = lint_obj(make_file([make_clause(examples=["ok", ""])]))
        self.assertIn("empty-string", checks(result))

    def test_wrong_type_for_string_field_is_detected(self):
        result = lint_obj(make_file([make_clause(statement=123)]))
        self.assertIn("invalid-type", checks(result))

    def test_wrong_type_for_string_array_is_detected(self):
        result = lint_obj(make_file([make_clause(examples="not-a-list")]))
        self.assertIn("invalid-type", checks(result))

    def test_non_dict_clause_entry_is_detected(self):
        result = lint_obj(make_file(["not a clause"]))
        self.assertIn("invalid-type", checks(result))

    def test_secret_in_free_text_field_is_reported_not_rewritten(self):
        result = lint_obj(make_file([make_clause(statement=f"key {FAKE_AWS} leak")]))
        self.assertIn("secret-in-free-text", checks(result))
        # 検出はするが、出力に秘密値そのものを再掲しない
        self.assertNotIn(FAKE_AWS, json.dumps(result, ensure_ascii=False))


# ---------------------------------------------------------------------------
# ID / revision rules
# ---------------------------------------------------------------------------

class TestIdAndRevisionRules(unittest.TestCase):
    def test_lowercase_id_violates_pattern(self):
        result = lint_obj(make_file([make_clause(id="lib-inv-001")]))
        self.assertIn("invalid-id", checks(result))

    def test_id_without_three_digit_serial_violates_pattern(self):
        result = lint_obj(make_file([make_clause(id="LIB-INV-01")]))
        self.assertIn("invalid-id", checks(result))

    def test_numeric_middle_segment_is_allowed(self):
        result = lint_obj(make_file([make_clause(id="LIB-2024-001")]))
        self.assertNotIn("invalid-id", checks(result))

    def test_zero_revision_is_detected(self):
        result = lint_obj(make_file([make_clause(revision=0)]))
        self.assertIn("invalid-revision", checks(result))

    def test_negative_revision_is_detected(self):
        result = lint_obj(make_file([make_clause(revision=-1)]))
        self.assertIn("invalid-revision", checks(result))

    def test_boolean_revision_is_detected(self):
        result = lint_obj(make_file([make_clause(revision=True)]))
        self.assertIn("invalid-revision", checks(result))

    def test_float_revision_is_detected(self):
        result = lint_obj(make_file([make_clause(revision=1.5)]))
        self.assertIn("invalid-revision", checks(result))

    def test_duplicate_id_within_file_is_detected(self):
        clauses = [make_clause(), make_clause(revision=2)]
        result = lint_obj(make_file(clauses))
        self.assertIn("duplicate-id", checks(result))

    def test_invalid_id_value_is_not_used_as_where_label(self):
        result = lint_obj(make_file([make_clause(id=FAKE_AWS)]))
        self.assertIn("invalid-id", checks(result))
        for f in result["findings"]:
            self.assertNotIn(FAKE_AWS, f["where"])
        # 生値は where 以外（mask 対象の what/why/how）にも残らない
        self.assertNotIn(FAKE_AWS, json.dumps(result, ensure_ascii=False))


# ---------------------------------------------------------------------------
# kind-specific payload violations
# ---------------------------------------------------------------------------

class TestPayloadViolations(unittest.TestCase):
    def test_missing_payload_required_key_is_detected(self):
        clause = make_clause(kind="pre_post", payload={
            "input_domain": "会員 ID とアイテム ID の組",
            "precondition": "在庫あり",
            "operation": "checkout(member_id, item_id)",
        })
        result = lint_obj(make_file([clause]))
        self.assertIn("payload-missing-required", checks(result))

    def test_unknown_payload_key_is_fail_closed(self):
        clause = make_clause(payload={
            "target": "貸出台帳", "condition": "重複なし", "extra": "typo"})
        result = lint_obj(make_file([clause]))
        self.assertIn("unknown-key", checks(result))

    def test_non_object_payload_is_detected(self):
        result = lint_obj(make_file([make_clause(payload="not-an-object")]))
        self.assertIn("invalid-type", checks(result))

    def test_empty_states_array_violates_min_items(self):
        clause = make_clause(kind="transition", payload={
            "states": [], "events": ["checkout"],
            "transitions": [
                {"from": "available", "event": "checkout", "to": "on_loan"}],
        })
        result = lint_obj(make_file([clause]))
        self.assertIn("min-items", checks(result))

    def test_empty_events_array_violates_min_items(self):
        clause = make_clause(kind="transition", payload={
            "states": ["available"], "events": [],
            "transitions": [
                {"from": "available", "event": "checkout", "to": "on_loan"}],
        })
        result = lint_obj(make_file([clause]))
        self.assertIn("min-items", checks(result))

    def test_transition_rule_missing_to_is_detected(self):
        clause = make_clause(kind="transition", payload={
            "states": ["available"], "events": ["checkout"],
            "transitions": [{"from": "available", "event": "checkout"}],
        })
        result = lint_obj(make_file([clause]))
        self.assertIn("missing-required", checks(result))

    def test_transition_rule_unknown_key_is_fail_closed(self):
        clause = make_clause(kind="transition", payload={
            "states": ["available"], "events": ["checkout"],
            "transitions": [{"from": "available", "event": "checkout",
                             "to": "on_loan", "when": "typo"}],
        })
        result = lint_obj(make_file([clause]))
        self.assertIn("unknown-key", checks(result))

    def test_forbidden_rule_with_from_and_event_passes(self):
        clause = make_clause(kind="transition", payload={
            "states": ["available", "retired"], "events": ["checkout", "retire"],
            "transitions": [
                {"from": "available", "event": "retire", "to": "retired"}],
            "forbidden": [{"from": "retired", "event": "checkout"}],
        })
        result = lint_obj(make_file([clause]))
        self.assertEqual(result["findings"], [])

    def test_authorization_effect_outside_enum_is_detected(self):
        clause = make_clause(kind="authorization", payload={
            "subject": "一般会員", "action": "retire",
            "resource": "蔵書アイテム", "effect": "maybe"})
        result = lint_obj(make_file([clause]))
        self.assertIn("invalid-enum", checks(result))

    def test_authorization_without_optional_context_passes(self):
        clause = make_clause(kind="authorization", payload={
            "subject": "一般会員", "action": "retire",
            "resource": "蔵書アイテム", "effect": "deny"})
        result = lint_obj(make_file([clause]))
        self.assertEqual(result["findings"], [])


# ---------------------------------------------------------------------------
# superseded_by reference integrity
# ---------------------------------------------------------------------------

class TestSupersededByIntegrity(unittest.TestCase):
    def test_dangling_successor_is_detected(self):
        result = lint_obj(make_file(
            [make_clause(superseded_by=["LIB-INV-999"])]))
        self.assertIn("dangling-superseded-by", checks(result))

    def test_self_reference_is_detected(self):
        result = lint_obj(make_file(
            [make_clause(superseded_by=["LIB-INV-001"])]))
        self.assertIn("self-superseded-by", checks(result))

    def test_two_clause_cycle_is_detected(self):
        clauses = [
            make_clause(id="LIB-INV-001", superseded_by=["LIB-INV-002"]),
            make_clause(id="LIB-INV-002", superseded_by=["LIB-INV-001"]),
        ]
        result = lint_obj(make_file(clauses))
        self.assertIn("cycle-superseded-by", checks(result))

    def test_three_clause_cycle_is_detected(self):
        clauses = [
            make_clause(id="LIB-INV-001", superseded_by=["LIB-INV-002"]),
            make_clause(id="LIB-INV-002", superseded_by=["LIB-INV-003"]),
            make_clause(id="LIB-INV-003", superseded_by=["LIB-INV-001"]),
        ]
        result = lint_obj(make_file(clauses))
        self.assertIn("cycle-superseded-by", checks(result))

    def test_successor_with_invalid_id_pattern_is_detected(self):
        result = lint_obj(make_file(
            [make_clause(superseded_by=["lib-inv-002"])]))
        self.assertIn("invalid-id", checks(result))

    def test_cross_file_cycle_is_detected(self):
        a = make_file([make_clause(id="LIB-INV-001", superseded_by=["LIB-INV-002"])])
        b = make_file([make_clause(id="LIB-INV-002", superseded_by=["LIB-INV-001"])])
        result = sl.lint_data([("a.json", a), ("b.json", b)])
        self.assertIn("cycle-superseded-by", checks(result))


# ---------------------------------------------------------------------------
# Fail-closed parsing (input corruption -> exit 2 layer)
# ---------------------------------------------------------------------------

class TestInputCorruption(unittest.TestCase):
    def _lint_text(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "clauses.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return sl.lint_paths([path])

    def _assert_corrupt(self, result, category):
        self.assertTrue(result["corrupt"])
        self.assertEqual([d["category"] for d in result["diagnostics"]],
                         [category])
        for d in result["diagnostics"]:
            self.assertNotIn("Traceback", d["message"])

    def test_broken_json_is_corruption(self):
        self._assert_corrupt(self._lint_text("{ broken"), "invalid-json")

    def test_empty_file_is_corruption(self):
        self._assert_corrupt(self._lint_text(""), "invalid-json")

    def test_duplicate_json_key_is_corruption(self):
        text = '{"schema_version": 1, "schema_version": 1, "clauses": []}'
        self._assert_corrupt(self._lint_text(text), "duplicate-json-key")

    def test_non_object_toplevel_is_corruption(self):
        self._assert_corrupt(self._lint_text("[]"), "not-an-object")

    def test_missing_clauses_key_is_corruption(self):
        self._assert_corrupt(
            self._lint_text('{"schema_version": 1}'), "missing-toplevel-key")

    def test_unknown_schema_version_is_corruption(self):
        text = json.dumps({"schema_version": 99, "clauses": []})
        self._assert_corrupt(self._lint_text(text), "unknown-schema-version")

    def test_boolean_schema_version_is_corruption(self):
        text = json.dumps({"schema_version": True, "clauses": []})
        self._assert_corrupt(self._lint_text(text), "unknown-schema-version")

    def test_string_schema_version_is_corruption(self):
        text = json.dumps({"schema_version": "1", "clauses": []})
        self._assert_corrupt(self._lint_text(text), "unknown-schema-version")

    def test_non_array_clauses_is_corruption(self):
        text = json.dumps({"schema_version": 1, "clauses": "oops"})
        self._assert_corrupt(self._lint_text(text), "clauses-not-array")

    def test_oversize_file_is_corruption(self):
        self._assert_corrupt(
            self._lint_text("x" * (sl.MAX_SIZE + 1)), "file-too-large")

    def test_over_deep_nesting_is_corruption(self):
        deep = "[" * (sl.MAX_DEPTH + 1) + "1" + "]" * (sl.MAX_DEPTH + 1)
        text = '{"schema_version": 1, "clauses": ' + deep + "}"
        self._assert_corrupt(self._lint_text(text), "too-deep")

    def test_too_many_clauses_is_corruption(self):
        original = sl.MAX_CLAUSES
        sl.MAX_CLAUSES = 2
        try:
            text = json.dumps(make_file([
                make_clause(id="LIB-INV-001"),
                make_clause(id="LIB-INV-002"),
                make_clause(id="LIB-INV-003"),
            ]))
            self._assert_corrupt(self._lint_text(text), "too-many-clauses")
        finally:
            sl.MAX_CLAUSES = original

    def test_healthy_file_findings_are_still_collected_next_to_broken_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = os.path.join(tmp, "broken.json")
            healthy = os.path.join(tmp, "healthy.json")
            with open(broken, "w", encoding="utf-8") as f:
                f.write("{ broken")
            with open(healthy, "w", encoding="utf-8") as f:
                json.dump(make_file([make_clause(kind="performance")]), f)
            result = sl.lint_paths([broken, healthy])
        self.assertTrue(result["corrupt"])
        self.assertIn("unknown-kind", checks(result))


# ---------------------------------------------------------------------------
# Path containment
# ---------------------------------------------------------------------------

class TestPathContainment(unittest.TestCase):
    def test_file_inside_root_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "specs", "clauses", "a.json")
            os.makedirs(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(make_file([make_clause()]), f)
            resolved = sl.check_containment(path, tmp)
            self.assertTrue(str(resolved).endswith("a.json"))

    def test_file_outside_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            os.makedirs(root)
            outside = os.path.join(tmp, "outside.json")
            with open(outside, "w", encoding="utf-8") as f:
                f.write("{}")
            with self.assertRaises(sl.SpecLintError):
                sl.check_containment(outside, root)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            os.makedirs(root)
            target = os.path.join(tmp, "real.json")
            with open(target, "w", encoding="utf-8") as f:
                f.write("{}")
            link = os.path.join(root, "link.json")
            os.symlink(target, link)
            with self.assertRaises(sl.SpecLintError):
                sl.check_containment(link, root)

    def test_symlinked_directory_component_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            outside_dir = os.path.join(tmp, "outside")
            os.makedirs(root)
            os.makedirs(outside_dir)
            with open(os.path.join(outside_dir, "a.json"), "w",
                      encoding="utf-8") as f:
                f.write("{}")
            os.symlink(outside_dir, os.path.join(root, "sub"))
            with self.assertRaises(sl.SpecLintError):
                sl.check_containment(os.path.join(root, "sub", "a.json"), root)


# ---------------------------------------------------------------------------
# Finding format (where / what / why / how)
# ---------------------------------------------------------------------------

class TestFindingFormat(unittest.TestCase):
    def test_every_finding_carries_where_what_why_how(self):
        clause = make_clause(id="lib-bad", revision=0, kind="performance",
                             statement="")
        result = lint_obj(make_file([clause, "junk"])
                          )
        self.assertGreater(len(result["findings"]), 0)
        for f in result["findings"]:
            for key in ("where", "what", "why", "how"):
                self.assertIn(key, f)
                self.assertTrue(f[key], f"empty {key} in {f}")

    def test_where_names_both_file_and_clause(self):
        result = lint_obj(make_file([make_clause(kind="performance")]),
                          name="clauses.json")
        f = result["findings"][0]
        self.assertIn("clauses.json", f["where"])
        self.assertIn("LIB-INV-001", f["where"])

    def test_findings_are_sorted_stably_by_where(self):
        b = make_file([make_clause(id="LIB-INV-002", kind="performance")])
        a = make_file([make_clause(id="LIB-INV-001", kind="performance")])
        result = sl.lint_data([("b.json", b), ("a.json", a)])
        wheres = [f["where"] for f in result["findings"]]
        self.assertEqual(wheres, sorted(wheres))


# ---------------------------------------------------------------------------
# CLI contract (exit codes / output shape)
# ---------------------------------------------------------------------------

class TestCliContract(unittest.TestCase):
    def _write_root(self, tmp, clauses_by_name):
        clauses_dir = os.path.join(tmp, "specs", "clauses")
        os.makedirs(clauses_dir, exist_ok=True)
        for name, data in clauses_by_name.items():
            with open(os.path.join(clauses_dir, name), "w",
                      encoding="utf-8") as f:
                if isinstance(data, str):
                    f.write(data)
                else:
                    json.dump(data, f, ensure_ascii=False)
        return tmp

    def test_report_only_with_findings_exits_zero_and_flags_findings_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file(
                [make_clause(kind="performance")])})
            proc = run_cli(["--root", tmp, "--json"])
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertTrue(out["findings_present"])

    def test_strict_with_findings_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file(
                [make_clause(kind="performance")])})
            proc = run_cli(["--root", tmp, "--strict"])
        self.assertEqual(proc.returncode, 1)

    def test_strict_clean_run_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file([make_clause()])})
            proc = run_cli(["--root", tmp, "--strict"])
        self.assertEqual(proc.returncode, 0)

    def test_corruption_exits_two_in_both_modes_without_traceback(self):
        for mode in ([], ["--strict"]):
            with tempfile.TemporaryDirectory() as tmp:
                self._write_root(tmp, {"a.json": "{ broken"})
                proc = run_cli(["--root", tmp, *mode])
            self.assertEqual(proc.returncode, 2, mode)
            self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_corrupt_json_output_is_marked_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": "{ broken",
                                   "b.json": make_file(
                                       [make_clause(kind="performance")])})
            proc = run_cli(["--root", tmp, "--json"])
        self.assertEqual(proc.returncode, 2)
        out = json.loads(proc.stdout)
        self.assertFalse(out["valid"])
        # 健全ファイルの診断は収集される（部分破損でも exit 2）
        self.assertIn("unknown-kind", {f["check"] for f in out["findings"]})

    def test_zero_targets_is_a_graceful_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli(["--root", tmp, "--json"])
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertFalse(out["findings_present"])
        self.assertEqual(out["summary"]["files"], 0)

    def test_path_outside_root_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            os.makedirs(root)
            outside = os.path.join(tmp, "outside.json")
            with open(outside, "w", encoding="utf-8") as f:
                json.dump(make_file([make_clause()]), f)
            proc = run_cli(["--root", root, outside])
        self.assertEqual(proc.returncode, 2)

    def test_missing_root_directory_exits_two(self):
        proc = run_cli(["--root", "/nonexistent-spec-verify-root"])
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_max_errors_truncates_details_but_summary_keeps_total(self):
        clauses = [make_clause(id=f"LIB-INV-00{i}", kind="performance")
                   for i in range(1, 4)]
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file(clauses)})
            proc = run_cli(["--root", tmp, "--json", "--max-errors", "1"])
        out = json.loads(proc.stdout)
        self.assertEqual(len(out["findings"]), 1)
        self.assertEqual(out["summary"]["findings"], 3)
        self.assertTrue(out["summary"]["truncated"])

    def test_text_output_puts_summary_before_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file(
                [make_clause(kind="performance")])})
            proc = run_cli(["--root", tmp])
        lines = proc.stdout.splitlines()
        self.assertIn("findings=", lines[0])

    def test_text_output_strips_control_characters(self):
        clause = make_clause()
        clause["bad\x1b[31mkey"] = "x"
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file([clause])})
            proc = run_cli(["--root", tmp])
        self.assertNotIn("\x1b", proc.stdout)

    def test_free_text_secret_never_reaches_cli_output(self):
        clause = make_clause(statement=f"credential {FAKE_AWS} in text")
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file([clause])})
            text = run_cli(["--root", tmp])
            machine = run_cli(["--root", tmp, "--json"])
        self.assertNotIn(FAKE_AWS, text.stdout + text.stderr)
        self.assertNotIn(FAKE_AWS, machine.stdout + machine.stderr)

    def test_credential_shaped_invalid_id_never_reaches_cli_output(self):
        # where は mask 対象外なので、不正 ID の生値が where 経由で
        # 露出しないこと（clauses[index] フォールバック）を CLI 出力で確認する
        clause = make_clause(id=FAKE_AWS)
        with tempfile.TemporaryDirectory() as tmp:
            self._write_root(tmp, {"a.json": make_file([clause])})
            text = run_cli(["--root", tmp])
            machine = run_cli(["--root", tmp, "--json"])
        self.assertNotIn(FAKE_AWS, text.stdout + text.stderr)
        self.assertNotIn(FAKE_AWS, machine.stdout + machine.stderr)


# ---------------------------------------------------------------------------
# Sync edge 1: clause-schema.md tables <-> code constants
# ---------------------------------------------------------------------------

_BACKTICK_TOKEN = re.compile(r"`([^`]+)`")


def _md_sections(path):
    """Split clause-schema.md into {heading: [line, ...]} (## level)."""
    sections = {}
    current = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                current = line[3:].strip()
                sections[current] = []
            elif current is not None:
                sections[current].append(line.rstrip("\n"))
    return sections


def _table_rows(lines):
    """Data rows per the parse contract: '|' rows whose first or second cell
    starts with a backticked token."""
    rows = []
    for line in lines:
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0].startswith("`") or cells[1].startswith("`"):
            rows.append(cells)
    return rows


def _field_table(rows):
    """{name: (type, required)} from a field/type/required/desc table."""
    out = {}
    for cells in rows:
        name = _BACKTICK_TOKEN.match(cells[0]).group(1)
        out[name] = (_BACKTICK_TOKEN.match(cells[1]).group(1),
                     _BACKTICK_TOKEN.match(cells[2]).group(1) == "required")
    return out


# 「`from` / `event` / `to`（必須、string）と `guard`（任意、string）」形式
# （clause-schema.md パース契約に明記されたネスト規則の prose 形式）。
_NESTED_RULE_PROSE = re.compile(r"((?:`[^`]+`(?:\s*/\s*)?)+)（(必須|任意)、string）")


def _nested_rule_fields(desc):
    """{name: (type, required)} from a transitions/forbidden description cell."""
    out = {}
    for tokens, marker in _NESTED_RULE_PROSE.findall(desc):
        for name in _BACKTICK_TOKEN.findall(tokens):
            out[name] = ("string", marker == "必須")
    return out


class TestSchemaSyncMdToCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = _md_sections(CLAUSE_SCHEMA_MD)

    def test_toplevel_table_matches_code_constants(self):
        rows = _table_rows(self.sections["ファイル構造"])
        self.assertEqual(_field_table(rows), sl.TOPLEVEL_FIELDS)

    def test_envelope_table_matches_code_constants(self):
        rows = _table_rows(self.sections["共通 envelope"])
        self.assertEqual(_field_table(rows), sl.ENVELOPE_FIELDS)

    def test_payload_table_matches_code_constants(self):
        rows = _table_rows(self.sections["kind 別 discriminated payload"])
        parsed = {}
        for cells in rows:
            kind = _BACKTICK_TOKEN.match(cells[0]).group(1)
            field = _BACKTICK_TOKEN.match(cells[1]).group(1)
            parsed.setdefault(kind, {})[field] = (
                _BACKTICK_TOKEN.match(cells[2]).group(1),
                _BACKTICK_TOKEN.match(cells[3]).group(1) == "required")
        self.assertEqual(parsed, sl.PAYLOAD_FIELDS)

    def test_kind_enum_in_md_matches_code(self):
        rows = _table_rows(self.sections["共通 envelope"])
        desc = next(cells[3] for cells in rows
                    if _BACKTICK_TOKEN.match(cells[0]).group(1) == "kind")
        self.assertIn("enum:", desc)
        self.assertEqual(tuple(_BACKTICK_TOKEN.findall(
            desc.split("enum:")[1])), sl.KINDS)

    def test_effect_enum_in_md_matches_code(self):
        rows = _table_rows(self.sections["kind 別 discriminated payload"])
        desc = next(cells[4] for cells in rows
                    if _BACKTICK_TOKEN.match(cells[1]).group(1) == "effect")
        self.assertIn("enum:", desc)
        self.assertEqual(tuple(_BACKTICK_TOKEN.findall(
            desc.split("enum:")[1])), sl.EFFECT_VALUES)

    def test_id_pattern_in_md_matches_code(self):
        rows = _table_rows(self.sections["ID・revision 規則"])
        cell = next(cells[1] for cells in rows
                    if cells[0].startswith("`id` パターン"))
        self.assertEqual(_BACKTICK_TOKEN.match(cell).group(1), sl.ID_PATTERN)

    def test_min_items_fields_in_md_match_code(self):
        rows = _table_rows(self.sections["kind 別 discriminated payload"])
        marked = {_BACKTICK_TOKEN.match(cells[1]).group(1)
                  for cells in rows if "1 要素以上" in cells[4]}
        self.assertEqual(marked, set(sl.MIN_ITEMS))
        self.assertTrue(all(n == 1 for n in sl.MIN_ITEMS.values()))

    def test_transition_rule_fields_in_md_match_code(self):
        """ネスト規則はフィールド名集合だけでなく必須/任意属性まで突合する
        （説明セルの「（必須、…）」「（任意、…）」prose をパースする）。"""
        rows = _table_rows(self.sections["kind 別 discriminated payload"])
        by_field = {_BACKTICK_TOKEN.match(cells[1]).group(1): cells[4]
                    for cells in rows}
        self.assertEqual(_nested_rule_fields(by_field["transitions"]),
                         sl.TRANSITION_RULE_FIELDS)
        self.assertEqual(_nested_rule_fields(by_field["forbidden"]),
                         sl.FORBIDDEN_RULE_FIELDS)

    def test_input_limits_in_md_match_code(self):
        rows = _table_rows(
            self.sections["exit code 契約（spec_lint / trace_matrix 共通）"])
        limits = {}
        for cells in rows:
            if cells[0].startswith("`"):
                continue  # exit code 表の行（先頭セルが `0` 等）はスキップ
            limits[_BACKTICK_TOKEN.match(cells[2]).group(1)] = int(
                _BACKTICK_TOKEN.match(cells[1]).group(1))
        self.assertEqual(limits, {
            "file-too-large": sl.MAX_SIZE,
            "too-many-clauses": sl.MAX_CLAUSES,
            "too-deep": sl.MAX_DEPTH,
        })

    def test_corruption_categories_in_md_match_code(self):
        """md の破損カテゴリ箇条書き ⇔ spec_lint の SpecLintError raise 箇所。"""
        lines = self.sections["exit code 契約（spec_lint / trace_matrix 共通）"]
        md_slugs = [m.group(1) for m in
                    (re.match(r"^- `([a-z-]+)`", line) for line in lines) if m]
        with open(SPEC_LINT, encoding="utf-8") as f:
            source = f.read()
        code_slugs = set(re.findall(r'SpecLintError\(\s*"([a-z-]+)"', source))
        self.assertEqual(len(md_slugs), len(set(md_slugs)),
                         "md のカテゴリ一覧に重複がある")
        self.assertEqual(set(md_slugs), code_slugs)


# ---------------------------------------------------------------------------
# Sync edge 2: code constants <-> spec-clause.schema.json
# ---------------------------------------------------------------------------

PAYLOAD_DEFS = {
    "invariant": "invariantPayload",
    "pre_post": "prePostPayload",
    "transition": "transitionPayload",
    "authorization": "authorizationPayload",
}


def _schema():
    with open(SCHEMA_JSON, encoding="utf-8") as f:
        return json.load(f)


def _type_token(prop):
    """Map a schema property back to the md/code type token."""
    if "$ref" in prop:
        name = prop["$ref"].rsplit("/", 1)[-1]
        return "string" if name in ("nonEmptyString", "clauseId") else "object"
    if "const" in prop:
        return "integer" if isinstance(prop["const"], int) else "string"
    if "enum" in prop:
        return "string"
    t = prop.get("type")
    if t == "array":
        return f"array[{_type_token(prop.get('items', {}))}]"
    return t


def _assert_object_def(testcase, node, fields, label):
    required = {f for f, (_, req) in fields.items() if req}
    testcase.assertEqual(set(node["required"]), required, label)
    testcase.assertEqual(set(node["properties"]), set(fields), label)
    for field, (token, _) in fields.items():
        testcase.assertEqual(_type_token(node["properties"][field]), token,
                             f"{label}.{field}")


class TestSchemaSyncCodeToJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = _schema()
        cls.defs = cls.schema["definitions"]

    def test_toplevel_matches_code_constants(self):
        _assert_object_def(self, self.schema, sl.TOPLEVEL_FIELDS, "toplevel")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"],
                         sl.SCHEMA_VERSION)

    def test_clause_envelope_matches_code_constants(self):
        _assert_object_def(self, self.defs["clause"], sl.ENVELOPE_FIELDS,
                           "clause")

    def test_kind_enum_matches_code(self):
        self.assertEqual(
            tuple(self.defs["clause"]["properties"]["kind"]["enum"]), sl.KINDS)

    def test_id_pattern_matches_code(self):
        self.assertEqual(self.defs["clauseId"]["pattern"], sl.ID_PATTERN)

    def test_revision_minimum_matches_positive_integer_rule(self):
        rev = self.defs["clause"]["properties"]["revision"]
        self.assertEqual(rev["type"], "integer")
        self.assertEqual(rev["minimum"], 1)

    def test_payload_defs_match_code_constants(self):
        for kind, def_name in PAYLOAD_DEFS.items():
            _assert_object_def(self, self.defs[def_name],
                               sl.PAYLOAD_FIELDS[kind], def_name)

    def test_effect_enum_matches_code(self):
        effect = self.defs["authorizationPayload"]["properties"]["effect"]
        self.assertEqual(tuple(effect["enum"]), sl.EFFECT_VALUES)

    def test_min_items_match_code(self):
        props = self.defs["transitionPayload"]["properties"]
        for field, minimum in sl.MIN_ITEMS.items():
            self.assertEqual(props[field]["minItems"], minimum, field)

    def test_transition_rule_defs_match_code_constants(self):
        _assert_object_def(self, self.defs["transitionRule"],
                           sl.TRANSITION_RULE_FIELDS, "transitionRule")
        _assert_object_def(self, self.defs["forbiddenRule"],
                           sl.FORBIDDEN_RULE_FIELDS, "forbiddenRule")

    def test_every_object_definition_is_fail_closed(self):
        """全 object 定義（type: object + properties を持つ node）に
        additionalProperties: false が存在する（前レビュー WARN 対応の
        構造アサーション）。allOf/then の条件付き refinement は properties を
        持っても対象外 — そこに false を置くと envelope フィールド全体を
        拒否してしまうため、object 定義本体だけが fail-closed の置き場所。"""
        stack = [("$", self.schema)]
        seen = 0
        while stack:
            path, node = stack.pop()
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    seen += 1
                    self.assertIs(node.get("additionalProperties"), False,
                                  f"additionalProperties missing at {path}")
                for k, v in node.items():
                    stack.append((f"{path}.{k}", v))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    stack.append((f"{path}[{i}]", v))
        self.assertGreater(seen, 5, "schema walk found too few object defs")


# ---------------------------------------------------------------------------
# Conformance fixture corpus (driven by fixtures/README.md)
# ---------------------------------------------------------------------------

_VALID_ROW = re.compile(r"^\|\s*`valid/([^`]+)`\s*\|\s*valid\s*\|")
_INVALID_ROW = re.compile(
    r"^\|\s*`invalid/([^`]+)`\s*\|\s*invalid\s*\|\s*`([^`]+)`[^|]*\|")


def _readme_expectations():
    valid, invalid = [], {}
    with open(FIXTURES_README, encoding="utf-8") as f:
        for line in f:
            m = _VALID_ROW.match(line)
            if m:
                valid.append(m.group(1))
                continue
            m = _INVALID_ROW.match(line)
            if m:
                invalid[m.group(1)] = m.group(2)
    return valid, invalid


class TestConformanceCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid, cls.invalid = _readme_expectations()

    def test_readme_lists_every_fixture_file_and_vice_versa(self):
        on_disk_valid = sorted(os.listdir(os.path.join(FIXTURES_DIR, "valid")))
        on_disk_invalid = sorted(
            os.listdir(os.path.join(FIXTURES_DIR, "invalid")))
        self.assertEqual(sorted(self.valid), on_disk_valid)
        self.assertEqual(sorted(self.invalid), on_disk_invalid)

    def test_all_valid_fixtures_pass(self):
        self.assertTrue(self.valid)
        for name in self.valid:
            path = os.path.join(FIXTURES_DIR, "valid", name)
            result = sl.lint_paths([path])
            self.assertFalse(result["corrupt"], name)
            self.assertEqual(result["findings"], [], name)

    def test_all_invalid_fixtures_are_detected_as_readme_expects(self):
        self.assertTrue(self.invalid)
        for name, slug in self.invalid.items():
            path = os.path.join(FIXTURES_DIR, "invalid", name)
            result = sl.lint_paths([path])
            if slug in CORRUPTION_SLUGS:
                self.assertTrue(result["corrupt"], name)
                self.assertEqual(
                    [d["category"] for d in result["diagnostics"]], [slug],
                    name)
            else:
                self.assertFalse(result["corrupt"], name)
                self.assertIn(slug, checks(result), name)


if __name__ == "__main__":
    unittest.main()
