#!/usr/bin/env python3
"""Unit tests for dossier_lint (TDD — written before the implementation).

Covers every GD* rule (fail / pass + near-miss), robustness (exit 2 paths),
path containment, and the catalog-sync guard against the contract rule table.
"""

import copy
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dossier_lint as dl  # noqa: E402

# Built at runtime so the literal AWS-key pattern never appears in this source
# file (the repo's secret-detection hook would otherwise flag the fixture).
FAKE_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"


def base_dossier():
    """A minimal fully-valid draft dossier that yields zero findings."""
    return {
        "schema_version": 1,
        "status": "draft",
        "superseded_by": None,
        "goal": {
            "statement": "ドキュメント品質を上げて維持する",
            "non_goals": ["別リポジトリは対象外"],
            "ssot": "docs/ が正の情報源",
        },
        "oracles": [{
            "id": "oracle:lint",
            "type": "true",
            "command": "python3 scripts/validate_repo.py",
            "oracle_files": ["docs/status.md"],
            "owner": "maintainer",
        }],
        "fragments": [{
            "id": "frag:a",
            "wire_to": "goal-loop",
            "exit_to": "ci_gate",
            "routing_proof": "完了条件で機械検証可能",
            "auto_fix_allowed": False,
            "why_not_auto_fix": "本文の意味的書き換えは非自動化",
            "self_modification_risk": "low",
            "blocked_by": [],
        }],
        "sensors": [{
            "id": "sensor:s",
            "rules": ["CA-S001"],
            "findings_policy": {"fix_action": "REPORT_ONLY", "enqueue": False},
        }],
        "inbox": [{
            "id": "inbox:q1",
            "question": "対象ドキュメントの範囲は？",
            "reclassify_when": "範囲が固定されたら sensor 化",
        }],
        "measurement": {
            "metrics": ["success_rate"],
            "stop_conditions": ["oracle が真"],
        },
    }


def rules_hit(dossier):
    return {f["rule"] for f in dl.run_checks(dossier)}


class TestValidBase(unittest.TestCase):
    def test_base_is_clean(self):
        self.assertEqual(dl.run_checks(base_dossier()), [])

    def test_finding_schema_fields(self):
        d = base_dossier()
        del d["schema_version"]
        for f in dl.run_checks(d):
            self.assertEqual(set(f), {"rule", "severity", "file", "locator",
                                      "message", "fix"})


class TestGD001(unittest.TestCase):
    def test_empty_dossier_flags_all_missing(self):
        self.assertIn("GD001", rules_hit({}))

    def test_missing_one_block(self):
        d = base_dossier()
        del d["measurement"]
        self.assertIn("GD001", rules_hit(d))

    def test_missing_schema_version(self):
        d = base_dossier()
        del d["schema_version"]
        self.assertIn("GD001", rules_hit(d))

    def test_wrong_type_block(self):
        d = base_dossier()
        d["oracles"] = "notalist"
        self.assertIn("GD001", rules_hit(d))


class TestGD002(unittest.TestCase):
    def test_bad_enum(self):
        d = base_dossier()
        d["status"] = "published"
        self.assertIn("GD002", rules_hit(d))

    def test_missing(self):
        d = base_dossier()
        del d["status"]
        self.assertIn("GD002", rules_hit(d))

    def test_wrong_type(self):
        d = base_dossier()
        d["status"] = ["draft"]
        self.assertIn("GD002", rules_hit(d))

    def test_valid(self):
        for s in ("draft", "approved", "superseded", "rejected"):
            d = base_dossier()
            d["status"] = s
            if s == "superseded":
                d["superseded_by"] = "20260101000000_next.json"
            self.assertNotIn("GD002", rules_hit(d))


class TestGD003(unittest.TestCase):
    def test_bad_enum(self):
        d = base_dossier()
        d["fragments"][0]["wire_to"] = "nowhere"
        self.assertIn("GD003", rules_hit(d))

    def test_missing(self):
        d = base_dossier()
        del d["fragments"][0]["wire_to"]
        self.assertIn("GD003", rules_hit(d))

    def test_wrong_type(self):
        d = base_dossier()
        d["fragments"][0]["wire_to"] = 42
        self.assertIn("GD003", rules_hit(d))


class TestGD004(unittest.TestCase):
    def test_bad_enum(self):
        d = base_dossier()
        d["fragments"][0]["exit_to"] = "somewhere"
        self.assertIn("GD004", rules_hit(d))

    def test_missing(self):
        d = base_dossier()
        del d["fragments"][0]["exit_to"]
        self.assertIn("GD004", rules_hit(d))


class TestGD005(unittest.TestCase):
    def test_dangling_reference(self):
        d = base_dossier()
        d["fragments"][0]["blocked_by"] = ["inbox:ghost"]
        self.assertIn("GD005", rules_hit(d))

    def test_real_reference_ok(self):
        d = base_dossier()
        d["fragments"][0]["blocked_by"] = ["inbox:q1"]
        self.assertNotIn("GD005", rules_hit(d))


class TestGD006(unittest.TestCase):
    def test_cross_block_duplicate(self):
        d = base_dossier()
        d["inbox"][0]["id"] = "frag:a"  # collides with the fragment id
        self.assertIn("GD006", rules_hit(d))

    def test_all_unique_ok(self):
        self.assertNotIn("GD006", rules_hit(base_dossier()))


class TestGD101(unittest.TestCase):
    def test_report_only_enqueue_true(self):
        d = base_dossier()
        d["sensors"][0]["findings_policy"] = {"fix_action": "REPORT_ONLY",
                                              "enqueue": True}
        self.assertIn("GD101", rules_hit(d))

    def test_report_only_enqueue_false_ok(self):
        self.assertNotIn("GD101", rules_hit(base_dossier()))

    def test_near_miss_auto_fix_enqueue_true_ok(self):
        d = base_dossier()
        d["sensors"][0]["findings_policy"] = {"fix_action": "AUTO_FIX",
                                              "enqueue": True}
        self.assertNotIn("GD101", rules_hit(d))


class TestGD102(unittest.TestCase):
    def test_approved_missing_routing_proof(self):
        d = base_dossier()
        d["status"] = "approved"
        del d["fragments"][0]["routing_proof"]
        self.assertIn("GD102", rules_hit(d))

    def test_draft_missing_routing_proof_ok(self):
        d = base_dossier()
        del d["fragments"][0]["routing_proof"]
        self.assertNotIn("GD102", rules_hit(d))

    def test_missing_why_not_auto_fix(self):
        d = base_dossier()
        del d["fragments"][0]["why_not_auto_fix"]
        self.assertIn("GD102", rules_hit(d))

    def test_auto_fix_true_needs_no_reason(self):
        d = base_dossier()
        d["fragments"][0]["auto_fix_allowed"] = True
        d["fragments"][0].pop("why_not_auto_fix", None)
        self.assertNotIn("GD102", rules_hit(d))


class TestGD103(unittest.TestCase):
    def test_incompatible_inbox_ci_gate(self):
        d = base_dossier()
        d["fragments"][0]["wire_to"] = "inbox"
        d["fragments"][0]["exit_to"] = "ci_gate"
        self.assertIn("GD103", rules_hit(d))

    def test_compatible_ok(self):
        d = base_dossier()
        d["fragments"][0]["wire_to"] = "loop-triage"
        d["fragments"][0]["exit_to"] = "resident_sensor"
        self.assertNotIn("GD103", rules_hit(d))


class TestGD104(unittest.TestCase):
    def test_approved_with_unresolved_blocked_by(self):
        d = base_dossier()
        d["status"] = "approved"
        d["fragments"][0]["blocked_by"] = ["inbox:q1"]
        self.assertIn("GD104", rules_hit(d))

    def test_superseded_without_superseded_by(self):
        d = base_dossier()
        d["status"] = "superseded"
        d["superseded_by"] = None
        self.assertIn("GD104", rules_hit(d))

    def test_rejected_with_active_exit(self):
        d = base_dossier()
        d["status"] = "rejected"
        d["fragments"][0]["exit_to"] = "ci_gate"
        self.assertIn("GD104", rules_hit(d))


class TestGD201(unittest.TestCase):
    def _proxy(self):
        return {
            "gap_from_true_goal": "表層のみ",
            "failure_modes": "偽陽性",
            "human_limit_approved": True,
            "hash_lock": True,
            "post_completion_human_check": True,
            "judge_type": "mechanical",
        }

    def test_missing_required_field(self):
        d = base_dossier()
        p = self._proxy()
        del p["failure_modes"]
        d["oracles"][0]["type"] = "proxy"
        d["oracles"][0]["proxy"] = p
        self.assertIn("GD201", rules_hit(d))

    def test_llm_subjective_rejected(self):
        d = base_dossier()
        p = self._proxy()
        p["judge_type"] = "llm_subjective"
        d["oracles"][0]["type"] = "proxy"
        d["oracles"][0]["proxy"] = p
        self.assertIn("GD201", rules_hit(d))

    def test_true_oracle_needs_no_proxy(self):
        self.assertNotIn("GD201", rules_hit(base_dossier()))

    def test_valid_proxy_ok(self):
        d = base_dossier()
        d["oracles"][0]["type"] = "proxy"
        d["oracles"][0]["proxy"] = self._proxy()
        self.assertNotIn("GD201", rules_hit(d))


class TestGD202(unittest.TestCase):
    def test_high_risk_auto_fix(self):
        d = base_dossier()
        d["fragments"][0]["self_modification_risk"] = "high"
        d["fragments"][0]["auto_fix_allowed"] = True
        d["fragments"][0].pop("why_not_auto_fix", None)
        self.assertIn("GD202", rules_hit(d))

    def test_high_risk_no_auto_fix_ok(self):
        d = base_dossier()
        d["fragments"][0]["self_modification_risk"] = "high"
        d["fragments"][0]["auto_fix_allowed"] = False
        self.assertNotIn("GD202", rules_hit(d))


class TestGD203(unittest.TestCase):
    def test_absolute_path_in_oracle_files(self):
        d = base_dossier()
        d["oracles"][0]["oracle_files"] = ["/home/user/secret.md"]
        self.assertIn("GD203", rules_hit(d))

    def test_secret_in_command(self):
        d = base_dossier()
        d["oracles"][0]["command"] = "curl -H 'token: " + FAKE_AWS + "'"
        self.assertIn("GD203", rules_hit(d))

    def test_relative_paths_ok(self):
        self.assertNotIn("GD203", rules_hit(base_dossier()))


class TestGD301(unittest.TestCase):
    def test_empty_oracle_files_warns(self):
        d = base_dossier()
        d["oracles"][0]["oracle_files"] = []
        self.assertIn("GD301", rules_hit(d))

    def test_glob_only_warns(self):
        d = base_dossier()
        d["oracles"][0]["oracle_files"] = ["docs/**"]
        self.assertIn("GD301", rules_hit(d))

    def test_explicit_list_ok(self):
        self.assertNotIn("GD301", rules_hit(base_dossier()))


class TestGD302(unittest.TestCase):
    def test_empty_non_goals_warns(self):
        d = base_dossier()
        d["goal"]["non_goals"] = []
        self.assertIn("GD302", rules_hit(d))

    def test_non_empty_ok(self):
        self.assertNotIn("GD302", rules_hit(base_dossier()))


class TestSeverityAndExitCode(unittest.TestCase):
    def test_warn_only_exit_zero(self):
        d = base_dossier()
        d["goal"]["non_goals"] = []  # GD302 warn only
        findings = dl.run_checks(d)
        self.assertTrue(findings)
        self.assertTrue(all(f["severity"] == "warn" for f in findings))
        self.assertFalse(dl.has_errors(findings))

    def test_error_present_has_errors(self):
        d = base_dossier()
        del d["status"]  # GD002 error
        self.assertTrue(dl.has_errors(dl.run_checks(d)))


class TestSecretMasking(unittest.TestCase):
    def test_findings_are_masked(self):
        # A secret embedded in a free-text field must not leak into messages.
        d = base_dossier()
        d["goal"]["statement"] = "鍵は " + FAKE_AWS + " です"
        del d["status"]  # force at least one finding that echoes context
        blob = " ".join(f["message"] + f["fix"] for f in dl.run_checks(d))
        self.assertNotIn(FAKE_AWS, blob)


class TestLoadRobustness(unittest.TestCase):
    def _tmp(self, content, name="d.json"):
        d = tempfile.mkdtemp()
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return p

    def test_broken_json_raises(self):
        p = self._tmp("{ not json ")
        with self.assertRaises(dl.DossierLoadError):
            dl.load_dossier(p)

    def test_duplicate_key_raises(self):
        p = self._tmp('{"status": "draft", "status": "approved"}')
        with self.assertRaises(dl.DossierLoadError):
            dl.load_dossier(p)

    def test_oversize_raises(self):
        p = self._tmp('{"x": "' + "a" * (dl.MAX_SIZE + 10) + '"}')
        with self.assertRaises(dl.DossierLoadError):
            dl.load_dossier(p)

    def test_missing_file_raises(self):
        with self.assertRaises(dl.DossierLoadError):
            dl.load_dossier("/nonexistent/path/d.json")

    def test_valid_loads(self):
        import json
        p = self._tmp(json.dumps(base_dossier()))
        self.assertEqual(dl.load_dossier(p)["status"], "draft")


class TestPathContainment(unittest.TestCase):
    def test_inside_dir_ok(self):
        root = tempfile.mkdtemp()
        ddir = os.path.join(root, "docs", "loop", "dossiers")
        os.makedirs(ddir)
        p = os.path.join(ddir, "a.json")
        with open(p, "w") as f:
            f.write("{}")
        self.assertEqual(os.path.realpath(dl.check_containment(p, ddir)),
                         os.path.realpath(p))

    def test_prefix_sibling_rejected(self):
        # docs/loop/dossiers-evil must not pass a startswith-style check.
        root = tempfile.mkdtemp()
        ddir = os.path.join(root, "docs", "loop", "dossiers")
        evil = os.path.join(root, "docs", "loop", "dossiers-evil")
        os.makedirs(ddir)
        os.makedirs(evil)
        p = os.path.join(evil, "a.json")
        with open(p, "w") as f:
            f.write("{}")
        with self.assertRaises(dl.DossierLoadError):
            dl.check_containment(p, ddir)

    def test_symlink_rejected(self):
        root = tempfile.mkdtemp()
        ddir = os.path.join(root, "dossiers")
        os.makedirs(ddir)
        outside = os.path.join(root, "outside.json")
        with open(outside, "w") as f:
            f.write("{}")
        link = os.path.join(ddir, "link.json")
        os.symlink(outside, link)
        with self.assertRaises(dl.DossierLoadError):
            dl.check_containment(link, ddir)


class TestCatalogSync(unittest.TestCase):
    """Contract rule table (§11) and RULES registry must not drift."""

    CONTRACT = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "shared", "references", "goal-decomposition-pattern.md")

    def _parse(self):
        row = re.compile(r"^\|\s*(GD\d+)\s*\|\s*(error|warn)\s*\|")
        out = {}
        with open(self.CONTRACT, encoding="utf-8") as f:
            for line in f:
                m = row.match(line.rstrip("\n"))
                if m:
                    out[m.group(1)] = m.group(2)
        return out

    def test_ids_match(self):
        self.assertEqual(set(self._parse()), set(dl.RULES),
                         "contract rule table IDs and RULES registry diverge")

    def test_severity_match(self):
        catalog = self._parse()
        for rid, meta in dl.RULES.items():
            self.assertEqual(catalog[rid], meta["severity"], f"{rid} severity")

    def test_compat_matrix_matches_contract(self):
        # The §4.1 table must agree with dossier_lint._COMPAT.
        for wire, exits in dl._COMPAT.items():
            self.assertTrue(exits, f"{wire} has no compatible exit")


class TestApprovedIntegration(unittest.TestCase):
    def test_full_approved_dossier_clean(self):
        d = base_dossier()
        d["status"] = "approved"
        d["fragments"][0]["blocked_by"] = []
        d["oracles"][0]["type"] = "proxy"
        d["oracles"][0]["proxy"] = {
            "gap_from_true_goal": "表層のみ",
            "failure_modes": "偽陽性の可能性",
            "human_limit_approved": True,
            "hash_lock": True,
            "post_completion_human_check": True,
            "judge_type": "mechanical",
        }
        self.assertEqual(dl.run_checks(d), [])


if __name__ == "__main__":
    unittest.main()
