#!/usr/bin/env python3
"""Unit tests for collect.py (skill-improve + trigger-eval --capture-prompts).

Secret literals are assembled at runtime from fragments so that repo secret
scanners do not flag this test file. The assembled strings still exercise the
real masking patterns.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import collect

# --- runtime-assembled sample secrets (avoid literal secrets in source) ---
SAMPLE_AWS = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
SAMPLE_PEM = "-----BEGIN RSA " + "PRIVATE KEY-----"
SAMPLE_JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0"
SAMPLE_JWT_3PART = SAMPLE_JWT + "." + "aGmacSignatureSecretPart123456"
SAMPLE_OPENAI_PROJ = "sk" + "-proj-" + ("A1b2_-" * 6)
SAMPLE_XOXB = "xo" + "xb-" + "123456789012-" + "abcdefghijklmnop"
SAMPLE_GHP = "gh" + "p_" + ("a" * 36)
SAMPLE_GH_PAT = "github" + "_pat_" + ("A1b2" * 10)
SAMPLE_OPENAI = "sk" + "-" + ("A1b2" * 12)
SAMPLE_ANTHROPIC = "sk" + "-ant-" + ("A1b2c3" * 8)
SAMPLE_GOOGLE = "AI" + "za" + ("A1b2c3d4" * 4)


class TestSecretMasking(unittest.TestCase):
    """Each secret class must be masked to [REDACTED:kind], quoted or not."""

    def _assert_masked(self, text, kind):
        masked = collect.mask_secrets(text)
        self.assertIn(f"[REDACTED:{kind}]", masked, f"kind={kind} not masked in: {masked}")
        found = {f["type"] for f in collect.detect_secrets(text)}
        self.assertIn(kind, found)

    def test_aws_key(self):
        self._assert_masked(f"key {SAMPLE_AWS} here", "aws_key")

    def test_private_key(self):
        self._assert_masked(SAMPLE_PEM, "private_key")

    def test_jwt(self):
        self._assert_masked(SAMPLE_JWT, "jwt")

    def test_email(self):
        self._assert_masked("contact me at alice@example.com please", "email")

    def test_home_path(self):
        self._assert_masked("see /home/someuser/develop/secret", "home_path")

    def test_ghp_token_unquoted(self):
        self._assert_masked(f"token {SAMPLE_GHP} end", "prefix_token")

    def test_ghp_token_quoted(self):
        self._assert_masked(f'token "{SAMPLE_GHP}"', "prefix_token")

    def test_github_pat(self):
        self._assert_masked(SAMPLE_GH_PAT, "prefix_token")

    def test_slack_bot_token(self):
        self._assert_masked(SAMPLE_XOXB, "prefix_token")

    def test_openai_key(self):
        self._assert_masked(SAMPLE_OPENAI, "prefix_token")

    def test_anthropic_key(self):
        self._assert_masked(SAMPLE_ANTHROPIC, "prefix_token")

    def test_google_api_key(self):
        self._assert_masked(SAMPLE_GOOGLE, "prefix_token")

    def test_openai_proj_key(self):
        # modern sk-proj- keys contain a dash and must still be masked
        self._assert_masked(SAMPLE_OPENAI_PROJ, "prefix_token")

    def test_jwt_signature_not_leaked(self):
        # a 3-part JWT must not leave the signature segment in plaintext
        masked = collect.mask_secrets(f"auth {SAMPLE_JWT_3PART} end")
        self.assertNotIn("aGmacSignatureSecretPart123456", masked)

    def test_anthropic_key_no_leftover(self):
        masked = collect.mask_secrets(f"key {SAMPLE_ANTHROPIC} end")
        self.assertNotIn(SAMPLE_ANTHROPIC, masked)
        # no residual of the raw key survives outside the placeholder
        self.assertNotIn(SAMPLE_ANTHROPIC[6:20], masked)

    def test_no_partial_disclosure(self):
        # full mask: none of the original secret chars leak
        masked = collect.mask_secrets(f"x {SAMPLE_AWS} y")
        self.assertNotIn(SAMPLE_AWS, masked)
        self.assertNotIn(SAMPLE_AWS[:8], masked.replace("[REDACTED:aws_key]", ""))


class TestDedupKey(unittest.TestCase):
    def test_same_type_collapses(self):
        secrets = [
            {"type": "email", "masked": "[REDACTED:email]"},
            {"type": "email", "masked": "[REDACTED:email]"},
        ]
        self.assertEqual(len(collect._deduplicate_secrets(secrets)), 1)


class TestValidateCaptureOutputPath(unittest.TestCase):
    def test_accepts_inside_claude_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".claude" / "tmp"
            base.mkdir(parents=True)
            out = base / "trigger-eval-x"
            out.mkdir()
            target = str(out / "prompts.jsonl")
            resolved = collect.validate_capture_output_path(target, base)
            self.assertIsNotNone(resolved)

    def test_rejects_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".claude" / "tmp"
            base.mkdir(parents=True)
            outside = Path(tmp) / "elsewhere"
            outside.mkdir()
            self.assertIsNone(
                collect.validate_capture_output_path(str(outside / "p.jsonl"), base)
            )

    def test_rejects_sibling_escape(self):
        # .claude/tmp2 must not be accepted as if inside .claude/tmp
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".claude" / "tmp"
            base.mkdir(parents=True)
            sibling = Path(tmp) / ".claude" / "tmp2"
            sibling.mkdir()
            self.assertIsNone(
                collect.validate_capture_output_path(str(sibling / "p.jsonl"), base)
            )

    def test_rejects_dotdot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".claude" / "tmp"
            base.mkdir(parents=True)
            self.assertIsNone(
                collect.validate_capture_output_path(str(base / ".." / "p.jsonl"), base)
            )

    def test_rejects_dotdot_as_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".claude" / "tmp"
            base.mkdir(parents=True)
            # a path whose final component is ".." must be rejected
            self.assertIsNone(
                collect.validate_capture_output_path(str(base) + "/sub/..", base)
            )


class TestGitIgnoreGate(unittest.TestCase):
    def setUp(self):
        # Hermetic git: ignore user/system config (also lets the sandbox run it).
        self._saved = {k: os.environ.get(k) for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")}
        os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
        os.environ["GIT_CONFIG_SYSTEM"] = os.devnull

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _init_repo(self, root):
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
        (root / ".gitignore").write_text(".claude/tmp/\n")

    def test_non_ignored_path_refused(self):
        # fail-closed: a path git does not ignore must return False
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            tracked = root / "tracked.jsonl"
            tracked.write_text("{}\n")
            self.assertFalse(collect.output_is_git_ignored(tracked))

    def test_ignored_path_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            ignored_dir = root / ".claude" / "tmp"
            ignored_dir.mkdir(parents=True)
            ignored = ignored_dir / "p.jsonl"
            ignored.write_text("{}\n")
            self.assertTrue(collect.output_is_git_ignored(ignored))

    def test_no_git_repo_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            # no git repo here -> undecidable -> refuse
            p = Path(tmp) / "p.jsonl"
            p.write_text("{}\n")
            self.assertFalse(collect.output_is_git_ignored(p))


class TestMtimePreFilter(unittest.TestCase):
    def test_filters_old_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recent = root / "recent.jsonl"
            old = root / "old.jsonl"
            recent.write_text("{}\n")
            old.write_text("{}\n")
            old_time = time.time() - 40 * 86400
            os.utime(old, (old_time, old_time))
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            kept = collect.filter_files_by_mtime([recent, old], cutoff)
            self.assertIn(recent, kept)
            self.assertNotIn(old, kept)


class TestCaptureRecords(unittest.TestCase):
    def _session(self, root, lines):
        p = root / "s.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_schema_and_masking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime.now(timezone.utc).isoformat()
            lines = [
                json.dumps({
                    "timestamp": now,
                    "message": {"role": "user", "content": "email me at bob@example.com"},
                }),
                json.dumps({
                    "timestamp": now,
                    "message": {"role": "user", "content": "/claude-skills:commit please"},
                }),
            ]
            p = self._session(root, lines)
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            records = collect.extract_capture_records(p, cutoff, project="proj")
            # every record has the fixed schema
            for r in records:
                self.assertEqual(
                    set(r.keys()),
                    {"ts", "project", "user_text_masked", "fired_skill", "signals"},
                )
                self.assertIsInstance(r["signals"], list)
            # user text masked
            joined = " ".join(r["user_text_masked"] for r in records)
            self.assertNotIn("bob@example.com", joined)
            self.assertIn("[REDACTED:email]", joined)
            # slash fire captured as bare name
            fired = [r["fired_skill"] for r in records if r["fired_skill"]]
            self.assertIn("commit", fired)

    def test_broken_and_empty_lines_tolerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime.now(timezone.utc).isoformat()
            lines = [
                "",
                "{not valid json",
                json.dumps({"timestamp": now, "message": {"role": "user", "content": "hi"}}),
            ]
            p = self._session(root, lines)
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            records = collect.extract_capture_records(p, cutoff, project="proj")
            self.assertEqual(len(records), 1)


class TestBodyFreeRegression(unittest.TestCase):
    """Default (body-free) output path and --output behavior stay unchanged."""

    def test_process_session_file_shape_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime.now(timezone.utc).isoformat()
            p = root / "s.jsonl"
            p.write_text(json.dumps({
                "timestamp": now,
                "message": {"role": "user", "content": "/claude-skills:plan go"},
            }) + "\n", encoding="utf-8")
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            result = collect.process_session_file(p, cutoff)
            # structural keys preserved (no message body leaked)
            self.assertIn("skill_invocations", result)
            self.assertIn("friction_signals", result)
            self.assertNotIn("user_text", json.dumps(result))

    def test_output_writer_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            collect._output_result({"ok": True}, str(out))
            self.assertEqual(json.loads(out.read_text())["ok"], True)


if __name__ == "__main__":
    unittest.main()
