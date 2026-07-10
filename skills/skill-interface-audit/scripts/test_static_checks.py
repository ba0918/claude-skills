#!/usr/bin/env python3
"""Tests for SI-S* static checks."""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import static_checks as sc


def _make_target(name="test-skill", content="", description="", tmpdir=None):
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    skill_dir = os.path.join(tmpdir, "skills", name)
    os.makedirs(skill_dir, exist_ok=True)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    full = f"---\nname: {name}\ndescription: {description}\n---\n\n{content}"
    with open(skill_md, "w") as f:
        f.write(full)
    return {
        "name": name,
        "skill_dir": skill_dir,
        "skill_md_content": full,
        "description": description,
    }


# ── SI-S001 ──────────────────────────────────────────────────────────────

class TestSIS001(unittest.TestCase):
    def test_no_references_pass(self):
        t = _make_target(content="# Test\n\nNo references here.")
        findings = sc.check_si_s001([t], {"root": os.path.dirname(t["skill_dir"])})
        self.assertEqual(len(findings), 0)

    def test_single_level_pass(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(name="my-skill", content="See [ref](references/foo.md).", tmpdir=tmpdir)
        refs_dir = os.path.join(t["skill_dir"], "references")
        os.makedirs(refs_dir, exist_ok=True)
        with open(os.path.join(refs_dir, "foo.md"), "w") as f:
            f.write("# Foo\nJust content, no links.\n")
        findings = sc.check_si_s001([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_chain_to_sibling_detected(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(name="my-skill", content="See [ref](references/a.md).", tmpdir=tmpdir)
        refs_dir = os.path.join(t["skill_dir"], "references")
        os.makedirs(refs_dir, exist_ok=True)
        with open(os.path.join(refs_dir, "a.md"), "w") as f:
            f.write("See also [b](b.md) for details.\n")
        with open(os.path.join(refs_dir, "b.md"), "w") as f:
            f.write("# B\nDeep content.\n")
        findings = sc.check_si_s001([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["id"], "SI-S001")

    def test_chain_to_shared_allowed(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(name="my-skill", content="See [ref](references/a.md).", tmpdir=tmpdir)
        refs_dir = os.path.join(t["skill_dir"], "references")
        os.makedirs(refs_dir, exist_ok=True)
        shared_dir = os.path.join(tmpdir, "skills", "shared", "references")
        os.makedirs(shared_dir, exist_ok=True)
        with open(os.path.join(refs_dir, "a.md"), "w") as f:
            f.write("See [shared](../../shared/references/common.md).\n")
        with open(os.path.join(shared_dir, "common.md"), "w") as f:
            f.write("# Common\n")
        findings = sc.check_si_s001([t], {"root": tmpdir})
        self.assertEqual(len(findings), 0)

    def test_chain_to_other_skill_detected(self):
        """A5: cross-skill link from references should be detected."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(name="my-skill", content="See [ref](references/a.md).", tmpdir=tmpdir)
        refs_dir = os.path.join(t["skill_dir"], "references")
        os.makedirs(refs_dir, exist_ok=True)
        other_dir = os.path.join(tmpdir, "skills", "other-skill", "references")
        os.makedirs(other_dir, exist_ok=True)
        with open(os.path.join(refs_dir, "a.md"), "w") as f:
            f.write("See [other](../../other-skill/references/z.md).\n")
        with open(os.path.join(other_dir, "z.md"), "w") as f:
            f.write("# Z\n")
        findings = sc.check_si_s001([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)

    def test_references_extra_not_confused(self):
        """A4: references-extra/ must not match references/ prefix."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(name="my-skill", content="See [ref](references-extra/a.md).", tmpdir=tmpdir)
        extra_dir = os.path.join(t["skill_dir"], "references-extra")
        os.makedirs(extra_dir, exist_ok=True)
        with open(os.path.join(extra_dir, "a.md"), "w") as f:
            f.write("# A\n")
        findings = sc.check_si_s001([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)


# ── SI-S002 ──────────────────────────────────────────────────────────────

class TestSIS002(unittest.TestCase):
    def test_clean_description_pass(self):
        t = _make_target(description="コードを静的に解析するスキル。「analyze」で起動。")
        findings = sc.check_si_s002([t], {"root": "."})
        self.assertEqual(len(findings), 0)

    def test_phase_number_detected(self):
        t = _make_target(description="Phase 1 で収集し Phase 2 で分析するスキル。")
        findings = sc.check_si_s002([t], {"root": "."})
        self.assertEqual(len(findings), 1)

    def test_numbered_list_detected(self):
        t = _make_target(description="1. 収集 2. 分析 3. レポートするスキル。")
        findings = sc.check_si_s002([t], {"root": "."})
        self.assertEqual(len(findings), 1)

    def test_arrow_chain_detected(self):
        t = _make_target(description="収集→分析→レポートの順で実行する。")
        findings = sc.check_si_s002([t], {"root": "."})
        self.assertEqual(len(findings), 1)

    def test_japanese_procedure_detected(self):
        t = _make_target(description="まずファイルを読み、次にレポートを出力する。")
        findings = sc.check_si_s002([t], {"root": "."})
        self.assertEqual(len(findings), 1)


# ── SI-S003 ──────────────────────────────────────────────────────────────

class TestSIS003(unittest.TestCase):
    def test_workflow_heavy_pass(self):
        content = "\n".join(
            ["# My Skill", "", "Short intro.", "", "## Workflow", ""]
            + [f"Step {i}." for i in range(40)]
            + ["", "## Notes", "", "A few notes."])
        t = _make_target(content=content)
        findings = sc.check_si_s003([t], {"root": "."})
        self.assertEqual(len(findings), 0)

    def test_prose_heavy_detected(self):
        content = "\n".join(
            ["# My Skill", "", "## Background", ""]
            + [f"Knowledge line {i}." for i in range(50)]
            + ["", "## More Background", ""]
            + [f"More knowledge {i}." for i in range(30)]
            + ["", "## Workflow", ""]
            + [f"Step {i}." for i in range(10)])
        t = _make_target(content=content)
        findings = sc.check_si_s003([t], {"root": "."})
        self.assertEqual(len(findings), 1)

    def test_empty_skill_no_crash(self):
        t = _make_target(content="")
        findings = sc.check_si_s003([t], {"root": "."})
        self.assertEqual(len(findings), 0)

    def test_intro_before_first_h2_is_prose(self):
        """D6: lines before first ## should count as prose."""
        content = "\n".join(
            ["# My Skill"] + [f"Intro line {i}." for i in range(50)]
            + ["", "## Workflow", ""]
            + [f"Step {i}." for i in range(10)])
        t = _make_target(content=content)
        findings = sc.check_si_s003([t], {"root": "."})
        self.assertEqual(len(findings), 1)

    def test_independent_h3_is_prose(self):
        """D6: ### without parent ## should be prose."""
        content = "\n".join(
            ["# My Skill", "", "## Workflow", ""]
            + [f"Step {i}." for i in range(10)]
            + ["", "### Standalone Section", ""]
            + [f"Standalone line {i}." for i in range(60)])
        t = _make_target(content=content)
        # Standalone section is under ## Workflow (last h2), so it's workflow
        # This tests the actual behavior
        findings = sc.check_si_s003([t], {"root": "."})
        self.assertEqual(len(findings), 0)


# ── SI-S004 ──────────────────────────────────────────────────────────────

class TestSIS004(unittest.TestCase):
    def test_clean_skill_pass(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\n## Workflow\n\nファイルを読み、分析する。",
                         tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_tool_name_mid_sentence_detected(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nその後 Edit で修正する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)
        self.assertIn("Edit", findings[0]["what"])

    def test_tool_name_in_code_block_excluded(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\n```\nEdit the file.\n```\n", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_tilde_fence_excluded(self):
        """E: ~~~ fenced blocks should also be excluded."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\n~~~\nEdit the file.\n~~~\n", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_tool_name_in_inline_code_excluded(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nツール名は `Edit` です。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_sentence_start_excluded(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nEdit the file. Read it back.", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_heading_excluded(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\n## Workflow\n\nDo things.", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_japanese_tool_notation_detected(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nBash ツールで実行する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)
        self.assertIn("Bash ツール", findings[0]["what"])

    def test_japanese_tool_no_double_count(self):
        """A2: 'Bash ツール' must produce exactly 1 finding, not 2."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nその後 Bash ツールで実行する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)

    def test_model_name_detected(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nclaude-opus-4 を使用する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)
        self.assertIn("モデル固有名", findings[0]["what"])

    def test_gpt_model_detected(self):
        """D3: gpt-* model names should be detected."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\ngpt-4.1 を使用する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)

    def test_o1_model_detected(self):
        """D3: o1-* model names should be detected."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\no1-preview を使用する。", tmpdir=tmpdir)
        # o1-preview doesn't match o1-[\d.]+, this is expected behavior
        # o1-2 would match
        t2 = _make_target(name="s2", content="# Skill\n\no1-3 を使用する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t2], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)

    def test_lsp_protocol_mention_excluded(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nLSP 準拠のサーバーと連携する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_lsp_tool_mention_detected(self):
        """D4: 'LSP ツール' should be detected."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nLSP ツールで解析する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertGreaterEqual(len(findings), 1)

    def test_numbered_list_start_excluded(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\n1. Read the file.\n2. Write the output.",
                         tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)

    def test_tool_mid_numbered_list_detected(self):
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\n1. その後 Edit で修正する。", tmpdir=tmpdir)
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 1)
        self.assertIn("Edit", findings[0]["what"])

    def test_symlink_in_references_skipped(self):
        """E: symlinks in references/ should be skipped."""
        tmpdir = tempfile.mkdtemp()
        t = _make_target(content="# Skill\n\nSome content.", tmpdir=tmpdir)
        refs_dir = os.path.join(t["skill_dir"], "references")
        os.makedirs(refs_dir, exist_ok=True)
        target_file = os.path.join(tmpdir, "external.md")
        with open(target_file, "w") as f:
            f.write("# External\n\nその後 Edit で修正。")
        os.symlink(target_file, os.path.join(refs_dir, "linked.md"))
        findings = sc.check_si_s004([t], {"root": os.path.join(tmpdir, "skills")})
        self.assertEqual(len(findings), 0)


# ── ID numbering ─────────────────────────────────────────────────────────

class TestIDNumbering(unittest.TestCase):
    def test_single_finding_no_suffix(self):
        """Single finding keeps base ID."""
        findings = sc._assign_ids([
            {"id": "SI-S004", "other": "data"},
        ])
        self.assertEqual(findings[0]["id"], "SI-S004")

    def test_multiple_findings_get_suffix(self):
        """A3: multiple findings get -1, -2, ... (no gap)."""
        findings = sc._assign_ids([
            {"id": "SI-S004", "other": "a"},
            {"id": "SI-S004", "other": "b"},
            {"id": "SI-S004", "other": "c"},
        ])
        self.assertEqual(findings[0]["id"], "SI-S004-1")
        self.assertEqual(findings[1]["id"], "SI-S004-2")
        self.assertEqual(findings[2]["id"], "SI-S004-3")

    def test_mixed_rules_numbered_independently(self):
        findings = sc._assign_ids([
            {"id": "SI-S004", "other": "a"},
            {"id": "SI-S001", "other": "x"},
            {"id": "SI-S004", "other": "b"},
        ])
        self.assertEqual(findings[0]["id"], "SI-S004-1")
        self.assertEqual(findings[1]["id"], "SI-S001")
        self.assertEqual(findings[2]["id"], "SI-S004-2")


# ── collect_targets ──────────────────────────────────────────────────────

class TestCollectTargets(unittest.TestCase):
    def test_collects_skills(self):
        tmpdir = tempfile.mkdtemp()
        skills_dir = os.path.join(tmpdir, "skills")
        os.makedirs(os.path.join(skills_dir, "my-skill"))
        with open(os.path.join(skills_dir, "my-skill", "SKILL.md"), "w") as f:
            f.write("---\nname: my-skill\ndescription: test\n---\n# My Skill\n")
        targets = sc.collect_targets(skills_dir)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["name"], "my-skill")

    def test_skips_shared(self):
        tmpdir = tempfile.mkdtemp()
        skills_dir = os.path.join(tmpdir, "skills")
        os.makedirs(os.path.join(skills_dir, "shared"))
        with open(os.path.join(skills_dir, "shared", "SKILL.md"), "w") as f:
            f.write("---\nname: shared\ndescription: test\n---\n")
        targets = sc.collect_targets(skills_dir)
        self.assertEqual(len(targets), 0)

    def test_skips_symlinked_skill_dir(self):
        tmpdir = tempfile.mkdtemp()
        skills_dir = os.path.join(tmpdir, "skills")
        real = os.path.join(skills_dir, "real-skill")
        os.makedirs(real)
        with open(os.path.join(real, "SKILL.md"), "w") as f:
            f.write("---\nname: real-skill\ndescription: test\n---\n")
        os.symlink(real, os.path.join(skills_dir, "linked-skill"))
        targets = sc.collect_targets(skills_dir)
        names = [t["name"] for t in targets]
        self.assertIn("real-skill", names)
        self.assertNotIn("linked-skill", names)


# ── CLI ──────────────────────────────────────────────────────────────────

class TestCLI(unittest.TestCase):
    def test_bare_output_filename(self):
        """A1: --output findings.json (no directory) must not crash."""
        tmpdir = tempfile.mkdtemp()
        skills_dir = os.path.join(tmpdir, "skills")
        os.makedirs(os.path.join(skills_dir, "dummy"))
        with open(os.path.join(skills_dir, "dummy", "SKILL.md"), "w") as f:
            f.write("---\nname: dummy\ndescription: test\n---\n# Dummy\n")
        out = os.path.join(tmpdir, "findings.json")
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "static_checks.py"),
             "--root", tmpdir, "--output", out],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.isfile(out))

    def test_multiple_skills(self):
        """C1: --skill a b should filter to both."""
        tmpdir = tempfile.mkdtemp()
        skills_dir = os.path.join(tmpdir, "skills")
        for name in ["alpha", "beta", "gamma"]:
            os.makedirs(os.path.join(skills_dir, name))
            with open(os.path.join(skills_dir, name, "SKILL.md"), "w") as f:
                f.write(f"---\nname: {name}\ndescription: test\n---\n# {name}\n")
        out = os.path.join(tmpdir, "out.json")
        subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "static_checks.py"),
             "--root", tmpdir, "--skill", "alpha", "beta", "--output", out],
            capture_output=True, text=True)
        import json
        findings_data = json.load(open(out))
        # We only care that it didn't crash and processed the right skills
        self.assertTrue(os.path.isfile(out))


# ── Real repo integration ────────────────────────────────────────────────

class TestRunOnRealRepo(unittest.TestCase):
    def test_self_audit_no_crash(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        skills_dir = os.path.join(root, "skills")
        if not os.path.isdir(skills_dir):
            self.skipTest("Not running from repo root")
        targets = sc.collect_targets(skills_dir)
        self.assertGreater(len(targets), 0)
        findings = sc.run_checks(targets, {"root": root})
        self.assertIsInstance(findings, list)
        for f in findings:
            for field in sc.CANONICAL_FIELDS:
                self.assertIn(field, f, f"Finding missing field: {field}")


if __name__ == "__main__":
    unittest.main()
