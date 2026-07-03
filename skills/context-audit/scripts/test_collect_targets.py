#!/usr/bin/env python3
"""Unit tests for collect_targets.py (deterministic path-allowlist discovery)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import collect_targets as ct


class TestSlugifyCwd(unittest.TestCase):
    def test_matches_claude_code_slug(self):
        # Real Claude Code slug: leading slash and every non-alnum -> '-'
        self.assertEqual(
            ct.slugify_cwd("/home/mizumi/develop/claude-skills"),
            "-home-mizumi-develop-claude-skills",
        )

    def test_dot_and_underscore_replaced(self):
        # '.' and '_' are non-alnum and become '-' (not just '/')
        self.assertEqual(ct.slugify_cwd("/x/.claude"), "-x--claude")
        self.assertEqual(ct.slugify_cwd("/a_b/c.d"), "-a-b-c-d")

    def test_alnum_preserved(self):
        self.assertEqual(ct.slugify_cwd("abc123"), "abc123")


class TestResolveMemoryDir(unittest.TestCase):
    def test_returns_existing_project_memory(self):
        with tempfile.TemporaryDirectory() as home:
            cwd = "/proj/app"
            slug = ct.slugify_cwd(cwd)
            mem = Path(home) / ".claude" / "projects" / slug / "memory"
            mem.mkdir(parents=True)
            resolved = ct.resolve_memory_dir(cwd, Path(home))
            self.assertEqual(resolved, mem)

    def test_missing_dir_returns_none(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertIsNone(ct.resolve_memory_dir("/proj/app", Path(home)))

    def test_rejects_dir_outside_projects_root(self):
        # A symlink escaping projects/ must fail the reverse-verify (fail-safe).
        with tempfile.TemporaryDirectory() as home:
            outside = Path(home) / "elsewhere" / "memory"
            outside.mkdir(parents=True)
            cwd = "/proj/app"
            slug = ct.slugify_cwd(cwd)
            proj = Path(home) / ".claude" / "projects" / slug
            proj.mkdir(parents=True)
            (proj / "memory").symlink_to(outside)
            self.assertIsNone(ct.resolve_memory_dir(cwd, Path(home)))


class TestCollectRepoTargets(unittest.TestCase):
    def _repo(self, tmp):
        root = Path(tmp)
        (root / "CLAUDE.md").write_text("# claude", encoding="utf-8")
        (root / "AGENTS.md").write_text("# agents", encoding="utf-8")
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "a.md").write_text("rule a", encoding="utf-8")
        (root / ".claude" / "review-rules.md").write_text("rr", encoding="utf-8")
        return root

    def test_classifies_allowlisted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            result = ct.collect_repo_targets(str(root))
            kinds = {t["kind"] for t in result["targets"]}
            self.assertIn("claude_md", kinds)
            self.assertIn("agents_md", kinds)
            self.assertIn("rules", kinds)
            self.assertIn("review_rules", kinds)

    def test_missing_rules_dir_graceful_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_text("x", encoding="utf-8")
            # No .claude/rules, no rules/ -> must not crash, just fewer targets
            result = ct.collect_repo_targets(str(root))
            kinds = {t["kind"] for t in result["targets"]}
            self.assertEqual(kinds, {"claude_md"})

    def test_excludes_archival_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "docs" / "plans"
            plans.mkdir(parents=True)
            (plans / "20260101_x.md").write_text("plan", encoding="utf-8")
            (root / "CLAUDE.md").write_text("x", encoding="utf-8")
            result = ct.collect_repo_targets(str(root))
            paths = {t["path"] for t in result["targets"]}
            self.assertTrue(all("docs/plans" not in p for p in paths))

    def test_empty_repo_no_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ct.collect_repo_targets(tmp)
            self.assertEqual(result["targets"], [])


class TestReadTarget(unittest.TestCase):
    def test_reads_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.md"
            p.write_text("hello 世界", encoding="utf-8")
            self.assertEqual(ct.read_target(str(p)), "hello 世界")

    def test_non_utf8_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.md"
            p.write_bytes(b"\xff\xfe bad bytes")
            # errors='replace' -> returns a string, never raises
            out = ct.read_target(str(p))
            self.assertIsInstance(out, str)

    def test_missing_file_returns_none(self):
        self.assertIsNone(ct.read_target("/nonexistent/path/f.md"))


class TestCollectTargets(unittest.TestCase):
    def test_memory_included_when_project_dir_present(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            cwd = "/proj/app"
            slug = ct.slugify_cwd(cwd)
            mem = Path(home) / ".claude" / "projects" / slug / "memory"
            mem.mkdir(parents=True)
            (mem / "MEMORY.md").write_text("mem", encoding="utf-8")
            (Path(repo) / "CLAUDE.md").write_text("x", encoding="utf-8")
            result = ct.collect_targets(repo, Path(home), cwd, include_global=False)
            cats = {t["category"] for t in result["targets"]}
            self.assertIn("memory", cats)
            self.assertIsNotNone(result["memory_dir"])

    def test_global_excluded_by_default(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            gclaude = Path(home) / ".claude" / "CLAUDE.md"
            gclaude.parent.mkdir(parents=True)
            gclaude.write_text("global", encoding="utf-8")
            result = ct.collect_targets(repo, Path(home), "/proj/app", include_global=False)
            paths = {t["path"] for t in result["targets"]}
            self.assertNotIn(str(gclaude), paths)

    def test_global_included_with_flag(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            gclaude = Path(home) / ".claude" / "CLAUDE.md"
            gclaude.parent.mkdir(parents=True)
            gclaude.write_text("global", encoding="utf-8")
            result = ct.collect_targets(repo, Path(home), "/proj/app", include_global=True)
            kinds = {t["kind"] for t in result["targets"]}
            self.assertIn("global_claude_md", kinds)


if __name__ == "__main__":
    unittest.main()
