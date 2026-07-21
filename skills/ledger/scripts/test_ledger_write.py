#!/usr/bin/env python3
"""Unit tests for ledger_write (TDD — written before the implementation).

ledger_write is the write-side companion to ledger_lint: it records
human-confirmed adjudications (add-row / approve / reject / batch-approve)
with machine-computed digests, and self-verifies every write with a
verify-before-swap gate (lint the in-memory result; os.replace() only when
clean) so a generated ledger always lints clean and a rejected write never
touches the file.

Covered contracts:
  - add-row initializes an UNDECIDED row whose ledger lints clean (argument
    names match the schema field names)
  - approve computes the digest ledger_lint recomputes, yields an AGREED row
  - reject yields a REJECTED row carrying no approval attachment
  - batch-approve emits a batch_digest-consistent manifest; a high-risk row
    aborts the batch before any write
  - verify-before-swap: a finding-producing input leaves the file untouched
    (a new file is not created; an existing file stays byte-identical)
  - exit-code contract 0 (success) / 1 (validation / business rule) /
    2 (usage / input corruption)
  - write-target containment (symlink / outside-root rejected)
  - secret pre-flight on new free text
  - approval is structurally coupled to a session artifact recording the
    human's answer (no standalone approval from a bare id); actor_kind is
    never a free argument
  - diff invariant: existing UNDECIDED rows survive every operation
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ledger_lint as ll  # noqa: E402
import ledger_write as lw  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
LEDGER_WRITE = os.path.join(SCRIPTS_DIR, "ledger_write.py")

# Built at runtime so no literal credential appears in this source file
# (the repo's secret-detection hook would otherwise flag it).
FAKE_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"


def make_row(**over):
    row = {
        "id": over.pop("id", "NAV-001"),
        "revision": over.pop("revision", 1),
        "state": over.pop("state", "UNDECIDED"),
        "claim": over.pop("claim", "トップナビはグローバル固定で全画面共通とする"),
    }
    row.update(over)
    return row


def make_file(rows, **top):
    data = {"schema_version": 1, "rows": rows}
    data.update(top)
    return data


def make_session(responses, session_id="S-20260722-01", **over):
    s = {"schema_version": 1, "session_id": session_id, "responses": responses}
    s.update(over)
    return s


def resp(row_id, answer="OK", revision=1, **over):
    r = {"row_id": row_id, "revision": revision, "answer": answer}
    r.update(over)
    return r


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


class WriteTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.ledger = os.path.join(self.root, "ledger.json")

    def tearDown(self):
        self._tmp.cleanup()

    def write_ledger(self, data, name="ledger.json"):
        return write_json(os.path.join(self.root, name), data)

    def write_session(self, session, name="session.json"):
        return write_json(os.path.join(self.root, name), session)

    def run_cli(self, subcmd, *args, ledger=None):
        return subprocess.run(
            [sys.executable, LEDGER_WRITE, subcmd, "--root", self.root,
             "--ledger", ledger or self.ledger, *args],
            capture_output=True, text=True)

    def load_ledger(self, name="ledger.json"):
        with open(os.path.join(self.root, name), encoding="utf-8") as f:
            return json.load(f)

    def read_raw(self, name="ledger.json"):
        with open(os.path.join(self.root, name), encoding="utf-8") as f:
            return f.read()

    def lint_findings(self, name="ledger.json"):
        return ll.lint_paths([os.path.join(self.root, name)])


class AddRowTests(WriteTestBase):
    def test_add_row_success_creates_undecided_row_lints_clean(self):
        r = self.run_cli("add-row", "--id", "NAV-001",
                         "--claim", "トップナビは全画面共通")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load_ledger()
        self.assertEqual(data["rows"][0]["state"], "UNDECIDED")
        self.assertEqual(data["rows"][0]["revision"], 1)
        self.assertEqual(self.lint_findings()["findings"], [])

    def test_add_row_argument_names_match_schema_fields(self):
        r = self.run_cli("add-row", "--id", "NAV-001", "--claim", "主張",
                         "--term-refs", "T-1", "T-2",
                         "--observations", "既存画面がある",
                         "--assumptions", "SSO を使うと仮定")
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.load_ledger()["rows"][0]
        self.assertEqual(row["term_refs"], ["T-1", "T-2"])
        self.assertEqual(row["observations"], ["既存画面がある"])
        self.assertEqual(row["assumptions"], ["SSO を使うと仮定"])
        self.assertEqual(self.lint_findings()["findings"], [])

    def test_add_row_appends_to_existing_ledger(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        r = self.run_cli("add-row", "--id", "NAV-002", "--claim", "フッタは非表示")
        self.assertEqual(r.returncode, 0, r.stderr)
        ids = [row["id"] for row in self.load_ledger()["rows"]]
        self.assertEqual(ids, ["NAV-001", "NAV-002"])

    def test_add_row_duplicate_id_rejected_file_unchanged(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        before = self.read_raw()
        r = self.run_cli("add-row", "--id", "NAV-001", "--claim", "別の主張")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.read_raw(), before)


class ApproveTests(WriteTestBase):
    def test_approve_produces_lint_clean_agreed_row(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.load_ledger()["rows"][0]
        self.assertEqual(row["state"], "AGREED")
        self.assertEqual(row["approval"]["actor_kind"], "human")
        self.assertEqual(self.lint_findings()["findings"], [])

    def test_approve_digest_matches_lint_recomputation(self):
        self.write_ledger(make_file([
            make_row(id="NAV-001", term_refs=["T-1", "T-2"])]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.load_ledger()["rows"][0]
        self.assertEqual(row["approval"]["digest"], ll.compute_digest(row))

    def test_approve_revision_mismatch_rejected(self):
        self.write_ledger(make_file([make_row(id="NAV-001", revision=2)]))
        sess = self.write_session(make_session([resp("NAV-001", revision=1)]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.load_ledger()["rows"][0]["state"], "UNDECIDED")

    def test_approve_nonexistent_row_rejected(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-777")]))
        r = self.run_cli("approve", "--row-id", "NAV-777", "--session", sess)
        self.assertEqual(r.returncode, 1)

    def test_approve_on_rejected_row_rejected(self):
        self.write_ledger(make_file([make_row(id="NAV-001", state="REJECTED")]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 1)

    def test_approve_on_agreed_row_rejected(self):
        self.write_ledger(make_file([make_row(id="NAV-001", state="AGREED")]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 1)

    def test_approve_provisional_row_drops_stale_attachment(self):
        # PROVISIONAL is an allowed prior state; its reeval_condition must not
        # linger on the resulting AGREED row (else lint would reject the write).
        self.write_ledger(make_file([make_row(
            id="NAV-001", state="PROVISIONAL",
            reeval_condition="pilot 実測後に再評価")]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.load_ledger()["rows"][0]
        self.assertEqual(row["state"], "AGREED")
        self.assertNotIn("reeval_condition", row)
        self.assertEqual(self.lint_findings()["findings"], [])

    def test_approve_json_output_reports_written_approval(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess,
                         "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["row_id"], "NAV-001")
        self.assertEqual(payload["revision"], 1)
        self.assertIn("digest", payload)


class SessionCouplingTests(WriteTestBase):
    """approve/reject must consume a session artifact that records the human's
    answer — a bare id with no recorded response cannot approve anything."""

    def test_approve_without_matching_session_response_rejected(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-999")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.load_ledger()["rows"][0]["state"], "UNDECIDED")

    def test_approve_requires_ok_answer(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-001", answer="保留")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.load_ledger()["rows"][0]["state"], "UNDECIDED")

    def test_actor_kind_is_not_a_free_argument(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess,
                         "--actor-kind", "llm")
        self.assertEqual(r.returncode, 2)


class RejectTests(WriteTestBase):
    def test_reject_produces_lint_clean_rejected_row(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-001", answer="違う")]))
        r = self.run_cli("reject", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.load_ledger()["rows"][0]
        self.assertEqual(row["state"], "REJECTED")
        self.assertNotIn("approval", row)
        self.assertEqual(self.lint_findings()["findings"], [])

    def test_reject_requires_chigau_answer(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session([resp("NAV-001", answer="OK")]))
        r = self.run_cli("reject", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.load_ledger()["rows"][0]["state"], "UNDECIDED")

    def test_reject_records_reason_in_observations(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        sess = self.write_session(make_session(
            [resp("NAV-001", answer="違う", reason="要件と矛盾する")]))
        r = self.run_cli("reject", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.load_ledger()["rows"][0]
        self.assertIn("要件と矛盾する", row.get("observations", []))
        self.assertEqual(self.lint_findings()["findings"], [])


class BatchApproveTests(WriteTestBase):
    def test_batch_approve_manifest_is_digest_consistent_and_lints_clean(self):
        self.write_ledger(make_file([
            make_row(id="NAV-001"), make_row(id="NAV-002", claim="フッタは非表示")]))
        sess = self.write_session(make_session(
            [resp("NAV-001"), resp("NAV-002")], batch_summary="2 件の合意要約"))
        r = self.run_cli("batch-approve", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load_ledger()
        self.assertEqual(len(data["batch_manifests"]), 1)
        m = data["batch_manifests"][0]
        self.assertEqual(
            m["batch_digest"],
            ll.compute_batch_digest(m["row_digests"], m["summary_digest"]))
        self.assertTrue(all(row["state"] == "AGREED" for row in data["rows"]))
        self.assertEqual(self.lint_findings()["findings"], [])

    def test_batch_approve_high_risk_row_aborts_before_write(self):
        self.write_ledger(make_file([
            make_row(id="RISK-001", risk="high"), make_row(id="NAV-002")]))
        before = self.read_raw()
        sess = self.write_session(make_session(
            [resp("RISK-001"), resp("NAV-002")], batch_summary="要約"))
        r = self.run_cli("batch-approve", "--session", sess)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.read_raw(), before)

    def test_batch_approve_high_risk_detection_uses_lint_risk_levels(self):
        self.assertIn(lw.HIGH_RISK, ll.RISK_LEVELS)


class VerifyBeforeSwapTests(WriteTestBase):
    """A finding-producing input must never reach disk: the new-file case
    leaves nothing behind, the existing-file case stays byte-identical."""

    def test_finding_input_does_not_create_new_file(self):
        r = self.run_cli("add-row", "--id", "nav_1", "--claim", "x")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.ledger))

    def test_finding_input_leaves_existing_file_byte_identical(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        before = self.read_raw()
        r = self.run_cli("add-row", "--id", "bad_id", "--claim", "x")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.read_raw(), before)

    def test_dry_run_does_not_write(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        before = self.read_raw()
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess,
                         "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read_raw(), before)


class ExitCodeTests(WriteTestBase):
    def test_success_is_exit_0(self):
        r = self.run_cli("add-row", "--id", "NAV-001", "--claim", "主張")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_business_rule_rejection_is_exit_1(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        r = self.run_cli("add-row", "--id", "NAV-001", "--claim", "重複")
        self.assertEqual(r.returncode, 1)

    def test_corrupt_ledger_is_exit_2(self):
        with open(self.ledger, "w", encoding="utf-8") as f:
            f.write("{not json")
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 2)

    def test_corrupt_session_is_exit_2(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        bad = os.path.join(self.root, "bad_session.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{not json")
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", bad)
        self.assertEqual(r.returncode, 2)

    def test_root_not_a_dir_is_exit_2(self):
        r = subprocess.run(
            [sys.executable, LEDGER_WRITE, "add-row", "--root", "/no/such/dir",
             "--ledger", "/no/such/dir/l.json", "--id", "NAV-001",
             "--claim", "x"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class ContainmentTests(WriteTestBase):
    def test_symlink_ledger_rejected(self):
        real = self.write_ledger(make_file([make_row()]), name="real.json")
        link = os.path.join(self.root, "link.json")
        os.symlink(real, link)
        r = self.run_cli("add-row", "--id", "NAV-009", "--claim", "x",
                         ledger=link)
        self.assertEqual(r.returncode, 2)

    def test_outside_root_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            target = os.path.join(other, "ledger.json")
            r = self.run_cli("add-row", "--id", "NAV-001", "--claim", "x",
                             ledger=target)
            self.assertEqual(r.returncode, 2)
            self.assertFalse(os.path.exists(target))


class SecretTests(WriteTestBase):
    def test_secret_in_claim_rejected_before_write(self):
        r = self.run_cli("add-row", "--id", "NAV-001",
                         "--claim", f"接続キーは {FAKE_AWS} を使う")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.ledger))

    def test_secret_in_observations_rejected_before_write(self):
        self.write_ledger(make_file([make_row(id="NAV-001")]))
        before = self.read_raw()
        r = self.run_cli("add-row", "--id", "NAV-002", "--claim", "主張",
                         "--observations", f"token {FAKE_AWS} を観測")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.read_raw(), before)


class DiffInvariantTests(WriteTestBase):
    def test_add_row_preserves_existing_rows(self):
        self.write_ledger(make_file([
            make_row(id="NAV-001"), make_row(id="NAV-002", claim="別の主張")]))
        r = self.run_cli("add-row", "--id", "NAV-003", "--claim", "新規主張")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {row["id"]: row for row in self.load_ledger()["rows"]}
        self.assertEqual(rows["NAV-001"]["state"], "UNDECIDED")
        self.assertEqual(rows["NAV-002"]["claim"], "別の主張")

    def test_approve_preserves_other_undecided_rows(self):
        self.write_ledger(make_file([
            make_row(id="NAV-001"), make_row(id="NAV-002", claim="別の主張")]))
        sess = self.write_session(make_session([resp("NAV-001")]))
        r = self.run_cli("approve", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {row["id"]: row for row in self.load_ledger()["rows"]}
        self.assertEqual(rows["NAV-001"]["state"], "AGREED")
        self.assertEqual(rows["NAV-002"]["state"], "UNDECIDED")
        self.assertEqual(rows["NAV-002"]["claim"], "別の主張")

    def test_reject_preserves_other_undecided_rows(self):
        self.write_ledger(make_file([
            make_row(id="NAV-001"), make_row(id="NAV-002", claim="別の主張")]))
        sess = self.write_session(make_session([resp("NAV-001", answer="違う")]))
        r = self.run_cli("reject", "--row-id", "NAV-001", "--session", sess)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {row["id"]: row for row in self.load_ledger()["rows"]}
        self.assertEqual(rows["NAV-001"]["state"], "REJECTED")
        self.assertEqual(rows["NAV-002"]["state"], "UNDECIDED")


if __name__ == "__main__":
    unittest.main()
