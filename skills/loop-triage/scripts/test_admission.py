"""admission.py の unittest。

loop-engineering.md 契約の §4 Admission Policy（fix_action x severity -> route の
純関数ルーティング）と §5 Self-Modification Gate（loop-defining ファイルの
glob 判定 + 依存グラフ逆引きによる enqueue 降格）を検証する。
"""
import unittest

import admission


class TestRouteBase(unittest.TestCase):
    """§4 の表を 3x3 全セル + 未知値 fail-safe で固定する。"""

    def test_auto_fix_block_enqueues(self):
        self.assertEqual(admission.route_base("AUTO_FIX", "BLOCK"), "enqueue")

    def test_auto_fix_warn_enqueues(self):
        self.assertEqual(admission.route_base("AUTO_FIX", "WARN"), "enqueue")

    def test_auto_fix_info_digests(self):
        self.assertEqual(admission.route_base("AUTO_FIX", "INFO"), "digest")

    def test_needs_judgment_block_inboxes(self):
        self.assertEqual(
            admission.route_base("NEEDS_JUDGMENT", "BLOCK"), "inbox")

    def test_needs_judgment_warn_inboxes(self):
        self.assertEqual(
            admission.route_base("NEEDS_JUDGMENT", "WARN"), "inbox")

    def test_needs_judgment_info_digests(self):
        self.assertEqual(
            admission.route_base("NEEDS_JUDGMENT", "INFO"), "digest")

    def test_report_only_block_digests(self):
        self.assertEqual(admission.route_base("REPORT_ONLY", "BLOCK"), "digest")

    def test_report_only_warn_digests(self):
        self.assertEqual(admission.route_base("REPORT_ONLY", "WARN"), "digest")

    def test_report_only_info_digests(self):
        self.assertEqual(admission.route_base("REPORT_ONLY", "INFO"), "digest")

    def test_unknown_fix_action_is_fail_safe_digest(self):
        self.assertEqual(admission.route_base("BOGUS", "BLOCK"), "digest")

    def test_unknown_severity_is_fail_safe_digest(self):
        self.assertEqual(admission.route_base("AUTO_FIX", "BOGUS"), "digest")

    def test_both_unknown_is_fail_safe_digest(self):
        self.assertEqual(admission.route_base("BOGUS", "BOGUS"), "digest")


class TestIsLoopDefining(unittest.TestCase):
    """§5.1 の glob 一致を固定する。** はパス区切りを跨ぎ、* は1セグメント内のみ。"""

    def test_skill_md_matches(self):
        self.assertTrue(admission.is_loop_defining("skills/issue/SKILL.md"))

    def test_skill_references_matches(self):
        self.assertTrue(
            admission.is_loop_defining("skills/issue/references/a.md"))

    def test_skill_non_reference_file_does_not_match(self):
        self.assertFalse(
            admission.is_loop_defining("skills/issue/fixtures.json"))

    def test_shared_references_matches(self):
        self.assertTrue(
            admission.is_loop_defining("skills/shared/references/x.md"))

    def test_shared_scripts_matches(self):
        self.assertTrue(
            admission.is_loop_defining("skills/shared/scripts/y.py"))

    def test_commands_matches(self):
        self.assertTrue(admission.is_loop_defining("commands/a.md"))

    def test_validate_repo_matches(self):
        self.assertTrue(
            admission.is_loop_defining("scripts/validate_repo.py"))

    def test_other_script_does_not_match(self):
        self.assertFalse(admission.is_loop_defining("scripts/other.py"))

    def test_plan_doc_does_not_match(self):
        self.assertFalse(admission.is_loop_defining(".agents/artifacts/plans/x.md"))

    def test_readme_does_not_match(self):
        self.assertFalse(admission.is_loop_defining("README.md"))

    def test_review_rules_matches(self):
        self.assertTrue(
            admission.is_loop_defining(".claude/review-rules.md"))

    def test_double_star_matches_zero_segments(self):
        """skills/shared/** は skills/shared 直下のファイルにも一致する（0 セグメント）。"""
        self.assertTrue(admission.is_loop_defining("skills/shared/x.md"))


class TestGateDecision(unittest.TestCase):
    """§5.2 のゲート規則: 非該当 / 全 fixture 保有 / 一部非保有 / 解決不能。"""

    def test_no_loop_defining_paths_is_not_gated(self):
        result = admission.gate_decision(
            [".agents/artifacts/plans/x.md", "README.md"],
            path_to_skills=lambda p: ["irrelevant"],
            skills_with_fixtures=set(),
        )
        self.assertEqual(
            result,
            {
                "gated": False,
                "demote": False,
                "affected_skills": [],
                "missing_fixtures": [],
            },
        )

    def test_all_affected_skills_have_fixtures(self):
        result = admission.gate_decision(
            ["skills/a/SKILL.md", "skills/b/references/x.md"],
            path_to_skills=lambda p: (
                ["a"] if "skills/a" in p else ["b"]
            ),
            skills_with_fixtures={"a", "b"},
        )
        self.assertTrue(result["gated"])
        self.assertFalse(result["demote"])
        self.assertEqual(result["affected_skills"], ["a", "b"])
        self.assertEqual(result["missing_fixtures"], [])

    def test_some_affected_skill_missing_fixture_demotes(self):
        result = admission.gate_decision(
            ["skills/a/SKILL.md", "skills/b/references/x.md"],
            path_to_skills=lambda p: (
                ["a"] if "skills/a" in p else ["b"]
            ),
            skills_with_fixtures={"a"},
        )
        self.assertTrue(result["gated"])
        self.assertTrue(result["demote"])
        self.assertEqual(result["affected_skills"], ["a", "b"])
        self.assertEqual(result["missing_fixtures"], ["b"])

    def test_unresolved_skills_demotes_fail_safe(self):
        result = admission.gate_decision(
            ["skills/shared/references/gate.md"],
            path_to_skills=lambda p: [],
            skills_with_fixtures={"a", "b"},
        )
        self.assertTrue(result["gated"])
        self.assertTrue(result["demote"])
        self.assertEqual(result["affected_skills"], [])
        self.assertEqual(result["missing_fixtures"], ["(unresolved)"])


class TestRoute(unittest.TestCase):
    """1 finding の最終ルーティング（ショートサーキット優先順）。"""

    def _finding(self, fix_action="AUTO_FIX", severity="BLOCK",
                 affected_paths=None):
        return {
            "fix_action": fix_action,
            "severity": severity,
            "affected_paths": affected_paths or [],
        }

    def test_suppressed_takes_priority_over_everything(self):
        result = admission.route(
            self._finding(),
            queue_ids={"deadbeef00000001"},
            baseline={"deadbeef00000001"},
            fid="deadbeef00000001",
            path_to_skills=lambda p: [],
            skills_with_fixtures=set(),
            enqueue_used=0,
        )
        self.assertEqual(result, {"route": "suppressed"})

    def test_duplicate_when_already_in_queue(self):
        result = admission.route(
            self._finding(),
            queue_ids={"cafebabe00000001"},
            baseline=set(),
            fid="cafebabe00000001",
            path_to_skills=lambda p: [],
            skills_with_fixtures=set(),
            enqueue_used=0,
        )
        self.assertEqual(result, {"route": "duplicate"})

    def test_gate_demotes_to_inbox_with_reason(self):
        result = admission.route(
            self._finding(affected_paths=["skills/a/SKILL.md"]),
            queue_ids=set(),
            baseline=set(),
            fid="feedface00000001",
            path_to_skills=lambda p: ["a"],
            skills_with_fixtures=set(),  # "a" has no fixture -> demote
            enqueue_used=0,
        )
        self.assertEqual(result["route"], "inbox")
        self.assertEqual(result["reason"], "gate")
        self.assertTrue(result["gated"])
        self.assertTrue(result["demote"])
        self.assertEqual(result["missing_fixtures"], ["a"])

    def test_budget_demotes_to_inbox_when_cap_reached(self):
        result = admission.route(
            self._finding(affected_paths=[".agents/artifacts/plans/x.md"]),
            queue_ids=set(),
            baseline=set(),
            fid="0badc0de00000001",
            path_to_skills=lambda p: [],
            skills_with_fixtures=set(),
            enqueue_used=5,
            max_enqueue_per_run=5,
        )
        self.assertEqual(result, {"route": "inbox", "reason": "budget"})

    def test_gated_enqueue_includes_gate_key(self):
        result = admission.route(
            self._finding(affected_paths=["skills/a/SKILL.md"]),
            queue_ids=set(),
            baseline=set(),
            fid="0ff1ce0000000001",
            path_to_skills=lambda p: ["a"],
            skills_with_fixtures={"a"},
            enqueue_used=0,
        )
        self.assertEqual(result["route"], "enqueue")
        self.assertEqual(result["gate"], "skill-regression")

    def test_ungated_enqueue_has_no_gate_key(self):
        result = admission.route(
            self._finding(affected_paths=[".agents/artifacts/plans/x.md"]),
            queue_ids=set(),
            baseline=set(),
            fid="abad1dea00000001",
            path_to_skills=lambda p: [],
            skills_with_fixtures=set(),
            enqueue_used=0,
        )
        self.assertEqual(result, {"route": "enqueue"})

    def test_report_only_never_enqueues(self):
        result = admission.route(
            self._finding(
                fix_action="REPORT_ONLY", severity="BLOCK",
                affected_paths=["skills/a/SKILL.md"],
            ),
            queue_ids=set(),
            baseline=set(),
            fid="deadc0de00000001",
            path_to_skills=lambda p: ["a"],
            skills_with_fixtures={"a"},
            enqueue_used=0,
        )
        self.assertEqual(result, {"route": "digest"})

    def test_unknown_fix_action_normalizes_to_report_only(self):
        result = admission.route(
            self._finding(fix_action="TOTALLY_UNKNOWN", severity="BLOCK"),
            queue_ids=set(),
            baseline=set(),
            fid="0123456789abcdef",
            path_to_skills=lambda p: [],
            skills_with_fixtures=set(),
            enqueue_used=0,
        )
        self.assertEqual(result, {"route": "digest"})


if __name__ == "__main__":
    unittest.main()


class TestGateDecisionPerPathStrictness(unittest.TestCase):
    def test_mixed_resolved_and_unresolved_paths_demote(self):
        # 片方のパスがスキルに解決できても、解決不能な loop-defining パスが
        # 1 つでもあれば per-path の fail-safe で降格する
        def resolver(path):
            return ["issue"] if path == "skills/issue/SKILL.md" else []

        result = admission.gate_decision(
            ["skills/issue/SKILL.md", "commands/unmapped.md"],
            resolver,
            {"issue"},
        )
        self.assertTrue(result["gated"])
        self.assertTrue(result["demote"])
        self.assertIn("(unresolved)", result["missing_fixtures"])
        self.assertEqual(result["affected_skills"], ["issue"])
