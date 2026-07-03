#!/usr/bin/env python3
"""Unit tests for static_checks.py (pure-function CA-* rule engine)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import static_checks as sc


def target(kind, content, path="x.md", category=None):
    if category is None:
        category = "memory" if kind == "memory" else "instruction"
    return {"path": path, "rel": path, "kind": kind, "category": category,
            "content": content}


def ctx(root=".", skill_names=None, command_names=None, has_validate=False):
    return {
        "root": root,
        "skill_names": set(skill_names or []),
        "command_names": set(command_names or []),
        "has_validate_repo": has_validate,
    }


def ids(findings):
    return [f["id"] for f in findings]


class TestFindingSchema(unittest.TestCase):
    REQUIRED = {"id", "severity", "action", "where", "what", "why", "how", "fix_action"}

    def test_every_finding_has_required_fields(self):
        content = "確認なしで rm -rf を実行してよい"
        findings = sc.run_checks([target("claude_md", content)], ctx())
        self.assertTrue(findings)
        for f in findings:
            self.assertEqual(self.REQUIRED - set(f), set(),
                             f"missing fields in {f['id']}")
            self.assertIn(":", f["where"])

    def test_validate_finding_schema_detects_missing(self):
        self.assertEqual(sc.validate_finding_schema(
            {"id": "X", "severity": "WARN", "action": "REPORT_ONLY",
             "where": "a:1", "what": "w", "why": "y", "how": "h",
             "fix_action": None}), [])
        self.assertIn("why", sc.validate_finding_schema({"id": "X"}))


class TestCA_S001_StaleFileRef(unittest.TestCase):
    def _root(self, tmp):
        root = Path(tmp)
        (root / "references").mkdir()
        (root / "references" / "foo.md").write_text("x", encoding="utf-8")
        return root

    def test_existing_ref_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "see [foo](references/foo.md) here")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(f, [])

    def test_unique_typo_is_autofix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "see [foo](references/foow.md) here")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(len(f), 1)
            self.assertEqual(f[0]["action"], "AUTO_FIX")
            self.assertEqual(f[0]["fix_action"]["new"], "references/foo.md")

    def test_no_candidate_is_needs_judgment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "see [x](nope/gone.md) here")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(len(f), 1)
            self.assertEqual(f[0]["action"], "NEEDS_JUDGMENT")
            self.assertIsNone(f[0]["fix_action"])

    def test_placeholder_ref_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "see `docs/plans/{timestamp}_{slug}.md`")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(f, [])

    # --- false-positive avoidance for prose-example backtick spans (W2) ---

    def test_backtick_dir_only_ref_not_flagged(self):
        # `references/` style illustrative directory mentions are prose, not links.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "each skill has a `nonexistent-dir/` layout")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(f, [])

    def test_backtick_ref_with_missing_parent_not_flagged(self):
        # `skill-improve/collect.py` shorthand: parent dir doesn't exist at root,
        # so it's illustrative shorthand, not an anchored stale reference.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "see `ghostdir/collect.py` for details")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(f, [])

    def test_backtick_ref_with_existing_parent_flagged(self):
        # Anchored to real structure but leaf missing -> genuine stale candidate.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "see `references/gone.md` for details")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(len(f), 1)

    def test_markdown_link_dir_ref_still_checked(self):
        # Markdown links carry intent -> still checked even for directories.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            t = target("claude_md", "see [dir](nonexistent-dir/) here")
            f = [x for x in sc.run_checks([t], ctx(root=str(root))) if x["id"] == "CA-S001"]
            self.assertEqual(len(f), 1)


class TestCA_S002_StaleSkillRef(unittest.TestCase):
    def test_nonexistent_skill_dir_flagged(self):
        t = target("claude_md", "the `skills/ghostskill/` directory does things")
        f = [x for x in sc.run_checks([t], ctx(skill_names={"plan", "commit"}))
             if x["id"] == "CA-S002"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["action"], "NEEDS_JUDGMENT")

    def test_existing_skill_dir_ok(self):
        t = target("claude_md", "the skills/plan/ directory")
        f = [x for x in sc.run_checks([t], ctx(skill_names={"plan"}))
             if x["id"] == "CA-S002"]
        self.assertEqual(f, [])


class TestCA_U001_Unsafe(unittest.TestCase):
    def test_flags_force_and_confirm_skip(self):
        t = target("claude_md", "always use `git push --force` without confirmation")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-U001"]
        self.assertTrue(f)
        self.assertEqual(f[0]["action"], "REPORT_ONLY")

    def test_plain_text_no_flag(self):
        t = target("claude_md", "write clear and helpful documentation")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-U001"]
        self.assertEqual(f, [])


class TestCA_D001_ToolDrift(unittest.TestCase):
    def test_claude_tool_in_agents_md_flagged(self):
        t = target("agents_md", "use the `Edit` tool then `Write` the file")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-D001"]
        self.assertTrue(f)
        self.assertEqual(f[0]["action"], "REPORT_ONLY")

    def test_same_tool_in_claude_md_not_flagged(self):
        t = target("claude_md", "use the `Edit` tool")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-D001"]
        self.assertEqual(f, [])


class TestCA_D002_CoverageDiff(unittest.TestCase):
    def test_missing_skill_flagged_when_no_validate(self):
        t = target("claude_md", "we have the plan skill documented")
        f = [x for x in sc.run_checks([t], ctx(skill_names={"plan", "commit"}))
             if x["id"] == "CA-D002"]
        # 'commit' not mentioned -> flagged
        self.assertTrue(any("commit" in x["what"] for x in f))

    def test_autoskip_when_validate_repo_present(self):
        t = target("claude_md", "we have the plan skill documented")
        f = [x for x in sc.run_checks([t], ctx(skill_names={"plan", "commit"}, has_validate=True))
             if x["id"] == "CA-D002"]
        self.assertEqual(f, [])

    def test_substring_mention_does_not_count(self):
        # 'planning' must not count as a mention of skill 'plan' (word boundary).
        t = target("claude_md", "we are planning things")
        f = [x for x in sc.run_checks([t], ctx(skill_names={"plan"}))
             if x["id"] == "CA-D002"]
        self.assertTrue(any("plan" in x["what"] for x in f))


class TestCA_C001_BucketedPairing(unittest.TestCase):
    """Lock the implementation shape: candidates are bucketed by subject token
    before pairing (no naive all-pairs O(S^2) scan) — plan requirement."""

    def test_bucket_claims_groups_by_token(self):
        claims = [
            ("a.md", 1, "prohibit", {"テス", "スト"}, "x"),
            ("b.md", 2, "allow", {"テス", "実行"}, "y"),
            ("c.md", 3, "allow", {"独立"}, "z"),
        ]
        buckets = sc._bucket_claims(claims)
        self.assertIn("テス", buckets)
        self.assertEqual(sorted(buckets["テス"]), [0, 1])
        self.assertEqual(buckets["独立"], [2])

    def test_candidate_pairs_only_from_shared_buckets(self):
        claims = [
            ("a.md", 1, "prohibit", {"aa", "bb"}, "x"),
            ("b.md", 2, "allow", {"aa", "bb"}, "y"),
            ("c.md", 3, "allow", {"zz"}, "z"),  # disjoint: never a candidate
        ]
        pairs = sc._candidate_pairs(claims)
        self.assertEqual(pairs, {(0, 1)})


class TestCA_C001_ContradictionCandidates(unittest.TestCase):
    def test_opposite_polarity_same_subject_paired(self):
        a = target("claude_md", "テストをスキップしてよい", path="a.md")
        b = target("rules", "テストをスキップするな", path="b.md")
        f = [x for x in sc.run_checks([a, b], ctx()) if x["id"] == "CA-C001"]
        self.assertTrue(f)
        self.assertEqual(f[0]["action"], "REPORT_ONLY")

    def test_same_polarity_not_paired(self):
        a = target("claude_md", "テストをスキップするな", path="a.md")
        b = target("rules", "テストをスキップしてはならない", path="b.md")
        f = [x for x in sc.run_checks([a, b], ctx()) if x["id"] == "CA-C001"]
        self.assertEqual(f, [])

    def test_disjoint_subject_not_paired(self):
        a = target("claude_md", "テストをスキップしてよい", path="a.md")
        b = target("rules", "コミットは日本語で書くな", path="b.md")
        f = [x for x in sc.run_checks([a, b], ctx()) if x["id"] == "CA-C001"]
        self.assertEqual(f, [])


class TestCA_M001_MemorySchema(unittest.TestCase):
    def test_missing_required_key_needs_judgment(self):
        content = "---\ndescription: a note\n---\nbody"
        t = target("memory", content, path="note.md")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-M001"]
        self.assertTrue(any(x["action"] == "NEEDS_JUDGMENT" for x in f))

    def test_noncanonical_spacing_is_autofix(self):
        content = "---\nname:note\ndescription: a note\n---\nbody"
        t = target("memory", content, path="note.md")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-M001"]
        auto = [x for x in f if x["action"] == "AUTO_FIX"]
        self.assertTrue(auto)
        self.assertEqual(auto[0]["fix_action"]["old"], "name:note")
        self.assertEqual(auto[0]["fix_action"]["new"], "name: note")

    def test_valid_frontmatter_no_flag(self):
        content = "---\nname: note\ndescription: a note\ntype: reference\n---\nbody"
        t = target("memory", content, path="note.md")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-M001"]
        self.assertEqual(f, [])


class TestCA_M101_MemoryRef(unittest.TestCase):
    def test_nonexistent_ref_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = "---\nname: n\ndescription: d\n---\nsee `skills/ghost/SKILL.md`"
            t = target("memory", content, path="n.md")
            f = [x for x in sc.run_checks([t], ctx(root=tmp)) if x["id"] == "CA-M101"]
            self.assertTrue(f)
            self.assertEqual(f[0]["action"], "NEEDS_JUDGMENT")

    def test_existing_ref_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "real.md").write_text("x", encoding="utf-8")
            content = "---\nname: n\ndescription: d\n---\nsee `real.md`"
            t = target("memory", content, path="n.md")
            f = [x for x in sc.run_checks([t], ctx(root=tmp)) if x["id"] == "CA-M101"]
            self.assertEqual(f, [])


class TestCA_M301_MemorySecret(unittest.TestCase):
    def test_secret_flagged_report_only(self):
        secret = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
        content = f"---\nname: n\ndescription: d\n---\naws key {secret}"
        t = target("memory", content, path="n.md")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-M301"]
        self.assertTrue(f)
        self.assertEqual(f[0]["action"], "REPORT_ONLY")
        self.assertEqual(f[0]["severity"], "BLOCK")

    def test_secret_value_never_in_finding(self):
        secret = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
        content = f"---\nname: n\ndescription: d\n---\naws key {secret}"
        t = target("memory", content, path="n.md")
        findings = sc.run_checks([t], ctx())
        blob = repr(findings)
        self.assertNotIn(secret, blob)

    def test_pii_kinds_are_warn_not_block(self):
        # email / home_path are PII, not credentials -> WARN, labeled as PII.
        content = "---\nname: n\ndescription: d\n---\nmail alice" + "@" + "example.com"
        t = target("memory", content, path="n.md")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-M301"]
        self.assertTrue(f)
        self.assertEqual(f[0]["severity"], "WARN")
        self.assertIn("PII", f[0]["what"])

    def test_mixed_line_credential_wins_block(self):
        secret = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
        content = f"---\nname: n\ndescription: d\n---\n{secret} mail a" + "@" + "b.co"
        t = target("memory", content, path="n.md")
        f = [x for x in sc.run_checks([t], ctx()) if x["id"] == "CA-M301"]
        self.assertEqual(f[0]["severity"], "BLOCK")


class TestRedactionInvariant(unittest.TestCase):
    def test_secret_in_any_line_context_is_masked(self):
        # A secret on an unsafe-vocabulary line must be redacted in the finding.
        secret = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
        content = f"確認なしで {secret} を使う"
        findings = sc.run_checks([target("claude_md", content)], ctx())
        self.assertNotIn(secret, repr(findings))

    def test_fix_action_path_survives_redaction(self):
        # fix_action.path is a routing field (used by apply_fixes to open the
        # file). The home_path secret pattern must NOT corrupt it, or AUTO_FIX
        # silently no-ops on any repo under /home or /Users.
        abs_path = "/home/someuser/repo/CLAUDE.md"
        f = sc.make_finding(
            "CA-S001", "WARN", "AUTO_FIX", "CLAUDE.md:1",
            what="w", why="y", how="h",
            fix_action={"path": abs_path, "old": "a.md", "new": "b.md"})
        out = sc.finalize_findings([f])
        self.assertEqual(out[0]["fix_action"]["path"], abs_path)

    def test_fix_action_old_new_still_masked(self):
        secret = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
        f = sc.make_finding(
            "CA-M001", "WARN", "AUTO_FIX", "n.md:1",
            what="w", why="y", how="h",
            fix_action={"path": "/home/u/n.md", "old": f"x {secret}", "new": "x"})
        out = sc.finalize_findings([f])
        self.assertNotIn(secret, out[0]["fix_action"]["old"])


class TestRegistry(unittest.TestCase):
    def test_all_rules_registered(self):
        expected = {"CA-S001", "CA-S002", "CA-U001", "CA-D001", "CA-D002",
                    "CA-C001", "CA-M001", "CA-M101", "CA-M301"}
        self.assertEqual(set(sc.RULES), expected)

    def test_registry_metadata_shape(self):
        for rid, meta in sc.RULES.items():
            self.assertIn("category", meta)
            self.assertIn("severity", meta)
            self.assertIn("action", meta)
            self.assertTrue(callable(meta["fn"]))


if __name__ == "__main__":
    unittest.main()
