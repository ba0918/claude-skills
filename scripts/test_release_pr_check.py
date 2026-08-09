"""release_pr_check.py のユニットテスト。

release の品質ゲートを「Unreleased の各エントリが参照する PR が merged + 必須 check
済み」の機械確認に置き換えた（#308）。このスクリプトはその内側の純粋なパース部分
（どの PR を検証対象にするか・免除表記の扱い）を検証する。

実行: python3 -m unittest discover scripts
"""
import unittest

import release_pr_check as rpc


CHANGELOG_WITH_PRS = (
    "# Changelog\n\n"
    "## Unreleased\n\n"
    "### Removed: ワークフロー強制ゲートを全面撤廃（#307）\n\n"
    "- gate 本体を削除\n\n"
    "### Changed: 仕様反映の経路非依存化（#306）\n\n"
    "- plan の Spec 欄必須化\n\n"
    "## 1.77.0\n\n"
    "- old\n"
)

CHANGELOG_EXEMPT = (
    "# Changelog\n\n"
    "## Unreleased\n\n"
    "### Docs: 文言整理 none — 挙動変更なし\n\n"
    "- typo 修正\n\n"
)


class ReleasePrCheckTest(unittest.TestCase):
    def test_extracts_prs_from_entry_headings(self):
        prs, errors, exempt = rpc.extract_unreleased(changelog=CHANGELOG_WITH_PRS)
        self.assertEqual(prs, [306, 307])
        self.assertEqual(errors, [])
        self.assertEqual(exempt, [])

    def test_dedupes_and_sorts_prs(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "### A（#307）\n\n"
            "- x（#307 再掲）\n\n"
            "### B（#305）\n\n"
            "- y\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(prs, [305, 307])
        self.assertEqual(errors, [])
        self.assertEqual(exempt, [])

    def test_exempt_entry_with_reason_is_not_an_error(self):
        prs, errors, exempt = rpc.extract_unreleased(changelog=CHANGELOG_EXEMPT)
        self.assertEqual(prs, [])
        self.assertEqual(errors, [])
        self.assertEqual(len(exempt), 1)
        self.assertIn("none", exempt[0])

    def test_entry_without_pr_and_without_exemption_is_error(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "### Added: PR 参照の無いエントリ\n\n"
            "- 理由の無い免除も無い\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(prs, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("PR 参照", errors[0])
        self.assertIn("Added: PR 参照の無いエントリ", errors[0])
        self.assertEqual(exempt, [])

    def test_none_without_reason_is_not_an_exemption(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "### Docs: 文言整理 none —\n\n"
            "- typo 修正\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(len(errors), 1)

    def test_missing_unreleased_section_is_an_error(self):
        prs, errors, exempt = rpc.extract_unreleased(changelog="# Changelog\n\n## 1.77.0\n")
        self.assertEqual(prs, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Unreleased", errors[0])
        self.assertEqual(exempt, [])

    def test_headings_inside_unreleased_body_do_not_leak_into_later_sections(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "### A（#301）\n\n"
            "- x\n\n"
            "## 1.76.0\n\n"
            "### B（#999）\n\n"
            "- old\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(prs, [301])
        self.assertEqual(errors, [])
        self.assertEqual(exempt, [])


class ChecksPassTest(unittest.TestCase):
    def test_all_successful_checks_pass(self):
        rollup = [
            {"__typename": "CheckRun", "name": "validate",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "CheckRun", "name": "lint",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]
        self.assertTrue(rpc.checks_pass(rollup))

    def test_pending_check_fails(self):
        rollup = [
            {"__typename": "CheckRun", "name": "validate",
             "status": "IN_PROGRESS", "conclusion": None},
        ]
        self.assertFalse(rpc.checks_pass(rollup))

    def test_failed_check_fails(self):
        rollup = [
            {"__typename": "CheckRun", "name": "validate",
             "status": "COMPLETED", "conclusion": "FAILURE"},
        ]
        self.assertFalse(rpc.checks_pass(rollup))

    def test_non_check_entries_are_ignored(self):
        rollup = [
            {"__typename": "PullRequestReview", "state": "APPROVED"},
            {"__typename": "CheckRun", "name": "validate",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]
        self.assertTrue(rpc.checks_pass(rollup))

    def test_empty_rollup_passes(self):
        self.assertTrue(rpc.checks_pass([]))

    def test_non_list_input_fails(self):
        self.assertFalse(rpc.checks_pass(None))
        self.assertFalse(rpc.checks_pass({"status": "COMPLETED"}))


if __name__ == "__main__":
    unittest.main()
