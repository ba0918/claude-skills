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
    "### Docs: 文言整理\n\n"
    "- none — 挙動変更なし\n\n"
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
        self.assertEqual(exempt, ["Docs: 文言整理"])

    def test_prose_mention_of_the_exemption_form_does_not_exempt(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "### Docs: 免除表記の説明を追記\n\n"
            "- PR 参照の無いエントリは `none — 理由` 形式の免除を要求すると書いた\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(exempt, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("PR 参照", errors[0])

    def test_body_without_an_entry_heading_is_an_error(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "- 見出しの無い本文（#310）\n\n"
            "### A（#311）\n\n"
            "- x\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(len(errors), 1)
        self.assertIn("###", errors[0])

    def test_unreleased_section_without_any_entry_heading_is_an_error(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "- 見出し無しで置かれた唯一の本文\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(len(errors), 1)
        self.assertIn("###", errors[0])

    def test_duplicated_unreleased_heading_is_an_error(self):
        changelog = (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "### A（#307）\n\n"
            "- x\n\n"
            "## Unreleased\n\n"
            "### B（#305）\n\n"
            "- y\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(prs, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Unreleased", errors[0])

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
            "### Docs: 文言整理\n\n"
            "- none —\n\n"
        )
        prs, errors, exempt = rpc.extract_unreleased(changelog=changelog)
        self.assertEqual(exempt, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("理由が空", errors[0])

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

    def test_successful_status_context_passes(self):
        rollup = [
            {"__typename": "StatusContext", "context": "ci/legacy", "state": "SUCCESS"},
            {"__typename": "CheckRun", "name": "validate",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]
        self.assertTrue(rpc.checks_pass(rollup))

    def test_failed_status_context_fails(self):
        rollup = [
            {"__typename": "StatusContext", "context": "ci/legacy", "state": "FAILURE"},
            {"__typename": "CheckRun", "name": "validate",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]
        self.assertFalse(rpc.checks_pass(rollup))

    def test_pending_status_context_fails(self):
        rollup = [
            {"__typename": "StatusContext", "context": "ci/legacy", "state": "PENDING"},
        ]
        self.assertFalse(rpc.checks_pass(rollup))

    def test_entry_of_unrecognized_shape_fails(self):
        rollup = [{"__typename": "SomethingNew", "name": "unknown"}]
        self.assertFalse(rpc.checks_pass(rollup))

    def test_empty_rollup_fails(self):
        # check が 1 つも無い状態（CI 未発火・token 権限不足）は
        # 「全 check 緑」の証明にならない
        self.assertFalse(rpc.checks_pass([]))

    def test_non_list_input_fails(self):
        self.assertFalse(rpc.checks_pass(None))
        self.assertFalse(rpc.checks_pass({"status": "COMPLETED"}))


if __name__ == "__main__":
    unittest.main()
