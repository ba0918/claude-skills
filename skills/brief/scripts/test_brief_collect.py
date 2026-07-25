#!/usr/bin/env python3
"""Unit tests for brief_collect.py (input collection for the brief skill).

These tests fix the two properties the rest of the pipeline depends on:
identifiers stay stable for identical input, and the candidate set is never
empty (session context is always available as a target).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brief_collect import (  # noqa: E402
    resolve_base,
    scan_candidates,
    split_diff_hunks,
    split_document_sections,
)

DIFF_TWO_FILES = """\
diff --git a/src/a.py b/src/a.py
index 1111111..2222222 100644
--- a/src/a.py
+++ b/src/a.py
@@ -1,4 +1,5 @@
 import os
-import sys
+import json
+import re

 def main():
@@ -20,3 +21,3 @@ def main():
-    return 1
+    return 0

diff --git a/docs/b.md b/docs/b.md
index 3333333..4444444 100644
--- a/docs/b.md
+++ b/docs/b.md
@@ -5,2 +5,3 @@
 text
+more text
"""


class SplitDiffHunks(unittest.TestCase):
    def test_returns_one_entry_per_hunk_across_files(self):
        hunks = split_diff_hunks(DIFF_TWO_FILES)
        self.assertEqual(len(hunks), 3)
        self.assertEqual(
            [h["path"] for h in hunks],
            ["src/a.py", "src/a.py", "docs/b.md"],
        )

    def test_assigns_unique_identifiers(self):
        ids = [h["id"] for h in split_diff_hunks(DIFF_TWO_FILES)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_identifiers_are_stable_for_identical_input(self):
        first = [h["id"] for h in split_diff_hunks(DIFF_TWO_FILES)]
        second = [h["id"] for h in split_diff_hunks(DIFF_TWO_FILES)]
        self.assertEqual(first, second)

    def test_counts_added_and_removed_lines(self):
        hunks = split_diff_hunks(DIFF_TWO_FILES)
        self.assertEqual((hunks[0]["added"], hunks[0]["removed"]), (2, 1))
        self.assertEqual((hunks[1]["added"], hunks[1]["removed"]), (1, 1))
        self.assertEqual((hunks[2]["added"], hunks[2]["removed"]), (1, 0))

    def test_returns_empty_list_for_empty_diff(self):
        self.assertEqual(split_diff_hunks(""), [])

    def test_ignores_diff_metadata_lines_when_counting(self):
        hunks = split_diff_hunks(DIFF_TWO_FILES)
        self.assertNotIn("+++ b/src/a.py", hunks[0]["body"])


DOC_WITH_SECTIONS = """\
# Plan Title

Intro paragraph.

## Goals

- one
- two

## Design

### Sub heading

detail

## Tests

- a
"""

DOC_WITHOUT_H2 = """\
# First

body

# Second

body
"""


class SplitDocumentSections(unittest.TestCase):
    def test_splits_on_the_shallowest_repeated_heading_level(self):
        sections = split_document_sections(DOC_WITH_SECTIONS)
        self.assertEqual([s["title"] for s in sections], ["Goals", "Design", "Tests"])

    def test_nested_headings_stay_inside_their_parent_section(self):
        sections = split_document_sections(DOC_WITH_SECTIONS)
        design = [s for s in sections if s["title"] == "Design"][0]
        self.assertIn("Sub heading", design["body"])

    def test_falls_back_to_top_headings_when_no_deeper_level_exists(self):
        sections = split_document_sections(DOC_WITHOUT_H2)
        self.assertEqual([s["title"] for s in sections], ["First", "Second"])

    def test_assigns_unique_stable_identifiers(self):
        first = [s["id"] for s in split_document_sections(DOC_WITH_SECTIONS)]
        second = [s["id"] for s in split_document_sections(DOC_WITH_SECTIONS)]
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(set(first)))

    def test_returns_empty_list_for_document_without_headings(self):
        self.assertEqual(split_document_sections("just text\n"), [])


def make_runner(responses):
    """Build a git runner stub. Keys are the joined argument list."""

    def runner(args):
        return responses.get(" ".join(args), (1, ""))

    return runner


class ResolveBase(unittest.TestCase):
    def test_returns_merge_base_when_a_default_branch_exists(self):
        runner = make_runner({"merge-base HEAD main": (0, "abc123\n")})
        self.assertEqual(resolve_base(runner), "abc123")

    def test_returns_none_when_no_default_branch_resolves(self):
        self.assertIsNone(resolve_base(make_runner({})))

    def test_prefers_the_first_resolvable_default_branch(self):
        runner = make_runner(
            {
                "merge-base HEAD main": (1, ""),
                "merge-base HEAD master": (0, "def456\n"),
            }
        )
        self.assertEqual(resolve_base(runner), "def456")


class ScanCandidates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def kinds(self, candidates):
        return [c["kind"] for c in candidates]

    def test_session_context_is_always_a_candidate(self):
        candidates = scan_candidates(self.root, make_runner({}))
        self.assertEqual(self.kinds(candidates), ["discussion"])

    def test_candidate_set_is_never_empty(self):
        self.assertTrue(scan_candidates(self.root, make_runner({})))

    def test_reports_unstaged_changes_with_a_file_count(self):
        runner = make_runner({"diff --numstat": (0, "1\t0\ta.py\n2\t3\tb.py\n")})
        candidates = scan_candidates(self.root, runner)
        unstaged = [c for c in candidates if c["kind"] == "unstaged"][0]
        self.assertEqual(unstaged["count"], 2)

    def test_reports_staged_changes_separately_from_unstaged(self):
        runner = make_runner({"diff --cached --numstat": (0, "1\t0\ta.py\n")})
        self.assertIn("staged", self.kinds(scan_candidates(self.root, runner)))

    def test_omits_branch_range_when_base_cannot_be_resolved(self):
        runner = make_runner({"diff --numstat": (0, "1\t0\ta.py\n")})
        self.assertNotIn("branch", self.kinds(scan_candidates(self.root, runner)))

    def test_includes_branch_range_when_base_resolves_and_differs(self):
        runner = make_runner(
            {
                "merge-base HEAD main": (0, "abc123\n"),
                "diff --numstat abc123..HEAD": (0, "1\t0\ta.py\n5\t2\tb.py\n"),
            }
        )
        candidates = scan_candidates(self.root, runner)
        branch = [c for c in candidates if c["kind"] == "branch"][0]
        self.assertEqual(branch["count"], 2)
        self.assertEqual(branch["ref"], "abc123..HEAD")

    def test_offers_the_most_recent_plan_document(self):
        plans = os.path.join(self.root, ".agents", "artifacts", "plans")
        os.makedirs(plans)
        for name in ("20260101000000_old.md", "20260201000000_new.md"):
            with open(os.path.join(plans, name), "w", encoding="utf-8") as fh:
                fh.write("# t\n\n## S\n\nbody\n")
        candidates = scan_candidates(self.root, make_runner({}))
        plan = [c for c in candidates if c["kind"] == "plan"][0]
        self.assertTrue(plan["ref"].endswith("20260201000000_new.md"))

    def test_offers_the_most_recent_handoff_document(self):
        handoff = os.path.join(self.root, ".agents", "artifacts", "handoff")
        os.makedirs(handoff)
        with open(os.path.join(handoff, "20260101000000_h.md"), "w", encoding="utf-8") as fh:
            fh.write("# h\n")
        self.assertIn("handoff", self.kinds(scan_candidates(self.root, make_runner({}))))

    def test_every_candidate_carries_a_reader_facing_label(self):
        runner = make_runner({"diff --numstat": (0, "1\t0\ta.py\n")})
        for candidate in scan_candidates(self.root, runner):
            self.assertTrue(candidate["label"].strip())


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# CLI
#
# The skill body drives collection through a shell, so the wiring between the
# subcommands and the pure functions is part of the contract, not a detail.
# ---------------------------------------------------------------------------

import io  # noqa: E402
import json  # noqa: E402
from contextlib import redirect_stdout  # noqa: E402

import brief_collect  # noqa: E402


def run_cli(*argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = brief_collect.main(list(argv))
    return code, buffer.getvalue()


class CandidatesCommand(unittest.TestCase):
    def test_it_emits_the_candidate_list_as_json(self):
        with tempfile.TemporaryDirectory() as root:
            code, out = run_cli("candidates", "--repo", root)
            self.assertEqual(code, 0)
            self.assertEqual([c["kind"] for c in json.loads(out)], ["discussion"])


class SectionsCommand(unittest.TestCase):
    def test_it_reports_identifiers_alongside_the_section_bodies(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "doc.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# Title\n\n## One\n\nbody\n\n## Two\n\nbody\n")
            code, out = run_cli("sections", "--file", path)
            self.assertEqual(code, 0)
            payload = json.loads(out)
            self.assertEqual(payload["sections"], ["s001", "s002"])
            self.assertEqual([s["title"] for s in payload["detail"]], ["One", "Two"])


class HunksCommand(unittest.TestCase):
    def test_a_branch_range_without_a_ref_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(SystemExit):
                run_cli("hunks", "--repo", root, "--source", "branch")


class BulletOnlyDocuments(unittest.TestCase):
    """A memo is one heading and a run of bullets. Headings cannot divide it."""

    MEMO = "# 打ち合わせメモ\n\n- 検索が遅い\n- 基盤の入れ替えは今期やらない\n- キャッシュは次回\n"

    def test_it_falls_back_to_the_bullets_when_headings_do_not_divide(self):
        units = split_document_sections(self.MEMO)
        self.assertEqual([u["id"] for u in units], ["b001", "b002", "b003"])
        self.assertEqual(units[0]["title"], "検索が遅い")

    def test_a_document_with_real_sections_still_splits_by_heading(self):
        text = "# T\n\n## One\n\n- a\n- b\n\n## Two\n\n- c\n"
        units = split_document_sections(text)
        self.assertEqual([u["id"] for u in units], ["s001", "s002"])

    def test_a_bare_list_with_no_heading_at_all_still_divides(self):
        units = split_document_sections("- one\n- two\n")
        self.assertEqual([u["id"] for u in units], ["b001", "b002"])


class CandidateDetail(unittest.TestCase):
    """Two documents that both report `count: 1` are not a choice."""

    def test_document_candidates_carry_something_that_tells_them_apart(self):
        with tempfile.TemporaryDirectory() as root:
            plans = os.path.join(root, ".agents", "artifacts", "plans")
            os.makedirs(plans)
            path = os.path.join(plans, "20260720093000_retry-backoff.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# 再試行に指数バックオフを入れる\n\nbody\n")
            candidates = scan_candidates(root, lambda args: (1, ""))
            plan = [c for c in candidates if c["kind"] == "plan"][0]
            self.assertIn("20260720093000_retry-backoff.md", plan["detail"])
            self.assertIn("再試行に指数バックオフを入れる", plan["detail"])
            self.assertIn("行", plan["detail"])

    def test_every_candidate_carries_a_detail_line(self):
        with tempfile.TemporaryDirectory() as root:
            for candidate in scan_candidates(root, lambda args: (1, "")):
                self.assertTrue(candidate["detail"].strip(), candidate["kind"])
