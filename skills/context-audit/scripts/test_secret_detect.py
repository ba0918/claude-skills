#!/usr/bin/env python3
"""Unit tests for the shared secret_detect module (skills/shared/scripts).

context-audit reuses skill-improve's secret detection instead of hand-rolling
new regexes. These tests are the regression suite for the shared module and
also assert parity with skill-improve/collect.py (the original home) so the
two cannot silently drift.

Sample secrets are assembled via concatenation so the values never appear as
literals (repo secret-scanning hook).
"""

import os
import sys
import unittest

# Import the shared module the same way the production scripts do.
_SHARED = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared", "scripts"
)
sys.path.insert(0, _SHARED)

import secret_detect as sd  # noqa: E402


SAMPLE_AWS = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
SAMPLE_JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "eyJ" + "zdWIiOiIxMjM" + "." + "SflKxwRJSMeK"
SAMPLE_ANTHROPIC = "sk" + "-ant-" + ("A1b2c3" * 8)
SAMPLE_EMAIL = "alice" + "@" + "example.com"


class TestDetectSecrets(unittest.TestCase):
    def test_detects_aws_key(self):
        found = {f["type"] for f in sd.detect_secrets(f"key {SAMPLE_AWS} end")}
        self.assertIn("aws_key", found)

    def test_detects_email(self):
        found = {f["type"] for f in sd.detect_secrets(f"mail {SAMPLE_EMAIL}")}
        self.assertIn("email", found)

    def test_no_false_positive_on_plain_text(self):
        self.assertEqual(sd.detect_secrets("just some normal prose here"), [])

    def test_finding_shape(self):
        findings = sd.detect_secrets(f"key {SAMPLE_AWS}")
        self.assertTrue(all("type" in f and "masked" in f for f in findings))


class TestMaskSecrets(unittest.TestCase):
    def test_masks_aws(self):
        masked = sd.mask_secrets(f"x {SAMPLE_AWS} y")
        self.assertNotIn(SAMPLE_AWS, masked)
        self.assertIn("[REDACTED:aws_key]", masked)

    def test_masks_jwt_including_signature(self):
        masked = sd.mask_secrets(f"auth {SAMPLE_JWT} end")
        self.assertNotIn("SflKxwRJSMeK", masked)

    def test_masks_anthropic_key(self):
        masked = sd.mask_secrets(f"key {SAMPLE_ANTHROPIC} end")
        self.assertNotIn(SAMPLE_ANTHROPIC, masked)

    def test_idempotent(self):
        once = sd.mask_secrets(f"x {SAMPLE_AWS} y")
        twice = sd.mask_secrets(once)
        self.assertEqual(once, twice)

    def test_plain_text_unchanged(self):
        text = "no secrets in this line"
        self.assertEqual(sd.mask_secrets(text), text)


class TestParityWithCollect(unittest.TestCase):
    """The shared module must be the single source of truth: skill-improve's
    collect.py re-exports it, so their patterns/behavior must be identical."""

    def _collect(self):
        collect_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "skill-improve", "scripts",
        )
        sys.path.insert(0, collect_dir)
        import collect  # noqa: E402
        return collect

    def test_pattern_names_match(self):
        collect = self._collect()
        shared_names = [name for name, _ in sd.SECRET_PATTERNS]
        collect_names = [name for name, _ in collect.SECRET_PATTERNS]
        self.assertEqual(shared_names, collect_names)

    def test_mask_output_matches(self):
        collect = self._collect()
        text = f"aws {SAMPLE_AWS} mail {SAMPLE_EMAIL} jwt {SAMPLE_JWT}"
        self.assertEqual(sd.mask_secrets(text), collect.mask_secrets(text))


if __name__ == "__main__":
    unittest.main()
