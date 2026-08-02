"""validate_review_output の契約テスト。

受入基準 C2 / C3 / C4 / C5 とチャネル分離の機械強制がここで固定される。
"""

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_review_output as vro  # noqa: E402


VALID = {
    "assurance_role": "diagnostic_only",
    "quality_gate_evidence": False,
    "dynamic_sensors_executed": [],
    "coverage": [
        {
            "target": "skills/example/SKILL.md",
            "value": "reviewed",
            "reason": "本文と参照契約を突き合わせた",
        },
        {
            "target": "実行品質（指示追従率）",
            "value": "unsupported",
            "reason": "実走センサーを回さないため。実測で reviewed へ昇格する",
        },
    ],
    "evidence": [
        {
            "skill": "example",
            "state": "accepted_without_run",
            "reason": "台帳の result が accepted-without-run",
        }
    ],
    "control_candidates": [
        {
            "id": "cc-1",
            "verdict": "BLOCK",
            "target": "skills/example/SKILL.md:12",
            "summary": "参照している契約の語彙と本文の定義が正面から矛盾する",
            "qualification_reason": "validate_repo チェック9 が同ファイルで違反を出している",
            "fix_action": "NEEDS_JUDGMENT",
        }
    ],
    "diagnostics": [
        {
            "id": "dg-1",
            "verdict": "OPPORTUNITY",
            "target": "skills/example/SKILL.md",
            "summary": "受入条件が観測可能なので fixture 化の資産価値がある",
        }
    ],
}


def doc(**overrides):
    d = copy.deepcopy(VALID)
    d.update(overrides)
    return d


class ValidDocumentTest(unittest.TestCase):
    def test_reference_document_passes_with_no_errors(self):
        self.assertEqual(vro.validate(doc()), [])


class NonEvidenceDeclarationTest(unittest.TestCase):
    """C5: 非証拠宣言 3 フィールドの必須化と値の固定。"""

    def test_missing_assurance_role_is_rejected(self):
        d = doc()
        del d["assurance_role"]
        self.assertIn("assurance_role", " ".join(vro.validate(d)))

    def test_missing_quality_gate_evidence_is_rejected(self):
        d = doc()
        del d["quality_gate_evidence"]
        self.assertIn("quality_gate_evidence", " ".join(vro.validate(d)))

    def test_missing_dynamic_sensors_executed_is_rejected(self):
        d = doc()
        del d["dynamic_sensors_executed"]
        self.assertIn("dynamic_sensors_executed", " ".join(vro.validate(d)))

    def test_assurance_role_claiming_gate_evidence_is_rejected(self):
        self.assertTrue(vro.validate(doc(assurance_role="quality_gate")))

    def test_quality_gate_evidence_true_is_rejected(self):
        self.assertTrue(vro.validate(doc(quality_gate_evidence=True)))


class DynamicSensorTest(unittest.TestCase):
    """C3: 実走センサー不使用の機械強制。"""

    def test_non_empty_dynamic_sensors_executed_is_rejected(self):
        errors = vro.validate(doc(dynamic_sensors_executed=["skill-regression"]))
        self.assertIn("dynamic_sensors_executed", " ".join(errors))


class BlockQualificationTest(unittest.TestCase):
    """C2: qualification_reason を欠く BLOCK の拒否。"""

    def test_block_without_qualification_reason_is_rejected(self):
        d = doc()
        del d["control_candidates"][0]["qualification_reason"]
        self.assertIn("qualification_reason", " ".join(vro.validate(d)))

    def test_block_with_blank_qualification_reason_is_rejected(self):
        d = doc()
        d["control_candidates"][0]["qualification_reason"] = "   "
        self.assertIn("qualification_reason", " ".join(vro.validate(d)))

    def test_warn_without_qualification_reason_is_accepted(self):
        d = doc()
        d["control_candidates"][0]["verdict"] = "WARN"
        del d["control_candidates"][0]["qualification_reason"]
        self.assertEqual(vro.validate(d), [])


class ChannelSeparationTest(unittest.TestCase):
    """診断チャネルが制御判断に流れ込む経路をスキーマで塞ぐ。"""

    def test_block_in_diagnostics_is_rejected(self):
        d = doc()
        d["diagnostics"][0]["verdict"] = "BLOCK"
        self.assertIn("diagnostics", " ".join(vro.validate(d)))

    def test_opportunity_in_control_candidates_is_rejected(self):
        d = doc()
        d["control_candidates"][0]["verdict"] = "OPPORTUNITY"
        self.assertIn("control_candidates", " ".join(vro.validate(d)))

    def test_auto_fix_in_diagnostics_is_rejected(self):
        d = doc()
        d["diagnostics"][0]["fix_action"] = "AUTO_FIX"
        self.assertIn("AUTO_FIX", " ".join(vro.validate(d)))

    def test_duplicate_finding_id_across_channels_is_rejected(self):
        d = doc()
        d["diagnostics"][0]["id"] = d["control_candidates"][0]["id"]
        self.assertTrue(vro.validate(d))


class EvidenceClassificationTest(unittest.TestCase):
    """C4: 5 状態分類。accepted_without_run が実走証拠と区別される。"""

    def test_five_states_are_the_declared_vocabulary(self):
        self.assertEqual(
            set(vro.EVIDENCE_STATES),
            {"current_pass", "accepted_without_run", "stale", "uncovered", "invalid"},
        )

    def test_accepted_without_run_carries_no_run_evidence(self):
        classified = vro.classify_evidence({"skill": "x", "state": "accepted_without_run"})
        self.assertFalse(classified["run_evidence"])
        self.assertFalse(classified["current"])

    def test_current_pass_carries_run_evidence(self):
        classified = vro.classify_evidence({"skill": "x", "state": "current_pass"})
        self.assertTrue(classified["run_evidence"])
        self.assertTrue(classified["current"])

    def test_accepted_without_run_and_current_pass_display_differently(self):
        a = vro.classify_evidence({"skill": "x", "state": "accepted_without_run"})
        b = vro.classify_evidence({"skill": "x", "state": "current_pass"})
        self.assertNotEqual(a["label"], b["label"])

    def test_stale_run_evidence_is_not_current(self):
        classified = vro.classify_evidence({"skill": "x", "state": "stale"})
        self.assertTrue(classified["run_evidence"])
        self.assertFalse(classified["current"])

    def test_declaring_run_evidence_for_accepted_without_run_is_rejected(self):
        d = doc()
        d["evidence"][0]["run_evidence"] = True
        self.assertIn("run_evidence", " ".join(vro.validate(d)))

    def test_unknown_evidence_state_is_rejected(self):
        d = doc()
        d["evidence"][0]["state"] = "verified"
        self.assertTrue(vro.validate(d))

    def test_classify_rejects_unknown_state(self):
        with self.assertRaises(ValueError):
            vro.classify_evidence({"skill": "x", "state": "verified"})


class CoverageLedgerTest(unittest.TestCase):
    """評価範囲の申告を欠いた出力を通さない（coverage-ledger の Iron Law）。"""

    def test_missing_coverage_is_rejected(self):
        d = doc()
        del d["coverage"]
        self.assertIn("coverage", " ".join(vro.validate(d)))

    def test_empty_coverage_is_rejected(self):
        self.assertIn("coverage", " ".join(vro.validate(doc(coverage=[]))))

    def test_unsupported_without_reason_is_rejected(self):
        d = doc()
        d["coverage"][1]["reason"] = ""
        self.assertTrue(vro.validate(d))

    def test_unknown_coverage_value_is_rejected(self):
        d = doc()
        d["coverage"][0]["value"] = "checked"
        self.assertTrue(vro.validate(d))


class UnknownKeyTest(unittest.TestCase):
    """宣言したつもりの前提が黙って捨てられる事故を防ぐ。"""

    def test_unknown_top_level_key_is_rejected(self):
        self.assertTrue(vro.validate(doc(verdict="PASS")))

    def test_unknown_finding_key_is_rejected(self):
        d = doc()
        d["control_candidates"][0]["severity"] = "critical"
        self.assertTrue(vro.validate(d))

    def test_unknown_coverage_key_is_rejected(self):
        d = doc()
        d["coverage"][0]["note"] = "x"
        self.assertTrue(vro.validate(d))


class ShapeTest(unittest.TestCase):
    def test_non_mapping_document_is_rejected(self):
        self.assertTrue(vro.validate([]))

    def test_non_list_channel_is_rejected(self):
        self.assertTrue(vro.validate(doc(diagnostics={})))

    def test_non_mapping_finding_is_rejected(self):
        self.assertTrue(vro.validate(doc(diagnostics=["dg-1"])))

    def test_both_channels_empty_is_accepted(self):
        self.assertEqual(vro.validate(doc(control_candidates=[], diagnostics=[])), [])


class CliTest(unittest.TestCase):
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "validate_review_output.py")

    def run_cli(self, payload, as_text=None):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write(as_text if as_text is not None else json.dumps(payload))
            path = fh.name
        try:
            return subprocess.run([sys.executable, self.script, path],
                                  capture_output=True, text=True)
        finally:
            os.unlink(path)

    def test_valid_document_exits_zero(self):
        self.assertEqual(self.run_cli(VALID).returncode, 0)

    def test_contract_violation_exits_one(self):
        d = doc()
        del d["control_candidates"][0]["qualification_reason"]
        result = self.run_cli(d)
        self.assertEqual(result.returncode, 1)
        self.assertIn("qualification_reason", result.stdout + result.stderr)

    def test_unparsable_input_exits_two(self):
        self.assertEqual(self.run_cli(None, as_text="{not json").returncode, 2)

    def test_missing_file_exits_two(self):
        result = subprocess.run([sys.executable, self.script, "/nonexistent/x.json"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_non_utf8_input_exits_two(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as fh:
            fh.write(b'\xff\xfe{"a":1}')
            path = fh.name
        try:
            result = subprocess.run([sys.executable, self.script, path],
                                    capture_output=True, text=True)
        finally:
            os.unlink(path)
        self.assertEqual(result.returncode, 2)

    def test_reads_stdin_with_dash(self):
        result = subprocess.run([sys.executable, self.script, "-"],
                                input=json.dumps(VALID),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
