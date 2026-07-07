import unittest

import triage


def _f(sensor="s", rule="r", severity="WARN", fix_action="AUTO_FIX",
       path="docs/x.md", what="w", title="t", affected=None):
    return {
        "sensor": sensor, "rule": rule, "severity": severity,
        "fix_action": fix_action, "where": {"path": path}, "what": what,
        "suggested_title": title,
        "affected_paths": affected if affected is not None else [path],
    }


def _no_impact(_path):
    return []


class TestOrderFindings(unittest.TestCase):
    def test_block_first_then_deterministic(self):
        fs = [_f(severity="INFO", what="c"), _f(severity="BLOCK", what="b"),
              _f(severity="WARN", what="a")]
        out = triage.order_findings(fs)
        self.assertEqual([f["severity"] for f in out], ["BLOCK", "WARN", "INFO"])

    def test_unknown_severity_last(self):
        fs = [_f(severity="???", what="x"), _f(severity="INFO", what="y")]
        out = triage.order_findings(fs)
        self.assertEqual(out[0]["severity"], "INFO")


class TestRunTriage(unittest.TestCase):
    def _run(self, findings, **kw):
        args = dict(baseline=set(), queue_ids=set(),
                    skills_with_fixtures=set(), impact_resolver=_no_impact,
                    max_enqueue=5)
        args.update(kw)
        return triage.run_triage(findings, **args)

    def test_invalid_schema_goes_digest(self):
        out = self._run([{"sensor": "s"}])
        self.assertEqual(out[0]["route"], "digest")
        self.assertEqual(out[0]["reason"], "invalid-schema")
        self.assertTrue(out[0]["errors"])

    def test_budget_consumed_in_severity_order(self):
        fs = [_f(severity="WARN", what="late"), _f(severity="BLOCK", what="first")]
        out = self._run(fs, max_enqueue=1)
        by_what = {d["finding"]["what"]: d for d in out}
        self.assertEqual(by_what["first"]["route"], "enqueue")
        self.assertEqual(by_what["late"]["route"], "inbox")
        self.assertEqual(by_what["late"]["reason"], "budget")

    def test_duplicate_does_not_consume_budget(self):
        import finding_identity as fi
        dup = _f(what="dup")
        dup_fid = fi.finding_id("s", "r", "docs/x.md", "dup")
        fs = [_f(severity="BLOCK", what="dup"), _f(severity="WARN", what="fresh")]
        # BLOCK の dup が先に処理されるが duplicate なので budget を消費しない
        out = self._run(fs, queue_ids={dup_fid}, max_enqueue=1)
        by_what = {d["finding"]["what"]: d for d in out}
        self.assertEqual(by_what["dup"]["route"], "duplicate")
        self.assertEqual(by_what["fresh"]["route"], "enqueue")

    def test_fix_action_missing_normalized_to_report_only(self):
        f = _f()
        del f["fix_action"]
        out = self._run([f])
        self.assertEqual(out[0]["route"], "digest")
        self.assertEqual(out[0]["finding"]["fix_action"], "REPORT_ONLY")

    def test_decision_carries_finding_id(self):
        out = self._run([_f()])
        self.assertRegex(out[0]["finding_id"], r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
