"""sensors.py の純関数（parse_validate_output / parse_ledger_check / map_context_audit）のテスト。

契約: skills/shared/references/loop-engineering.md §2 Finding Schema
"""

import unittest

from sensors import map_context_audit, parse_ledger_check, parse_validate_output


class ParseValidateOutputTest(unittest.TestCase):
    def test_pass_output_returns_empty_list(self):
        text = "✓ 全チェック合格\n"
        self.assertEqual(parse_validate_output(text), [])

    def test_two_violations_one_with_path_one_without(self):
        text = (
            "✗ 2 件の違反:\n"
            "  [frontmatter] description がない: commands/foo.md\n"
            "  [frontmatter] description がない: commands/bar\n"
        )
        findings = parse_validate_output(text)
        self.assertEqual(len(findings), 2)

        first = findings[0]
        self.assertEqual(first["sensor"], "validate-repo")
        self.assertEqual(first["rule"], "frontmatter")
        self.assertEqual(first["severity"], "BLOCK")
        self.assertEqual(first["fix_action"], "NEEDS_JUDGMENT")
        self.assertEqual(first["where"], {"path": "commands/foo.md"})
        self.assertEqual(
            first["what"],
            "[frontmatter] description がない: commands/foo.md",
        )
        self.assertEqual(first["suggested_title"], "validate: [frontmatter] を解消する")
        self.assertEqual(first["affected_paths"], ["commands/foo.md"])

        second = findings[1]
        self.assertEqual(second["rule"], "frontmatter")
        self.assertEqual(second["where"], {"path": "."})
        self.assertEqual(second["affected_paths"], [])
        self.assertEqual(
            second["what"],
            "[frontmatter] description がない: commands/bar",
        )

    def test_tag_extraction_with_hyphenated_tag(self):
        text = "  [update-manifest] 台帳が古い: skills/foo/sync.json\n"
        findings = parse_validate_output(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "update-manifest")
        self.assertEqual(findings[0]["where"]["path"], "skills/foo/sync.json")

    def test_non_bracket_lines_are_ignored(self):
        text = "✗ 1 件の違反:\n  [drift] README.md が言及していない: foo\n何か他の行\n"
        findings = parse_validate_output(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "drift")


class ParseLedgerCheckTest(unittest.TestCase):
    def test_two_stale_skills_parse_enumerated_files(self):
        text = (
            "[stale] plan: skills/plan/SKILL.md, skills/plan/references/foo.md\n"
            "[stale] iterate: skills/iterate/SKILL.md\n"
            "✗ 2 件。skill-regression の run ワークフローで再評価してから ledger.py --update すること\n"
        )
        findings = parse_ledger_check(text)
        self.assertEqual(len(findings), 2)

        first = findings[0]
        self.assertEqual(first["sensor"], "ledger-check")
        self.assertEqual(first["rule"], "stale")
        self.assertEqual(first["severity"], "WARN")
        self.assertEqual(first["fix_action"], "NEEDS_JUDGMENT")
        self.assertEqual(first["where"], {"path": "skills/plan/fixtures.json"})
        self.assertEqual(
            first["what"],
            "[stale] plan: skills/plan/SKILL.md, skills/plan/references/foo.md",
        )
        self.assertEqual(first["suggested_title"], "skill-regression: plan を再評価する")
        self.assertEqual(
            first["affected_paths"],
            ["skills/plan/SKILL.md", "skills/plan/references/foo.md"],
        )

        second = findings[1]
        self.assertEqual(second["where"], {"path": "skills/iterate/fixtures.json"})
        self.assertEqual(second["affected_paths"], ["skills/iterate/SKILL.md"])

    def test_unverified_skill_has_no_enumerated_files(self):
        text = (
            "[unverified] doc-write: fixtures.json はあるが検証記録がない"
            "（skill-regression run 後に --update）\n"
        )
        findings = parse_ledger_check(text)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["rule"], "unverified")
        self.assertEqual(finding["where"], {"path": "skills/doc-write/fixtures.json"})
        self.assertEqual(finding["affected_paths"], [])
        self.assertEqual(finding["suggested_title"], "skill-regression: doc-write を再評価する")

    def test_all_verified_output_returns_empty_list(self):
        text = "✓ regression ledger: 全スキル検証済み\n"
        self.assertEqual(parse_ledger_check(text), [])


class MapContextAuditTest(unittest.TestCase):
    def test_where_with_path_and_line_is_decomposed(self):
        raw = [{
            "id": "CA-D001",
            "severity": "WARN",
            "fix_action": "NEEDS_JUDGMENT",
            "where": "a.md:12",
            "what": "老朽化した指示が残っている",
        }]
        findings = map_context_audit(raw)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["sensor"], "context-audit")
        self.assertEqual(finding["rule"], "CA-D001")
        self.assertEqual(finding["severity"], "WARN")
        self.assertEqual(finding["fix_action"], "NEEDS_JUDGMENT")
        self.assertEqual(finding["where"], {"path": "a.md", "line": 12})
        self.assertEqual(finding["what"], "老朽化した指示が残っている")
        self.assertEqual(
            finding["suggested_title"], "context-audit: CA-D001 老朽化した指示が残っている",
        )
        self.assertEqual(finding["affected_paths"], ["a.md"])

    def test_where_with_path_only(self):
        raw = [{
            "id": "CA-D002",
            "severity": "INFO",
            "fix_action": "REPORT_ONLY",
            "where": "skills/shared/references/testing-anti-patterns.md",
            "what": "matched secret-like pattern",
        }]
        findings = map_context_audit(raw)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(
            finding["where"], {"path": "skills/shared/references/testing-anti-patterns.md"},
        )
        self.assertNotIn("line", finding["where"])
        self.assertEqual(
            finding["affected_paths"],
            ["skills/shared/references/testing-anti-patterns.md"],
        )

    def test_pass_severity_is_excluded(self):
        raw = [
            {
                "id": "CA-D001",
                "severity": "PASS",
                "fix_action": "REPORT_ONLY",
                "where": "a.md",
                "what": "問題なし",
            },
            {
                "id": "CA-D003",
                "severity": "BLOCK",
                "fix_action": "NEEDS_JUDGMENT",
                "where": "b.md:5",
                "what": "有害な指示",
            },
        ]
        findings = map_context_audit(raw)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "CA-D003")

    def test_missing_why_is_tolerated(self):
        raw = [{
            "id": "CA-D004",
            "severity": "WARN",
            "fix_action": "NEEDS_JUDGMENT",
            "where": "c.md:3",
            "what": "矛盾する指示",
            # why キーなし
        }]
        findings = map_context_audit(raw)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["what"], "矛盾する指示")
        self.assertNotIn("why", findings[0])

    def test_why_is_carried_through(self):
        # SKILL Step 5 の「概要 = what + why」が成立するよう、why を写像で落とさない
        raw = [{
            "id": "CA-D005",
            "severity": "WARN",
            "fix_action": "AUTO_FIX",
            "where": "d.md:7",
            "what": "旧形式の表記",
            "why": "機械的置換で解消する",
        }]
        findings = map_context_audit(raw)
        self.assertEqual(findings[0]["why"], "機械的置換で解消する")


class TestCliContextAudit(unittest.TestCase):
    """SKILL.md が規定する --context-audit PATH の取り込み経路（CLI 統合）。"""

    def test_context_audit_flag_merges_findings(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        script = Path(__file__).resolve().parent / "sensors.py"
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ca = tdp / "ca.json"
            ca.write_text(json.dumps([
                {"id": "CA-S001", "severity": "WARN",
                 "fix_action": "NEEDS_JUDGMENT",
                 "where": "CLAUDE.md:10", "what": "古い指示"},
                {"id": "CA-S002", "severity": "PASS",
                 "fix_action": "REPORT_ONLY",
                 "where": "CLAUDE.md:20", "what": "問題なし"},
            ]))
            out = tdp / "out.json"
            # repo-root は validate/ledger スクリプトが存在しない空ディレクトリ
            # （_run_capture が空文字扱い → 機械センサー findings は 0 件）
            r = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(tdp),
                 "--out", str(out), "--context-audit", str(ca)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            findings = json.loads(out.read_text())
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["sensor"], "context-audit")
            self.assertEqual(findings[0]["rule"], "CA-S001")


if __name__ == "__main__":
    unittest.main()
