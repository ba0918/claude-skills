#!/usr/bin/env python3
"""Unit tests for aggregate_report.py (baseline suppression + report skeleton)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aggregate_report as ar


def finding(id="CA-S001", severity="WARN", action="NEEDS_JUDGMENT",
            where="a.md:1", what="w", fix_action=None):
    return {"id": id, "severity": severity, "action": action, "where": where,
            "what": what, "why": "y", "how": "h", "fix_action": fix_action}


class TestFindingId(unittest.TestCase):
    def test_deterministic(self):
        f = finding()
        self.assertEqual(ar.finding_id(f), ar.finding_id(dict(f)))

    def test_opaque_not_raw_content(self):
        f = finding(what="a secret-ish detail")
        fid = ar.finding_id(f)
        self.assertNotIn("secret-ish detail", fid)
        self.assertTrue(all(c in "0123456789abcdef" for c in fid))

    def test_distinct_findings_distinct_ids(self):
        self.assertNotEqual(
            ar.finding_id(finding(where="a.md:1")),
            ar.finding_id(finding(where="a.md:2")),
        )


class TestSuppression(unittest.TestCase):
    def test_removes_matching_and_counts(self):
        f1, f2 = finding(where="a.md:1"), finding(where="a.md:2")
        baseline = {"suppressions": [ar.finding_id(f1)]}
        kept, suppressed = ar.apply_suppression([f1, f2], baseline)
        self.assertEqual(len(kept), 1)
        self.assertEqual(suppressed, 1)
        self.assertEqual(kept[0]["where"], "a.md:2")

    def test_none_baseline_keeps_all(self):
        f1, f2 = finding(where="a.md:1"), finding(where="a.md:2")
        kept, suppressed = ar.apply_suppression([f1, f2], None)
        self.assertEqual(len(kept), 2)
        self.assertEqual(suppressed, 0)


class TestSummarize(unittest.TestCase):
    def test_counts_by_action(self):
        fs = [finding(action="AUTO_FIX"), finding(action="AUTO_FIX"),
              finding(action="REPORT_ONLY")]
        s = ar.summarize(fs)
        self.assertEqual(s["AUTO_FIX"], 2)
        self.assertEqual(s["REPORT_ONLY"], 1)
        self.assertEqual(s["NEEDS_JUDGMENT"], 0)

    def test_counts_by_severity(self):
        fs = [finding(severity="BLOCK"), finding(severity="WARN")]
        s = ar.summarize(fs)
        self.assertEqual(s["by_severity"]["BLOCK"], 1)
        self.assertEqual(s["by_severity"]["WARN"], 1)


class TestBuildReport(unittest.TestCase):
    def test_top_line_counts(self):
        fs = [finding(action="AUTO_FIX", where="a.md:1"),
              finding(action="NEEDS_JUDGMENT", where="a.md:2")]
        baseline = {"suppressions": [ar.finding_id(finding(action="AUTO_FIX", where="a.md:1"))]}
        report = ar.build_report(fs, baseline)
        self.assertEqual(report["summary"]["total"], 1)
        self.assertEqual(report["summary"]["suppressed"], 1)
        self.assertEqual(report["summary"]["NEEDS_JUDGMENT"], 1)

    def test_action_not_recomputed(self):
        f = finding(id="CA-M001", action="AUTO_FIX", fix_action={"path": "n", "old": "a", "new": "b"})
        report = ar.build_report([f], None)
        self.assertEqual(report["findings"][0]["action"], "AUTO_FIX")

    def test_severity_desc_order(self):
        fs = [finding(severity="INFO", where="a.md:1"),
              finding(severity="BLOCK", where="a.md:2"),
              finding(severity="WARN", where="a.md:3")]
        report = ar.build_report(fs, None)
        sevs = [f["severity"] for f in report["findings"]]
        self.assertEqual(sevs, ["BLOCK", "WARN", "INFO"])

    def test_deterministic(self):
        fs = [finding(where="a.md:1"), finding(where="b.md:2", severity="BLOCK")]
        self.assertEqual(ar.build_report(fs, None), ar.build_report(fs, None))

    def test_finding_id_attached(self):
        report = ar.build_report([finding()], None)
        self.assertIn("finding_id", report["findings"][0])


class TestBuildBaseline(unittest.TestCase):
    def test_contains_only_opaque_ids(self):
        fs = [finding(where="a.md:1", what="sensitive detail"),
              finding(where="a.md:2")]
        baseline = ar.build_baseline(fs)
        self.assertEqual(baseline["version"], 1)
        self.assertEqual(len(baseline["suppressions"]), 2)
        blob = repr(baseline)
        self.assertNotIn("sensitive detail", blob)
        self.assertNotIn("a.md", blob)

    def test_roundtrip_suppresses_everything(self):
        fs = [finding(where="a.md:1"), finding(where="a.md:2")]
        baseline = ar.build_baseline(fs)
        kept, suppressed = ar.apply_suppression(fs, baseline)
        self.assertEqual(kept, [])
        self.assertEqual(suppressed, 2)

    def test_deterministic_sorted(self):
        fs = [finding(where="b.md:9"), finding(where="a.md:1")]
        b1 = ar.build_baseline(fs)
        b2 = ar.build_baseline(list(reversed(fs)))
        self.assertEqual(b1, b2)


if __name__ == "__main__":
    unittest.main()
