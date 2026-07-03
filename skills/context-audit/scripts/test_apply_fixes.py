#!/usr/bin/env python3
"""Unit tests for apply_fixes.py (deterministic AUTO_FIX application)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apply_fixes as af


def s001(path, old, new):
    return {"id": "CA-S001", "action": "AUTO_FIX",
            "fix_action": {"path": path, "old": old, "new": new}}


def m001(path, old, new):
    return {"id": "CA-M001", "action": "AUTO_FIX",
            "fix_action": {"path": path, "old": old, "new": new}}


class TestPathReplacement(unittest.TestCase):
    def test_replaces_markdown_link(self):
        content = "see [foo](references/foow.md) end"
        out = af.apply_fixes(content, [s001("f.md", "references/foow.md", "references/foo.md")])
        self.assertIn("(references/foo.md)", out)
        self.assertNotIn("foow.md", out)

    def test_replaces_backtick_ref(self):
        content = "the `references/foow.md` file"
        out = af.apply_fixes(content, [s001("f.md", "references/foow.md", "references/foo.md")])
        self.assertIn("`references/foo.md`", out)

    def test_idempotent(self):
        content = "see [foo](references/foow.md) end"
        fixes = [s001("f.md", "references/foow.md", "references/foo.md")]
        once = af.apply_fixes(content, fixes)
        twice = af.apply_fixes(once, fixes)
        self.assertEqual(once, twice)


class TestFrontmatterNormalization(unittest.TestCase):
    def test_normalizes_key_spacing(self):
        content = "---\nname:note\ndescription: d\n---\nbody text"
        out = af.apply_fixes(content, [m001("n.md", "name:note", "name: note")])
        self.assertIn("name: note", out)

    def test_body_bytes_unchanged(self):
        content = "---\nname:note\ndescription: d\n---\nbody `name:note` text"
        out = af.apply_fixes(content, [m001("n.md", "name:note", "name: note")])
        # The body's literal 'name:note' inside backticks must NOT be touched.
        body_in = content.split("---", 2)[2]
        body_out = out.split("---", 2)[2]
        self.assertEqual(body_in, body_out)

    def test_idempotent(self):
        content = "---\nname:note\ndescription: d\n---\nbody"
        fixes = [m001("n.md", "name:note", "name: note")]
        once = af.apply_fixes(content, fixes)
        twice = af.apply_fixes(once, fixes)
        self.assertEqual(once, twice)

    def test_crlf_line_normalized_preserving_terminator(self):
        # CRLF files: the '\r' suffix must not defeat the match, and the
        # terminator must be preserved (no line-ending churn).
        content = "---\r\nname:note\r\ndescription: d\r\n---\r\nbody"
        out = af.apply_fixes(content, [m001("n.md", "name:note", "name: note")])
        self.assertIn("name: note\r\n", out)
        self.assertTrue(out.endswith("body"))


class TestSelectivity(unittest.TestCase):
    def test_needs_judgment_is_noop(self):
        content = "see [x](nope/gone.md) end"
        finding = {"id": "CA-S001", "action": "NEEDS_JUDGMENT", "fix_action": None}
        self.assertEqual(af.apply_fixes(content, [finding]), content)

    def test_report_only_is_noop(self):
        content = "some content"
        finding = {"id": "CA-U001", "action": "REPORT_ONLY", "fix_action": None}
        self.assertEqual(af.apply_fixes(content, [finding]), content)

    def test_multiple_fixes_applied(self):
        content = "[a](references/foow.md) and `references/barr.md`"
        fixes = [
            s001("f.md", "references/foow.md", "references/foo.md"),
            s001("f.md", "references/barr.md", "references/bar.md"),
        ]
        out = af.apply_fixes(content, fixes)
        self.assertIn("references/foo.md", out)
        self.assertIn("references/bar.md", out)


if __name__ == "__main__":
    unittest.main()
