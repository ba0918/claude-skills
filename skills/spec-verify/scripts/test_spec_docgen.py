#!/usr/bin/env python3
"""Unit tests for spec_docgen (TDD — written before the implementation).

Covers: the generation-marker + read-only header contract (the view is never
a second source of truth), the summary table / per-clause sections /
tombstone-draft accounting, free-text safety (raw-HTML and link injection
neutralized, field-aware secret masking), deterministic output, the --output
write rules (containment, 正本ツリー保護, marker-gated overwrite), and the
CLI exit contract (0 = view generated even with unverified clauses — docgen
is not a gate; 2 = input corruption / usage error, nothing written).
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import spec_docgen as sd  # noqa: E402
import spec_lint as sl  # noqa: E402
import test_trace_matrix as ttm  # noqa: E402  (clause/manifest fixture 再利用)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC_DOCGEN = os.path.join(SCRIPTS_DIR, "spec_docgen.py")

FAKE_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"


def gen(clauses, manifest_data=None, draft_files=0):
    view, _result = sd.generate(
        [("clauses.json", ttm.make_clause_file(clauses))],
        manifest_data, draft_files=draft_files)
    return view


def verified_input():
    clauses = [ttm.make_clause()]
    m = ttm.manifest(bindings=[ttm.binding()],
                     observations=[ttm.observation()])
    return clauses, m


def run_cli(args):
    return subprocess.run(
        [sys.executable, SPEC_DOCGEN, *args],
        capture_output=True, text=True)


# ---------------------------------------------------------------------------
# View contract (marker / header / summary / detail / tombstone)
# ---------------------------------------------------------------------------

class TestViewContract(unittest.TestCase):
    def test_first_line_is_the_generation_marker(self):
        clauses, m = verified_input()
        view = gen(clauses, m)
        self.assertTrue(view.splitlines()[0].startswith(sd.MARKER_PREFIX))

    def test_header_declares_readonly_and_source_of_truth(self):
        clauses, m = verified_input()
        view = gen(clauses, m)
        self.assertIn("編集禁止", view)
        self.assertIn("specs/clauses/", view)

    def test_summary_table_carries_level_cases_and_last_verified(self):
        clauses, m = verified_input()
        view = gen(clauses, m)
        table_row = next(line for line in view.splitlines()
                         if line.startswith(f"| `{ttm.CLAUSE_ID}`"))
        self.assertIn("property", table_row)
        self.assertIn("100", table_row)
        self.assertIn("2026-07-17T04:10:34Z", table_row)

    def test_detail_section_includes_statement_rationale_examples_and_tests(self):
        clauses = [ttm.make_clause(
            rationale="上限超過は会計と信頼性を壊す",
            examples=["貸出 3 冊 / 上限 5 → 貸出可"],
            counterexamples=["貸出 5 冊 / 上限 5 → 貸出不可"])]
        m = ttm.manifest(bindings=[ttm.binding()],
                         observations=[ttm.observation()])
        view = gen(clauses, m)
        self.assertIn("会員の貸出中冊数は貸出上限を超えない", view)
        self.assertIn("上限超過は会計と信頼性を壊す", view)
        self.assertIn("貸出 3 冊 / 上限 5 → 貸出可", view)
        self.assertIn("貸出 5 冊 / 上限 5 → 貸出不可", view)
        self.assertIn(f"`{ttm.TEST_ID}`", view)

    def test_tombstone_is_listed_separately_with_successors(self):
        clauses = [
            ttm.make_clause(),
            ttm.make_clause(id="LIB-INV-002",
                            superseded_by=["LIB-INV-003"]),
            ttm.make_clause(id="LIB-INV-003"),
        ]
        view = gen(clauses, ttm.manifest())
        self.assertIn("`LIB-INV-002` → 後継: `LIB-INV-003`", view)
        # tombstone は一覧表・詳細に現れない（別掲のみ）
        self.assertNotIn("| `LIB-INV-002`", view)
        self.assertNotIn("### `LIB-INV-002`", view)

    def test_statement_summary_is_truncated_and_full_text_survives(self):
        long_statement = "あ" * 60
        view = gen([ttm.make_clause(statement=long_statement)],
                   ttm.manifest())
        self.assertIn("あ" * 40 + "…", view)
        self.assertIn(long_statement, view)

    def test_unverified_clause_without_manifest_still_renders(self):
        view = gen([ttm.make_clause()], None)
        self.assertIn("unverified", view)
        self.assertTrue(view.splitlines()[0].startswith(sd.MARKER_PREFIX))


# ---------------------------------------------------------------------------
# Free-text safety (自由文はデータ — HTML / リンク注入と secret を無効化)
# ---------------------------------------------------------------------------

class TestViewSafety(unittest.TestCase):
    def test_raw_html_in_statement_is_escaped(self):
        view = gen([ttm.make_clause(
            statement="<script>alert(1)</script> | x")], ttm.manifest())
        self.assertNotIn("<script>", view)
        self.assertIn("&lt;script&gt;", view)

    def test_pipe_in_statement_does_not_break_the_table(self):
        view = gen([ttm.make_clause(statement="a | b")], ttm.manifest())
        self.assertIn("a \\| b", view)

    def test_link_injection_is_neutralized(self):
        view = gen([ttm.make_clause(
            statement="[evil](https://evil.example)")], ttm.manifest())
        # 角括弧がエスケープされリンク構文 [text](url) が成立しない
        self.assertNotIn("[evil](https://evil.example)", view)
        self.assertIn("\\[evil\\](https://evil.example)", view)

    def test_secret_is_masked_but_clause_and_test_ids_survive(self):
        clauses = [ttm.make_clause(rationale=f"key {FAKE_AWS} を使う")]
        m = ttm.manifest(bindings=[ttm.binding()],
                         observations=[ttm.observation()])
        view = gen(clauses, m)
        self.assertNotIn(FAKE_AWS, view)
        self.assertIn(ttm.CLAUSE_ID, view)
        self.assertIn(ttm.TEST_ID, view)

    def test_output_is_deterministic_for_identical_input(self):
        clauses, m = verified_input()
        self.assertEqual(gen(clauses, m), gen(clauses, m))


# ---------------------------------------------------------------------------
# --output write rules (containment / 正本ツリー保護 / marker-gated overwrite)
# ---------------------------------------------------------------------------

class TestOutputGuard(unittest.TestCase):
    def test_specs_toplevel_target_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "specs"))
            path = os.path.join(tmp, "specs", "SPEC.md")
            self.assertEqual(sd.check_output_path(path, tmp, False),
                             os.path.realpath(path))

    def test_specs_clauses_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sl.SpecLintError):
                sd.check_output_path(
                    os.path.join(tmp, "specs", "clauses", "README.md"),
                    tmp, False)

    def test_specs_evidence_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sl.SpecLintError):
                sd.check_output_path(
                    os.path.join(tmp, "specs", "evidence", "view.md"),
                    tmp, False)

    def test_git_dir_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sl.SpecLintError):
                sd.check_output_path(
                    os.path.join(tmp, ".git", "view.md"), tmp, False)

    def test_target_outside_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sl.SpecLintError):
                sd.check_output_path(
                    os.path.join(tmp, "..", "view.md"), tmp, False)

    def test_existing_non_docgen_file_requires_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "SPEC.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 手書きの仕様書\n")
            with self.assertRaises(sl.SpecLintError):
                sd.check_output_path(path, tmp, False)
            self.assertEqual(sd.check_output_path(path, tmp, True),
                             os.path.realpath(path))

    def test_existing_docgen_file_is_overwritable_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "SPEC.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(sd.MARKER_PREFIX + " ... -->\n古いビュー\n")
            self.assertEqual(sd.check_output_path(path, tmp, False),
                             os.path.realpath(path))


# ---------------------------------------------------------------------------
# CLI exit contract
# ---------------------------------------------------------------------------

class TestCliContract(unittest.TestCase):
    def test_stdout_view_and_exit_zero(self):
        clauses, m = verified_input()
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses=clauses, manifest_data=m)
            proc = run_cli(["--root", tmp])
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(proc.stdout.startswith(sd.MARKER_PREFIX))

    def test_unverified_clauses_are_not_a_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses=[ttm.make_clause()],
                           manifest_data=ttm.manifest())
            proc = run_cli(["--root", tmp])
            self.assertEqual(proc.returncode, 0)
            self.assertIn("unverified", proc.stdout)

    def test_output_writes_view_and_allows_regeneration(self):
        clauses, m = verified_input()
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses=clauses, manifest_data=m)
            out = os.path.join(tmp, "specs", "SPEC.md")
            proc = run_cli(["--root", tmp, "--output", out])
            self.assertEqual(proc.returncode, 0)
            with open(out, encoding="utf-8") as f:
                self.assertTrue(f.read().startswith(sd.MARKER_PREFIX))
            proc = run_cli(["--root", tmp, "--output", out])
            self.assertEqual(proc.returncode, 0)

    def test_output_under_specs_clauses_is_a_usage_error(self):
        clauses, m = verified_input()
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses=clauses, manifest_data=m)
            out = os.path.join(tmp, "specs", "clauses", "README.md")
            proc = run_cli(["--root", tmp, "--output", out])
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(os.path.exists(out))

    def test_corrupt_clause_file_exits_two_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses="{ not json")
            out = os.path.join(tmp, "view.md")
            proc = run_cli(["--root", tmp, "--output", out])
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(os.path.exists(out))

    def test_explicit_missing_manifest_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses=[ttm.make_clause()])
            proc = run_cli(["--root", tmp, "--manifest",
                            os.path.join(tmp, "nope.json")])
            self.assertEqual(proc.returncode, 2)

    def test_missing_default_manifest_generates_unverified_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses=[ttm.make_clause()])
            proc = run_cli(["--root", tmp])
            self.assertEqual(proc.returncode, 0)
            self.assertIn("unverified", proc.stdout)

    def test_draft_files_are_counted_but_never_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ttm.write_root(tmp, clauses=[ttm.make_clause()],
                           manifest_data=ttm.manifest())
            drafts = os.path.join(tmp, ".agents", "artifacts",
                                  "spec-verify", "drafts")
            os.makedirs(drafts)
            with open(os.path.join(drafts, "x.json"), "w",
                      encoding="utf-8") as f:
                f.write("{ broken json")
            proc = run_cli(["--root", tmp])
            self.assertEqual(proc.returncode, 0)
            self.assertIn("draft: 1", proc.stdout)


if __name__ == "__main__":
    unittest.main()
