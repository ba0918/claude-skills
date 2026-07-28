#!/usr/bin/env python3
"""Mechanical regression tests for workspace-isolated entry points."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "skills/artifacts/SKILL.md"
CYCLE = ROOT / "skills/cycle/SKILL.md"
ITERATE = ROOT / "skills/iterate/SKILL.md"
ITERATE_FIXTURES = ROOT / "skills/iterate/fixtures.json"
GITHUB = ROOT / "skills/github-issue/SKILL.md"
GITHUB_FIXTURES = ROOT / "skills/github-issue/fixtures.json"
WORKTREE = ROOT / "skills/github-issue/references/worktree-cycle.md"


class Step4SkillIntegrationTests(unittest.TestCase):
    def compact(self, path):
        return " ".join(path.read_text(encoding="utf-8").split())

    def test_artifacts_documents_fresh_init_and_canonical_recovery(self):
        text = self.compact(ARTIFACTS)
        self.assertIn("only when no workspace policy, artifact policy, canonical store, or legacy store existed at command start", text)
        self.assertIn("isolation: worktree", text)
        self.assertIn("existing or partially initialized", text)
        self.assertIn("/claude-skills:artifacts recover --run-id {run_id}", text)
        self.assertIn("never chooses a conflict winner", text)
        self.assertIn("never deletes a preserved worktree", text)
        self.assertIn("resume context only when the state is `failed_readonly`", text)
        self.assertIn("Recovery never publishes automatically", text)
        self.assertIn("publish is a separate action", text)
        self.assertNotIn("an already-approved publication may be retried", text)

    def assert_outer_protocol(self, path):
        text = self.compact(path)
        resolve = text.index("Resolve isolation exactly once")
        create = text.index("Create exactly one outer worktree")
        ingress = text.index("Initialize satellite ingress")
        inner = text.index("Launch one inner run")
        collect = text.index("Collect on every terminal path")
        merge = text.index("Merge and run post-merge verification")
        publish = text.index("Publish only after verification passes")
        cleanup = text.index("Cleanup only when cleanup_allowed")
        self.assertLess(resolve, create)
        self.assertLess(create, ingress)
        self.assertLess(ingress, inner)
        self.assertLess(inner, collect)
        self.assertLess(collect, merge)
        self.assertLess(merge, publish)
        self.assertLess(publish, cleanup)
        self.assertIn("resolved_isolation=worktree", text)
        self.assertIn("must not re-resolve isolation or create a nested worktree", text)
        self.assertIn("/claude-skills:artifacts recover --run-id {satellite_run_id}", text)
        self.assertIn("In `inplace` mode, preserve the existing workflow unchanged", text)
        self.assertNotIn("otherwise deliberately discard", text)
        self.assertIn("explicit human authorization", text)
        self.assertIn("shared exact six-line formatter", text)

    def test_cycle_and_iterate_share_the_outer_protocol(self):
        self.assert_outer_protocol(CYCLE)
        self.assert_outer_protocol(ITERATE)

    def test_github_issue_uses_shared_transport_before_cleanup(self):
        text = self.compact(GITHUB)
        self.assertIn("shared satellite transport facade", text)
        self.assertNotIn("Materialize the plan into the worktree", text)
        self.assertIn("pinned_plan={repository_relative_plan_path}", text)
        self.assertIn("resolved_isolation=worktree", text)
        self.assertIn("satellite_run_id={satellite_run_id}", text)
        self.assertIn("satellite_capability_file={capability_file_path}", text)
        self.assertLess(text.index("collect on every terminal path"), text.index("remove the worktree"))
        self.assertIn("never writes the main artifact store directly", text)
        self.assertNotIn("rejected or reverted result, record deliberate discard", text)
        self.assertIn("close the issue and apply terminal labels", text)
        self.assertIn("publish failure preserves the worktree", text)
        self.assertIn("shared exact six-line formatter", text)

    def test_worktree_reference_is_shared_contract_adapter(self):
        text = self.compact(WORKTREE)
        self.assertIn("shared ingress, capability, collect, publish, and cleanup gate", text)
        self.assertIn("harvest precedes cleanup", text)
        self.assertIn("/claude-skills:artifacts recover --run-id {satellite_run_id}", text)

    def test_new_fixtures_cover_outer_inner_and_recovery(self):
        iterate = json.loads(ITERATE_FIXTURES.read_text(encoding="utf-8"))
        github = json.loads(GITHUB_FIXTURES.read_text(encoding="utf-8"))
        iterate_ids = {item["id"] for item in iterate["scenarios"]}
        github_ids = {item["id"] for item in github["scenarios"]}
        self.assertTrue({"it-outer-worktree", "it-inner-context", "it-recovery"} <= iterate_ids)
        self.assertTrue({"gi-008"} <= github_ids)


if __name__ == "__main__":
    unittest.main()
