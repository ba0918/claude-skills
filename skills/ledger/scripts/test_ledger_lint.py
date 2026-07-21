#!/usr/bin/env python3
"""Unit tests for ledger_lint (TDD — written before the implementation).

Covers: hand-rolled row validation (envelope / state-attachments / approval
authenticity), fail-closed parsing (exit-2 corruption paths), path
containment, the where/what/why/how finding contract, CLI exit-code contract,
the diff invariant (UNDECIDED must not vanish silently), term_refs membership
against a CONTEXT vocabulary file, and the agreement-ledger.md <-> code
constants sync.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ledger_lint as ll  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
LEDGER_LINT = os.path.join(SCRIPTS_DIR, "ledger_lint.py")
LEDGER_MD = os.path.join(
    SCRIPTS_DIR, "..", "..", "shared", "references", "agreement-ledger.md")

# Built at runtime so no literal credential ever appears in this source file
# (the repo's secret-detection hook would otherwise flag it).
FAKE_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"


def digest_of(claim, term_refs=None):
    core = {"claim": claim, "term_refs": sorted(term_refs or [])}
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def make_approval(claim, term_refs=None, revision=1, **over):
    ev = {
        "row_id": "NAV-001",
        "revision": revision,
        "digest": digest_of(claim, term_refs),
        "session_id": "S-20260721-01",
        "actor_kind": "human",
        "prior_state": "UNDECIDED",
    }
    ev.update(over)
    return ev


def make_row(**over):
    claim = over.get("claim", "トップナビはグローバル固定で全画面共通とする")
    term_refs = over.get("term_refs")
    row = {
        "id": "NAV-001",
        "revision": 1,
        "state": "UNDECIDED",
        "claim": claim,
    }
    row.update(over)
    return row


def make_agreed_row(**over):
    rid = over.pop("id", "NAV-001")
    rev = over.pop("revision", 1)
    claim = over.pop("claim", "トップナビはグローバル固定で全画面共通とする")
    term_refs = over.pop("term_refs", None)
    row = {
        "id": rid,
        "revision": rev,
        "state": "AGREED",
        "claim": claim,
        "approval": make_approval(claim, term_refs, revision=rev, row_id=rid),
    }
    if term_refs is not None:
        row["term_refs"] = term_refs
    row.update(over)
    return row


def make_file(rows, **top):
    data = {"schema_version": 1, "rows": rows}
    data.update(top)
    return data


def lint_obj(data, name="ledger.json", **kw):
    return ll.lint_data([(name, data)], **kw)


def checks(result):
    return sorted(f["check"] for f in result["findings"])


def advisory_checks(result):
    return sorted(a["check"] for a in result["advisories"])


def batch_digest_of(row_digests, summary_digest):
    core = {"row_digests": sorted(row_digests), "summary_digest": summary_digest}
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def make_batch_manifest(row_digests, summary_digest="SUM-DIGEST-01", **over):
    manifest = {
        "batch_digest": batch_digest_of(row_digests, summary_digest),
        "row_digests": list(row_digests),
        "summary_digest": summary_digest,
    }
    manifest.update(over)
    return manifest


class DigestTests(unittest.TestCase):
    def test_compute_digest_matches_documented_algorithm(self):
        row = make_row(claim="X", term_refs=["T-2", "T-1"])
        self.assertEqual(ll.compute_digest(row), digest_of("X", ["T-2", "T-1"]))

    def test_digest_ignores_term_ref_order(self):
        a = ll.compute_digest(make_row(claim="X", term_refs=["T-1", "T-2"]))
        b = ll.compute_digest(make_row(claim="X", term_refs=["T-2", "T-1"]))
        self.assertEqual(a, b)


class DigestRobustnessTests(unittest.TestCase):
    """compute_digest must be total: malformed rows get type findings, never
    an uncaught TypeError that crashes the linter (fail-closed break)."""

    def test_digest_total_on_non_list_term_refs(self):
        self.assertIsInstance(
            ll.compute_digest({"claim": "x", "term_refs": 5}), str)

    def test_digest_total_on_non_string_claim(self):
        self.assertIsInstance(
            ll.compute_digest({"claim": 5, "term_refs": ["a"]}), str)

    def test_digest_total_on_bool_term_refs(self):
        self.assertIsInstance(
            ll.compute_digest({"claim": "x", "term_refs": True}), str)

    def test_agreed_row_with_malformed_term_refs_does_not_crash(self):
        row = {
            "id": "NAV-001", "revision": 1, "state": "AGREED",
            "claim": "x", "term_refs": 5,
            "approval": {
                "row_id": "NAV-001", "revision": 1, "digest": "z",
                "session_id": "S-1", "actor_kind": "human",
                "prior_state": "UNDECIDED"},
        }
        result = lint_obj(make_file([row]))  # must not raise
        self.assertIn("invalid-type", checks(result))


class ValidLedgerTests(unittest.TestCase):
    def test_valid_ledger_no_findings(self):
        result = lint_obj(make_file([
            make_row(),
            make_agreed_row(id="NAV-002", claim="フッタは表示しない"),
        ]))
        self.assertEqual(result["findings"], [])
        self.assertFalse(result["corrupt"])
        self.assertFalse(result["findings_present"])

    def test_empty_ledger_is_clean(self):
        result = lint_obj(make_file([]))
        self.assertEqual(result["findings"], [])
        self.assertFalse(result["corrupt"])

    def test_unicode_claim_and_id_ok(self):
        result = lint_obj(make_file([
            make_row(claim="全角スペース　を含む多バイト主張 🎌"),
        ]))
        self.assertEqual(result["findings"], [])

    def test_finding_contract_has_all_keys(self):
        result = lint_obj(make_file([make_row(state="BOGUS")]))
        self.assertTrue(result["findings"])
        for f in result["findings"]:
            self.assertEqual(set(f), {"where", "check", "what", "why", "how"})


class EnvelopeTests(unittest.TestCase):
    def test_missing_id_and_revision_detected(self):
        row = make_row()
        del row["id"]
        del row["revision"]
        self.assertIn("missing-required", checks(lint_obj(make_file([row]))))

    def test_invalid_id_pattern_detected(self):
        self.assertIn("invalid-id", checks(lint_obj(make_file([
            make_row(id="nav_1")]))))

    def test_duplicate_id_detected(self):
        result = lint_obj(make_file([make_row(), make_row()]))
        self.assertIn("duplicate-id", checks(result))

    def test_nonpositive_revision_detected(self):
        self.assertIn("invalid-revision", checks(lint_obj(make_file([
            make_row(revision=0)]))))
        self.assertIn("invalid-revision", checks(lint_obj(make_file([
            make_row(revision=True)]))))

    def test_unknown_state_detected(self):
        self.assertIn("unknown-state", checks(lint_obj(make_file([
            make_row(state="MAYBE")]))))

    def test_unknown_envelope_key_detected(self):
        self.assertIn("unknown-key", checks(lint_obj(make_file([
            make_row(bogus="x")]))))

    def test_empty_required_string_detected(self):
        self.assertIn("empty-required-string", checks(lint_obj(make_file([
            make_row(claim="")]))))


class StateAttachmentTests(unittest.TestCase):
    def test_agreed_without_approval_detected(self):
        row = make_agreed_row()
        del row["approval"]
        self.assertIn("approval-missing", checks(lint_obj(make_file([row]))))

    def test_delegated_requires_capability_fields(self):
        row = make_row(state="DELEGATED", delegation={"subject": "実装エージェント"})
        result = lint_obj(make_file([row]))
        # operation / scope / expiry / revocation missing
        self.assertIn("missing-required", checks(result))

    def test_delegated_complete_capability_ok(self):
        row = make_row(state="DELEGATED", delegation={
            "subject": "実装エージェント",
            "operation": "NAV コンポーネント実装",
            "scope": "現 plan のみ",
            "expiry": "本 plan 完了時",
            "revocation": "台帳行を UNDECIDED へ戻す",
        })
        self.assertEqual(lint_obj(make_file([row]))["findings"], [])

    def test_provisional_requires_reeval_condition(self):
        self.assertIn("reeval-condition-missing", checks(lint_obj(make_file([
            make_row(state="PROVISIONAL")]))))

    def test_provisional_with_reeval_condition_ok(self):
        row = make_row(state="PROVISIONAL",
                       reeval_condition="pilot の裁定時間実測後に再評価")
        self.assertEqual(lint_obj(make_file([row]))["findings"], [])

    def test_undecided_with_approval_is_forbidden(self):
        row = make_row(state="UNDECIDED",
                       approval=make_approval("トップナビはグローバル固定で全画面共通とする"))
        self.assertIn("attachment-not-allowed", checks(lint_obj(make_file([row]))))

    def test_rejected_with_delegation_is_forbidden(self):
        row = make_row(state="REJECTED", delegation={
            "subject": "x", "operation": "y", "scope": "z",
            "expiry": "w", "revocation": "v"})
        self.assertIn("attachment-not-allowed", checks(lint_obj(make_file([row]))))


class ApprovalAuthenticityTests(unittest.TestCase):
    def test_revision_mismatch_is_stale_approval(self):
        # row revised to 2 after approval captured at revision 1
        row = make_agreed_row(revision=2)
        row["approval"] = make_approval(row["claim"], revision=1)
        self.assertIn("approval-revision-mismatch",
                      checks(lint_obj(make_file([row]))))

    def test_digest_mismatch_means_claim_changed(self):
        row = make_agreed_row()
        row["claim"] = "主張が承認後に書き換わった"  # digest no longer matches
        self.assertIn("approval-digest-mismatch",
                      checks(lint_obj(make_file([row]))))

    def test_non_human_actor_rejected(self):
        row = make_agreed_row()
        row["approval"]["actor_kind"] = "llm"
        self.assertIn("approval-actor-not-human",
                      checks(lint_obj(make_file([row]))))

    def test_approval_row_id_mismatch_detected(self):
        row = make_agreed_row()
        row["approval"]["row_id"] = "NAV-999"
        self.assertIn("approval-row-id-mismatch",
                      checks(lint_obj(make_file([row]))))

    def test_approval_missing_required_field(self):
        row = make_agreed_row()
        del row["approval"]["session_id"]
        self.assertIn("missing-required", checks(lint_obj(make_file([row]))))

    def test_invalid_prior_state_detected(self):
        row = make_agreed_row()
        row["approval"]["prior_state"] = "NOPE"
        self.assertIn("invalid-prior-state",
                      checks(lint_obj(make_file([row]))))

    def test_invalid_revision_row_suppresses_double_mismatch(self):
        # An invalid row.revision already yields invalid-revision; comparing a
        # differing approval.revision against it must NOT add noise (I3 guard).
        row = make_agreed_row(revision=0)   # invalid row revision
        row["approval"]["revision"] = 1     # differs from the (invalid) 0
        cs = checks(lint_obj(make_file([row])))
        self.assertIn("invalid-revision", cs)
        self.assertNotIn("approval-revision-mismatch", cs)


class EpistemicSeparationTests(unittest.TestCase):
    def test_observation_assumption_conflation_detected(self):
        row = make_row(
            observations=["ログイン画面が存在する", "同じ文言"],
            assumptions=["同じ文言"],
        )
        self.assertIn("observation-assumption-conflation",
                      checks(lint_obj(make_file([row]))))

    def test_disjoint_observation_assumption_ok(self):
        row = make_row(
            observations=["ログイン画面が存在する"],
            assumptions=["SSO を使うと仮定"],
        )
        self.assertEqual(lint_obj(make_file([row]))["findings"], [])


class TermRefsTests(unittest.TestCase):
    def test_undefined_term_detected_with_context(self):
        row = make_row(term_refs=["T-UNKNOWN"])
        result = lint_obj(make_file([row]), context_terms={"T-1", "T-2"})
        self.assertIn("undefined-term", checks(result))

    def test_defined_term_ok_with_context(self):
        row = make_row(term_refs=["T-1"])
        result = lint_obj(make_file([row]), context_terms={"T-1", "T-2"})
        self.assertEqual(result["findings"], [])

    def test_term_refs_skipped_without_context(self):
        row = make_row(term_refs=["T-ANYTHING"])
        result = lint_obj(make_file([row]), context_terms=None)
        self.assertEqual(result["findings"], [])


class DiffInvariantTests(unittest.TestCase):
    def test_undecided_vanished_detected(self):
        baseline = {"NAV-001", "NAV-050"}
        row = make_row(id="NAV-001")  # NAV-050 gone
        result = lint_obj(make_file([row]), baseline_undecided_ids=baseline)
        self.assertIn("undecided-vanished", checks(result))

    def test_undecided_transitioned_is_not_vanished(self):
        baseline = {"NAV-001"}
        row = make_agreed_row(id="NAV-001")  # transitioned to AGREED
        result = lint_obj(make_file([row]), baseline_undecided_ids=baseline)
        self.assertNotIn("undecided-vanished", checks(result))


class SecretTests(unittest.TestCase):
    def test_secret_in_claim_detected(self):
        row = make_row(claim=f"接続キーは {FAKE_AWS} を使う")
        self.assertIn("secret-in-free-text", checks(lint_obj(make_file([row]))))

    def test_secret_masked_in_finding_output(self):
        row = make_row(observations=[f"token {FAKE_AWS} を観測"])
        result = lint_obj(make_file([row]))
        blob = json.dumps(result["findings"], ensure_ascii=False)
        self.assertNotIn(FAKE_AWS, blob)


class CorruptionTests(unittest.TestCase):
    def _write(self, tmp, text):
        path = os.path.join(tmp, "ledger.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_toplevel_not_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, "[]")
            result = ll.lint_paths([p])
            self.assertTrue(result["corrupt"])
            self.assertEqual(result["diagnostics"][0]["category"], "not-an-object")

    def test_missing_toplevel_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"schema_version": 1}')
            result = ll.lint_paths([p])
            self.assertEqual(result["diagnostics"][0]["category"],
                             "missing-toplevel-key")

    def test_rows_not_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"schema_version": 1, "rows": {}}')
            self.assertEqual(ll.lint_paths([p])["diagnostics"][0]["category"],
                             "rows-not-array")

    def test_unknown_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"schema_version": 2, "rows": []}')
            self.assertEqual(ll.lint_paths([p])["diagnostics"][0]["category"],
                             "unknown-schema-version")

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, "{not json")
            self.assertEqual(ll.lint_paths([p])["diagnostics"][0]["category"],
                             "invalid-json")

    def test_empty_file_is_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, "")
            self.assertEqual(ll.lint_paths([p])["diagnostics"][0]["category"],
                             "invalid-json")

    def test_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(
                tmp, '{"schema_version": 1, "rows": [], "rows": []}')
            self.assertEqual(ll.lint_paths([p])["diagnostics"][0]["category"],
                             "duplicate-json-key")

    def test_too_deep_nesting(self):
        with tempfile.TemporaryDirectory() as tmp:
            deep = "[" * 40 + "]" * 40
            p = self._write(tmp, deep)
            self.assertEqual(ll.lint_paths([p])["diagnostics"][0]["category"],
                             "too-deep")

    def test_file_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"schema_version":1,"rows":[]}')
            # patch stat via oversized real file
            big = os.path.join(tmp, "big.json")
            with open(big, "w") as f:
                f.write(" " * (ll.MAX_SIZE + 1))
            self.assertEqual(ll.lint_paths([big])["diagnostics"][0]["category"],
                             "file-too-large")


class ContainmentTests(unittest.TestCase):
    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ll.LedgerLintError):
                ll.check_containment("/etc/passwd", root)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "real.json")
            with open(target, "w") as f:
                f.write("{}")
            link = os.path.join(root, "link.json")
            os.symlink(target, link)
            with self.assertRaises(ll.LedgerLintError):
                ll.check_containment(link, root)


class ReadOnlyTests(unittest.TestCase):
    def test_lint_does_not_modify_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.json")
            content = json.dumps(make_file([make_row()]))
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            before = os.stat(path).st_mtime_ns
            snapshot = os.listdir(tmp)
            ll.lint_paths([path])
            self.assertEqual(os.stat(path).st_mtime_ns, before)
            self.assertEqual(sorted(os.listdir(tmp)), sorted(snapshot))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), content)


class CliTests(unittest.TestCase):
    def _run(self, args, tmp):
        return subprocess.run(
            [sys.executable, LEDGER_LINT, "--root", tmp, *args],
            capture_output=True, text=True)

    def _write(self, tmp, data, name="ledger.json"):
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data))
        return path

    def test_clean_report_only_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, make_file([make_row()]))
            self.assertEqual(self._run([p], tmp).returncode, 0)

    def test_findings_report_only_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, make_file([make_row(state="BOGUS")]))
            self.assertEqual(self._run([p], tmp).returncode, 0)

    def test_findings_strict_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, make_file([make_row(state="BOGUS")]))
            self.assertEqual(self._run([p, "--strict"], tmp).returncode, 1)

    def test_corruption_exit_2_mode_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, [])
            self.assertEqual(self._run([p], tmp).returncode, 2)
            self.assertEqual(self._run([p, "--strict"], tmp).returncode, 2)

    def test_json_output_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, make_file([make_row(state="BOGUS")]))
            out = self._run([p, "--json"], tmp)
            payload = json.loads(out.stdout)
            self.assertIn("valid", payload)
            self.assertIn("findings_present", payload)
            self.assertTrue(payload["findings_present"])

    def test_root_not_a_dir_usage_error(self):
        out = subprocess.run(
            [sys.executable, LEDGER_LINT, "--root", "/no/such/dir"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)


# ---------------------------------------------------------------------------
# Sync: agreement-ledger.md tables <-> code constants
# ---------------------------------------------------------------------------

def _tables_under(md_text, heading):
    """Return the markdown table data rows (list of cell lists) that appear
    under the given heading, up to the next heading of same-or-higher level."""
    lines = md_text.splitlines()
    out = []
    collecting = False
    for line in lines:
        if line.startswith("#"):
            collecting = heading in line
            continue
        if not collecting:
            continue
        s = line.strip()
        if s.startswith("|") and "---" not in s:
            cells = [c.strip() for c in s.strip("|").split("|")]
            out.append(cells)
    return out


def _first_token(cell):
    m = re.search(r"`([^`]+)`", cell)
    return m.group(1) if m else None


def _field_table(md_text, heading):
    """Parse a field table (フィールド | 型 | 必須 | ...) into
    {field: (type_token, required_bool)}. 必須 cell == `required` -> True;
    `optional` / 条件付き -> False."""
    out = {}
    for cells in _tables_under(md_text, heading):
        if len(cells) < 3:
            continue
        field = _first_token(cells[0])
        typ = _first_token(cells[1])
        if not field or not typ:
            continue
        out[field] = (typ, _first_token(cells[2]) == "required")
    return out


class SyncTests(unittest.TestCase):
    """agreement-ledger.md tables <-> code constants (md:3-6 drift guard)."""

    @classmethod
    def setUpClass(cls):
        with open(LEDGER_MD, encoding="utf-8") as f:
            cls.md = f.read()
        with open(LEDGER_LINT, encoding="utf-8") as f:
            cls.src = f.read()

    def test_states_match(self):
        rows = _tables_under(self.md, "状態と必須随伴フィールド")
        md_states = {_first_token(r[0]) for r in rows if _first_token(r[0])}
        self.assertEqual(md_states, set(ll.STATES))

    def test_state_attachment_match(self):
        md_map = {}
        for cells in _tables_under(self.md, "状態と必須随伴フィールド"):
            st = _first_token(cells[0])
            att = _first_token(cells[1]) if len(cells) >= 2 else None
            if st and att:
                md_map[st] = att
        self.assertEqual(md_map, dict(ll.STATE_ATTACHMENT))

    def test_corruption_slugs_match_raise_sites(self):
        # Compare md's slug list against the ACTUAL category-producing sites in
        # the source (LedgerLintError raises + literal internal diagnostics),
        # not a hand-maintained constant that could drift from the raises.
        code_slugs = set(re.findall(r'LedgerLintError\(\s*"([a-z-]+)"', self.src))
        code_slugs |= set(re.findall(r'"category":\s*"([a-z-]+)"', self.src))
        md_slugs = set(re.findall(r"^- `([a-z-]+)` —", self.md, re.MULTILINE))
        self.assertTrue(md_slugs)
        self.assertEqual(code_slugs, md_slugs)

    def test_input_limits_match(self):
        values = {}
        for r in _tables_under(self.md, "入力上限と破損カテゴリ"):
            slug = _first_token(r[2]) if len(r) >= 3 else None
            num = re.search(r"`(\d+)`", r[1]) if len(r) >= 2 else None
            if slug and num:
                values[slug] = int(num.group(1))
        self.assertEqual(values.get("file-too-large"), ll.MAX_SIZE)
        self.assertEqual(values.get("too-many-rows"), ll.MAX_ROWS)
        self.assertEqual(values.get("too-deep"), ll.MAX_DEPTH)

    def test_row_fields_full_match(self):
        self.assertEqual(_field_table(self.md, "共通 row（行）"),
                         dict(ll.ROW_FIELDS))

    def test_approval_fields_match(self):
        self.assertEqual(_field_table(self.md, "承認イベント"),
                         dict(ll.APPROVAL_FIELDS))

    def test_delegation_fields_match(self):
        self.assertEqual(_field_table(self.md, "委任 capability"),
                         dict(ll.DELEGATION_FIELDS))

    def test_toplevel_fields_match(self):
        self.assertEqual(_field_table(self.md, "ファイル構造"),
                         dict(ll.TOPLEVEL_FIELDS))

    def test_id_pattern_match(self):
        pat = None
        for cells in _tables_under(self.md, "ID・revision 規則"):
            tok = _first_token(cells[1]) if len(cells) >= 2 else None
            if tok and tok.startswith("^"):
                pat = tok
        self.assertEqual(pat, ll.ID_PATTERN)

    def test_actor_kinds_match(self):
        # Parse the actor_kind enum out of the 承認イベント table so md/code
        # drift is caught if the enum ever changes (not a tautological assert).
        md_actors = set()
        for cells in _tables_under(self.md, "承認イベント"):
            if _first_token(cells[0]) == "actor_kind" and len(cells) >= 4:
                m = re.search(r"enum:\s*((?:`[^`]+`(?:\s*/\s*)?)+)", cells[3])
                if m:
                    md_actors = set(re.findall(r"`([^`]+)`", m.group(1)))
        self.assertEqual(md_actors, set(ll.ACTOR_KINDS))


class ContextLoadTests(unittest.TestCase):
    def _write(self, tmp, text):
        p = os.path.join(tmp, "ctx.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_unknown_schema_version_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"schema_version": 99, "terms": []}')
            with self.assertRaises(ll.LedgerLintError):
                ll.load_context_terms(p)

    def test_missing_schema_version_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"terms": []}')
            with self.assertRaises(ll.LedgerLintError):
                ll.load_context_terms(p)

    def test_terms_not_array_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"schema_version": 1, "terms": {}}')
            with self.assertRaises(ll.LedgerLintError):
                ll.load_context_terms(p)

    def test_valid_context_returns_ids_with_states(self):
        # load_context_terms now returns {id: state} so pending-vocabulary can
        # read the vocabulary-specific state (§C), not just membership.
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(
                tmp,
                '{"schema_version":1,"terms":[{"id":"T-1","term":"a",'
                '"state":"確定"}]}')
            self.assertEqual(ll.load_context_terms(p), {"T-1": "確定"})

    def test_context_membership_survives_dict_form(self):
        # term_refs membership (undefined-term) must still work when the
        # loader returns a dict keyed by term id.
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(
                tmp,
                '{"schema_version":1,"terms":[{"id":"T-1","term":"a",'
                '"state":"競合中"}]}')
            terms = ll.load_context_terms(p)
            self.assertIn("T-1", terms)
            self.assertEqual(terms["T-1"], "競合中")


class BaselineLoadTests(unittest.TestCase):
    def _write(self, tmp, data):
        p = os.path.join(tmp, "base.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return p

    def test_corrupt_baseline_raises_not_silent_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, '{"schema_version": 1, "rows": {}}')
            with self.assertRaises(ll.LedgerLintError):
                ll.load_baseline_undecided_ids(p)

    def test_valid_baseline_returns_undecided_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, make_file([
                make_row(id="NAV-001"),
                make_agreed_row(id="NAV-002", claim="x"),
            ]))
            self.assertEqual(
                ll.load_baseline_undecided_ids(p), {"NAV-001"})


class LintNeverRaisesTests(unittest.TestCase):
    """The lint over untrusted input must never crash — fail-closed instead."""

    def test_reviewer_mixed_type_examples_do_not_crash(self):
        for refs in (["T-1", 5], [None, None]):
            row = {
                "id": "NAV-001", "revision": 1, "state": "AGREED",
                "claim": "x", "term_refs": refs,
                "approval": {
                    "row_id": "NAV-001", "revision": 1, "digest": "z",
                    "session_id": "S-1", "actor_kind": "human",
                    "prior_state": "UNDECIDED"},
            }
            result = lint_obj(make_file([row]))  # must not raise
            self.assertTrue(result["findings"] or result["diagnostics"])

    def test_unexpected_row_error_becomes_internal_error_diagnostic(self):
        def boom(*_a, **_k):
            raise RuntimeError("unexpected")
        original = ll._check_row
        ll._check_row = boom
        try:
            result = ll.lint_data([("ledger.json", make_file([make_row()]))])
        finally:
            ll._check_row = original
        self.assertTrue(result["corrupt"])
        self.assertEqual(result["diagnostics"][0]["category"], "internal-error")

    def test_healthy_and_corrupt_file_mix(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "good.json")
            bad = os.path.join(tmp, "bad.json")
            with open(good, "w", encoding="utf-8") as f:
                f.write(json.dumps(make_file([make_row(state="BOGUS")])))
            with open(bad, "w", encoding="utf-8") as f:
                f.write("[]")
            result = ll.lint_paths([good, bad])
            self.assertTrue(result["corrupt"])       # bad -> diagnostic
            self.assertTrue(result["findings"])       # good -> findings kept


class SecretLeakTests(unittest.TestCase):
    def test_credential_shaped_invalid_id_not_leaked(self):
        row = make_row(id=f"X{FAKE_AWS}")  # invalid id pattern
        result = lint_obj(make_file([row]))
        blob = json.dumps(result["findings"], ensure_ascii=False)
        self.assertNotIn(FAKE_AWS, blob)  # masked in what, and never in where
        for f in result["findings"]:
            self.assertNotIn(FAKE_AWS, f["where"])

    def test_cli_no_traceback_on_mixed_type_term_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "ledger.json")
            row = {
                "id": "NAV-001", "revision": 1, "state": "AGREED",
                "claim": "x", "term_refs": ["T-1", 5],
                "approval": {
                    "row_id": "NAV-001", "revision": 1, "digest": "z",
                    "session_id": "S-1", "actor_kind": "human",
                    "prior_state": "UNDECIDED"},
            }
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"schema_version": 1, "rows": [row]}, f)
            out = subprocess.run(
                [sys.executable, LEDGER_LINT, "--root", tmp, p],
                capture_output=True, text=True)
            self.assertIn(out.returncode, (0, 1, 2))
            self.assertNotIn("Traceback", out.stderr)


class RiskFieldTests(unittest.TestCase):
    def test_valid_high_risk_row_alone_ok(self):
        # A high-risk row on its own is valid; the batch prohibition only
        # applies when it appears inside a batch manifest.
        self.assertEqual(
            lint_obj(make_file([make_row(risk="high")]))["findings"], [])

    def test_valid_normal_risk_row_ok(self):
        self.assertEqual(
            lint_obj(make_file([make_row(risk="normal")]))["findings"], [])

    def test_unknown_risk_value_detected(self):
        self.assertIn("unknown-risk", checks(lint_obj(make_file([
            make_row(risk="critical")]))))

    def test_row_without_risk_is_backward_compatible(self):
        # Existing ledgers have no risk field; they must stay valid (optional).
        self.assertEqual(lint_obj(make_file([make_row()]))["findings"], [])


class BatchManifestTests(unittest.TestCase):
    def test_valid_batch_manifest_no_findings(self):
        rows = [make_row(id="NAV-001"), make_row(id="NAV-002")]
        digests = [ll.compute_digest(r) for r in rows]
        result = lint_obj(make_file(
            rows, batch_manifests=[make_batch_manifest(digests)]))
        self.assertEqual(result["findings"], [])

    def test_ledger_without_batch_manifests_is_backward_compatible(self):
        # schema_version 1 ledgers predating batch_manifests stay valid — the
        # key is optional at the top level (§B backward compatibility).
        result = lint_obj(make_file([make_row()]))
        self.assertEqual(result["findings"], [])
        self.assertFalse(result["corrupt"])

    def test_batch_digest_mismatch_detected(self):
        rows = [make_row(id="NAV-001")]
        digests = [ll.compute_digest(r) for r in rows]
        manifest = make_batch_manifest(digests)
        manifest["batch_digest"] = "0" * 64  # no longer matches constituents
        result = lint_obj(make_file(rows, batch_manifests=[manifest]))
        self.assertIn("batch-digest-mismatch", checks(result))

    def test_high_risk_row_in_batch_detected(self):
        high = make_row(id="RISK-001", risk="high")
        digests = [ll.compute_digest(high)]
        result = lint_obj(make_file(
            [high], batch_manifests=[make_batch_manifest(digests)]))
        self.assertIn("high-risk-in-batch", checks(result))

    def test_batch_manifest_missing_required_field_detected(self):
        manifest = make_batch_manifest([ll.compute_digest(make_row())])
        del manifest["summary_digest"]
        result = lint_obj(make_file([make_row()], batch_manifests=[manifest]))
        self.assertIn("missing-required", checks(result))

    def test_batch_manifest_unknown_key_detected(self):
        manifest = make_batch_manifest([ll.compute_digest(make_row())])
        manifest["bogus"] = "x"
        result = lint_obj(make_file([make_row()], batch_manifests=[manifest]))
        self.assertIn("unknown-key", checks(result))

    def test_batch_manifests_not_array_detected(self):
        result = lint_obj(make_file([make_row()], batch_manifests={}))
        self.assertIn("invalid-type", checks(result))

    def test_batch_manifest_not_object_detected(self):
        result = lint_obj(make_file([make_row()], batch_manifests=["x"]))
        self.assertIn("invalid-type", checks(result))

    def test_batch_manifest_optional_fields_ok(self):
        rows = [make_row(id="NAV-001")]
        digests = [ll.compute_digest(r) for r in rows]
        manifest = make_batch_manifest(
            digests, excluded_rows=["NAV-009"], dependencies=["NAV-000"])
        self.assertEqual(
            lint_obj(make_file(rows, batch_manifests=[manifest]))["findings"],
            [])


class ComputeBatchDigestTests(unittest.TestCase):
    def test_batch_digest_ignores_row_digest_order(self):
        a = ll.compute_batch_digest(["d1", "d2"], "sum")
        b = ll.compute_batch_digest(["d2", "d1"], "sum")
        self.assertEqual(a, b)

    def test_batch_digest_total_on_malformed_input(self):
        # Must be total: malformed manifests get type findings elsewhere, the
        # digest helper must never crash the linter (fail-closed).
        self.assertIsInstance(ll.compute_batch_digest(5, None), str)


class PendingVocabularyTests(unittest.TestCase):
    def test_agreed_undefined_term_escalated_to_pending_vocabulary(self):
        row = make_agreed_row(term_refs=["T-UNKNOWN"])
        result = lint_obj(make_file([row]), context_terms={"T-1": "確定"})
        cs = checks(result)
        self.assertIn("pending-vocabulary", cs)   # (a) confirmed escalation
        self.assertIn("undefined-term", cs)       # all-state check still fires

    def test_undecided_undefined_term_not_escalated(self):
        row = make_row(term_refs=["T-UNKNOWN"])   # UNDECIDED
        result = lint_obj(make_file([row]), context_terms={"T-1": "確定"})
        cs = checks(result)
        self.assertIn("undefined-term", cs)
        self.assertNotIn("pending-vocabulary", cs)

    def test_agreed_conflicting_term_is_advisory_only(self):
        row = make_agreed_row(term_refs=["T-C"])
        result = lint_obj(make_file([row]), context_terms={"T-C": "競合中"})
        self.assertIn("unstable-term-dependency", advisory_checks(result))
        self.assertEqual(result["findings"], [])   # (b) does not gate

    def test_agreed_deprecated_term_is_advisory_only(self):
        row = make_agreed_row(term_refs=["T-D"])
        result = lint_obj(make_file([row]), context_terms={"T-D": "廃語"})
        self.assertIn("unstable-term-dependency", advisory_checks(result))
        self.assertEqual(result["findings"], [])

    def test_agreed_confirmed_term_no_finding_no_advisory(self):
        row = make_agreed_row(term_refs=["T-OK"])
        result = lint_obj(make_file([row]), context_terms={"T-OK": "確定"})
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["advisories"], [])

    def test_advisories_key_present_on_clean_ledger(self):
        result = lint_obj(make_file([make_row()]))
        self.assertEqual(result["advisories"], [])


class SyncTestsV2(unittest.TestCase):
    """New schema tables (§B) <-> code constants (§D lockstep)."""

    @classmethod
    def setUpClass(cls):
        with open(LEDGER_MD, encoding="utf-8") as f:
            cls.md = f.read()

    def test_batch_manifest_fields_match(self):
        self.assertEqual(_field_table(self.md, "batch 承認 manifest"),
                         dict(ll.BATCH_MANIFEST_FIELDS))

    def test_toplevel_includes_batch_manifests(self):
        self.assertEqual(_field_table(self.md, "ファイル構造"),
                         dict(ll.TOPLEVEL_FIELDS))
        self.assertIn("batch_manifests", ll.TOPLEVEL_FIELDS)

    def test_row_fields_include_risk(self):
        self.assertEqual(_field_table(self.md, "共通 row（行）"),
                         dict(ll.ROW_FIELDS))
        self.assertIn("risk", ll.ROW_FIELDS)

    def test_risk_levels_match(self):
        md_risks = set()
        for cells in _tables_under(self.md, "共通 row（行）"):
            if _first_token(cells[0]) == "risk" and len(cells) >= 4:
                m = re.search(r"enum:\s*((?:`[^`]+`(?:\s*/\s*)?)+)", cells[3])
                if m:
                    md_risks = set(re.findall(r"`([^`]+)`", m.group(1)))
        self.assertEqual(md_risks, set(ll.RISK_LEVELS))


class AdvisoryGateTests(unittest.TestCase):
    def _run(self, args, tmp):
        return subprocess.run(
            [sys.executable, LEDGER_LINT, "--root", tmp, *args],
            capture_output=True, text=True)

    def test_advisory_does_not_gate_under_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = os.path.join(tmp, "ctx.json")
            with open(ctx, "w", encoding="utf-8") as f:
                json.dump({"schema_version": 1, "terms": [
                    {"id": "T-C", "term": "x", "state": "競合中"}]}, f)
            ledger = os.path.join(tmp, "ledger.json")
            with open(ledger, "w", encoding="utf-8") as f:
                json.dump(make_file([make_agreed_row(term_refs=["T-C"])]), f)
            out = self._run([ledger, "--strict", "--context", ctx], tmp)
            self.assertEqual(out.returncode, 0)   # advisory-only: no gate

    def test_json_output_includes_advisories(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = os.path.join(tmp, "ctx.json")
            with open(ctx, "w", encoding="utf-8") as f:
                json.dump({"schema_version": 1, "terms": [
                    {"id": "T-C", "term": "x", "state": "廃語"}]}, f)
            ledger = os.path.join(tmp, "ledger.json")
            with open(ledger, "w", encoding="utf-8") as f:
                json.dump(make_file([make_agreed_row(term_refs=["T-C"])]), f)
            out = self._run([ledger, "--json", "--context", ctx], tmp)
            payload = json.loads(out.stdout)
            self.assertIn("advisories", payload)
            self.assertTrue(payload["advisories"])


if __name__ == "__main__":
    unittest.main()
