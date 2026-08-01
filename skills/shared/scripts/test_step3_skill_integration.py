#!/usr/bin/env python3
"""Mechanical regression tests for worktree transport skill integration."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
PARALLEL = ROOT / "skills/parallel-cycle/SKILL.md"
MERGE = ROOT / "skills/parallel-cycle/references/merge-strategy.md"
PLAN_IMPLEMENT = ROOT / "skills/plan-implement/SKILL.md"
FIXTURES = ROOT / "skills/plan-implement/fixtures.json"
CYCLE = ROOT / "skills/cycle/SKILL.md"
CYCLE_INNER = ROOT / "skills/cycle/references/inner-satellite.md"
CYCLE_COMPLETION = ROOT / "skills/cycle/references/completion.md"
CYCLE_FIXTURES = ROOT / "skills/cycle/fixtures.json"


class Step3SkillIntegrationTests(unittest.TestCase):
    RECOVERY_TEMPLATE = (
        "reason_code={reason_code}\n"
        "run_id={satellite_run_id}\n"
        "main_tree_path={main_tree_path}\n"
        "worktree_path={worktree_path_or_unavailable}\n"
        "reason={reason}\n"
        "recovery_command=/claude-skills:artifacts recover --run-id {satellite_run_id}"
    )

    def test_parallel_cycle_orders_ingress_before_delegate_and_collect_before_merge(self):
        text = PARALLEL.read_text(encoding="utf-8")
        create = text.index("**Create the worktree**")
        ingress = text.index("**Initialize satellite and ingress the pinned plan**")
        delegate = text.index("**Run the cycle**")
        collect = text.index("**Collect the satellite store**")
        merge = text.index("### Step 3.2: Merge Each Successful Branch")
        publish = text.index("**Publish collected artifacts**")
        cleanup = text.index("### Step 3.4: Cleanup")
        self.assertLess(create, ingress)
        self.assertLess(ingress, delegate)
        self.assertLess(delegate, collect)
        self.assertLess(collect, merge)
        self.assertLess(merge, publish)
        self.assertLess(publish, cleanup)

    def test_each_plan_gets_unique_satellite_identity_but_result_keeps_batch_identity(self):
        text = PARALLEL.read_text(encoding="utf-8")
        self.assertIn("batch_run_id={batch_run_id}", text)
        self.assertIn("satellite_run_id={batch_run_id}-{plan_id}", text)
        self.assertIn("derive `{satellite_run_id}` from `{batch_run_id}` and `{plan_id}`", text)
        self.assertIn("pinned_plan={repository_relative_plan_path}", text)
        self.assertIn("resolved_isolation=worktree", text)
        self.assertIn("satellite_capability_file={capability_file_path}", text)
        self.assertIn("Never place the raw capability", text)
        self.assertIn(
            "/claude-skills:artifacts recover --run-id {satellite_run_id}", text
        )
        self.assertIn(
            ".agents/artifacts/plans/results/{batch_run_id}_parallel_result.md", text
        )

    def test_two_plan_ingress_has_distinct_runtime_and_recovery_targets(self):
        text = " ".join(PARALLEL.read_text(encoding="utf-8").split())
        self.assertIn(
            "Plan A: satellite_run_id={batch_run_id}-A; "
            "Plan B: satellite_run_id={batch_run_id}-B", text,
        )
        self.assertIn(
            "runtime/provenance, capability file, staging, lifecycle, and recovery command "
            "are keyed by `{satellite_run_id}`", text,
        )
        self.assertIn(
            "batch summary and result filename are keyed only by `{batch_run_id}`", text,
        )

    def test_every_terminal_path_collects_and_failed_harvest_preserves_recovery(self):
        text = " ".join(PARALLEL.read_text(encoding="utf-8").split())
        self.assertIn(
            "success, implementation failure, cancellation, and verification failure",
            text,
        )
        self.assertIn(
            "/claude-skills:artifacts recover --run-id {satellite_run_id}", text,
        )
        self.assertIn("collect failure or conflict", text)
        self.assertIn("must not remove the worktree", text)

    def test_merge_strategy_separates_collect_publish_and_cleanup(self):
        text = " ".join(MERGE.read_text(encoding="utf-8").split())
        self.assertIn("Collect before merge", text)
        self.assertIn("Publish only after the merge and post-merge verification pass", text)
        self.assertIn("cleanup_allowed", text)
        self.assertIn("collect or publish fails", text)

    def test_plan_implement_defines_satellite_mode_without_weakening_gates(self):
        text = " ".join(PLAN_IMPLEMENT.read_text(encoding="utf-8").split())
        self.assertIn("Satellite execution context", text)
        self.assertIn("store-relative `pinned_plan`", text)
        self.assertIn("read the capability from `satellite_capability_file`", text)
        self.assertIn("records progress in the runtime progress file", text)
        self.assertIn("must not invoke `plan`", text)
        self.assertIn("must not write `status.md`, `session-history.md`, or derived indexes", text)
        self.assertIn("TDD, review, verification, and per-step commits remain mandatory", text)

    def test_cycle_accepts_resolved_satellite_context_without_outer_orchestration(self):
        # The inner-satellite deltas are canonical in references/inner-satellite.md;
        # the SKILL keeps the parameter contract and a mandatory read of that file.
        skill = " ".join(CYCLE.read_text(encoding="utf-8").split())
        inner = " ".join(CYCLE_INNER.read_text(encoding="utf-8").split())
        self.assertIn(
            "store-relative `pinned_plan`, `resolved_isolation=worktree`, "
            "`satellite_run_id`, and `satellite_capability_file`", skill,
        )
        self.assertIn("references/inner-satellite.md", skill)
        self.assertIn("skip workspace claim and release", inner)
        self.assertIn("do not auto-select or re-resolve the plan", inner)
        self.assertIn("do not create or switch branches or create a nested worktree", inner)
        self.assertIn(
            "pass the complete satellite context unchanged to `plan-implement`", inner,
        )
        self.assertIn(
            "suppress `status.md`, `session-history.md`, and derived-index writes", inner,
        )

    def test_cycle_passes_inner_context_to_implement_delegate(self):
        text = " ".join(CYCLE_INNER.read_text(encoding="utf-8").split())
        self.assertIn(
            "append the complete resolved context to the implementation prompt", text,
        )

    def test_inner_phase2_defers_outer_owned_artifacts_and_issue_close_but_keeps_commits(self):
        # Deferral and relay facts are canonical in references/completion.md;
        # commit mandatoriness in references/inner-satellite.md.
        skill = " ".join(CYCLE.read_text(encoding="utf-8").split())
        inner = " ".join(CYCLE_INNER.read_text(encoding="utf-8").split())
        completion = " ".join(CYCLE_COMPLETION.read_text(encoding="utf-8").split())
        self.assertIn("references/completion.md", skill)
        self.assertIn(
            "defer result-artifact composition to the outer orchestrator", completion,
        )
        self.assertIn(
            "skip singleton status and session-history composition", completion,
        )
        self.assertIn(
            "must not auto-close a linked issue", completion,
        )
        self.assertIn(
            "tracked implementation commits remain mandatory", inner,
        )
        self.assertIn(
            "return the implementation counts, commit list, "
            "plan status, review verdict and findings summary, "
            "final gate verdict, linked issue slug, and "
            "phase failures", completion,
        )

    def test_all_terminal_diagnostics_use_shared_formatter_and_exact_reason_codes(self):
        parallel = PARALLEL.read_text(encoding="utf-8")
        merge = MERGE.read_text(encoding="utf-8")
        self.assertIn(self.RECOVERY_TEMPLATE, parallel)
        self.assertIn(self.RECOVERY_TEMPLATE, merge)
        text = " ".join(parallel.split())
        for code in ("SATELLITE_PRESERVED", "HARVEST_CONFLICT", "HARVEST_INTERRUPTED"):
            self.assertIn(f"`reason_code={code}`", text)
        self.assertNotIn("--run-id {run_id}", merge)
        self.assertNotIn(
            "report `/claude-skills:artifacts recover --run-id", parallel,
        )
        self.assertNotIn(
            "recovery command `/claude-skills:artifacts recover --run-id", parallel,
        )

    def test_plan_implement_fixture_covers_satellite_mode(self):
        data = json.loads(FIXTURES.read_text(encoding="utf-8"))
        scenario = next(item for item in data["scenarios"] if item["id"] == "pi-004")
        requirements = " ".join(item["text"] for item in scenario["requirements"])
        self.assertIn("repository-relative pinned_plan", requirements)
        self.assertIn("satellite_capability_file", requirements)
        self.assertIn("status.md", requirements)
        self.assertIn("session-history.md", requirements)
        self.assertIn("derived index", requirements)
        self.assertIn("TDD", requirements)
        self.assertIn("commit", requirements)

    def test_cycle_fixture_covers_inner_satellite_context(self):
        data = json.loads(CYCLE_FIXTURES.read_text(encoding="utf-8"))
        scenario = next(item for item in data["scenarios"] if item["id"] == "cy-004")
        requirements = " ".join(item["text"] for item in scenario["requirements"])
        for expected in (
            "pinned_plan", "resolved_isolation", "satellite_run_id",
            "satellite_capability_file", "workspace claim", "nested worktree",
            "plan-implement", "singleton",
            "result artifact", "issue close", "outer orchestrator", "tracked commit",
        ):
            self.assertIn(expected, requirements)


if __name__ == "__main__":
    unittest.main()
