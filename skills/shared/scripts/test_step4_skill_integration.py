#!/usr/bin/env python3
"""Mechanical regression tests for workspace-isolated entry points."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "skills/artifacts/SKILL.md"
CYCLE = ROOT / "skills/cycle/SKILL.md"
ITERATE = ROOT / "skills/iterate/SKILL.md"
PUBLICATION = ROOT / "skills/shared/references/publication-protocol.md"
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
        pub_ref = text.index("publication protocol")
        self.assertLess(resolve, create)
        self.assertLess(create, ingress)
        self.assertLess(ingress, inner)
        self.assertLess(inner, collect)
        self.assertLess(collect, pub_ref)
        self.assertIn("publication-protocol.md", text)
        self.assertIn("resolved_isolation=worktree", text)
        self.assertIn("must not re-resolve isolation or create a nested worktree", text)
        self.assertIn("/claude-skills:artifacts recover --run-id {satellite_run_id}", text)
        self.assertIn("In `inplace` mode, preserve the existing workflow unchanged", text)
        self.assertNotIn("otherwise deliberately discard", text)
        self.assertIn("shared exact six-line formatter", text)
        self.assertIn("merge, verify, and advance main", text)

    def test_cycle_and_iterate_share_the_outer_protocol(self):
        self.assert_outer_protocol(CYCLE)
        self.assert_outer_protocol(ITERATE)

    def test_publication_protocol_shared_reference_exists(self):
        text = self.compact(PUBLICATION)
        self.assertIn("prospective merge", text)
        self.assertIn("Publish only after main is advanced", text)
        self.assertIn("Cleanup only when", text)
        self.assertIn("Publication succeeded", text)
        self.assertIn("explicit human authorization", text)
        self.assertIn("compare-and-swap", text)
        self.assertIn("quality-gate-contract", text)
        self.assertIn("evidence_check.py", text)
        self.assertIn("machine_verified", text)
        self.assertIn("semantic_reviewed", text)
        cas_retry = text.index("second CAS failure")
        terminal = text.index("Terminal publish failure")
        self.assertLess(cas_retry, terminal)

    def test_publication_protocol_operational_invariants(self):
        text = self.compact(PUBLICATION)
        # producer and checker are pinned to one evidence directory
        self.assertIn("--evidence-dir {evidence_dir}", text)
        self.assertIn("Producer and checker must name the same `{evidence_dir}`", text)
        # exclusive access precedes the clean check, the CAS, and the destructive sync
        lock = text.index("workspace lock")
        clean = text.index("status --porcelain` prints nothing")
        cas = text.index("update-ref refs/heads/main {post_merge_sha} {expected_main_sha}")
        reset = text.index("reset --hard refs/heads/main")
        self.assertLess(lock, clean)
        self.assertLess(clean, cas)
        self.assertLess(cas, reset)
        # without the lock, a checked-out main terminates BEFORE the CAS —
        # never a ref advance that strands the checkout
        nolock_stop = text.index("before step 3's compare-and-swap")
        self.assertLess(lock, nolock_stop)
        self.assertLess(nolock_stop, cas)
        self.assertIn("the destructive reset in step 4 is forbidden", text)
        # the prospective merge is one fixed worktree procedure, not a menu
        self.assertIn("worktree add --detach {tmp_merge_root} {expected_main_sha}", text)
        self.assertIn("merge --no-ff {satellite_branch}", text)
        self.assertNotIn("or equivalent", text)
        # prospective evidence stages per-SHA and only promotes after the CAS
        self.assertIn("evidence-staging/{post_merge_sha}", text)
        self.assertIn("Never write prospective evidence into the default evidence directory", text)
        promote = text.index("Promote the evidence")
        self.assertLess(reset, promote)
        # promotion is copy -> verify -> delete, so a mid-copy crash is repairable
        self.assertIn("copy — never move —", text)
        self.assertIn("Copy-then-verify-then-delete", text)
        # the CAS is the commit point; later steps repair forward, never roll back
        self.assertIn("commit point", text)
        self.assertLess(cas, text.index("commit point"))
        # interrupted completion is detected from durable state, not process memory
        self.assertIn("durable marker", text)
        # a main checked out in a foreign worktree stops the publish before the CAS
        foreign = text.index("any worktree other than")
        self.assertLess(foreign, cas)
        # semantic evidence delegates ledger and convergence to the contract
        self.assertIn("§4.3", text)
        self.assertIn("convergence conditions of §5", text)
        self.assertIn("target the exact `{post_merge_sha}` tree", text)

    def test_cycle_warn_autofix_relay_names_its_result_file(self):
        text = self.compact(CYCLE)
        self.assertIn("{run_id}_fix-warn.md", text)
        self.assertIn("`{role}` = `fix-warn`", text)

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
