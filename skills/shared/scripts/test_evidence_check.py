"""evidence_check.py の検証。

テスト名は仕様（What）を語る: publishable になる条件・ならない理由・検査不能の区別。
証跡不在が「skip される」のではなく「否定判定になる」ことを同じ重みで検証する
（vacuous pass の構造的排除が本スクリプトの存在理由の半分であるため）。
"""

import json
import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout

import evidence_check

SHA_A = "a" * 40
SHA_B = "b" * 40

CONTRACT_TEXT = (
    "# Quality Gate Contract\n\n"
    "## Contract Identity\n\n"
    "This contract carries an explicit, machine-readable version: "
    "**`quality-gate-contract 1.0.0`**.\n"
)

PROFILE_TEXT = (
    "# Profile\n\n"
    "`in-force: skill-repository-profile 1.0.0 since 2026-08-03`\n\n"
    "Identity: `skill-repository-profile 1.0.0`\n\n"
    "Conforms to `quality-gate-contract 1.0.0`.\n"
)


def write_record(evidence_dir, filename_state, **overrides):
    record = {
        "schema_version": 1,
        "state": filename_state,
        "target_sha": SHA_A,
        "contract": "quality-gate-contract",
        "contract_version": "1.0.0",
        "profile": None,
        "produced_at": "2026-07-28T12:00:00Z",
        "grounds": "unit-test fixture",
    }
    record.update(overrides)
    path = os.path.join(evidence_dir, f"{filename_state}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    return path


class EvidenceCheckHarness(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        self.contract_path = os.path.join(self.root, "contract.md")
        with open(self.contract_path, "w", encoding="utf-8") as handle:
            handle.write(CONTRACT_TEXT)
        self.evidence_dir = os.path.join(self.root, "evidence")
        os.makedirs(self.evidence_dir)

    def run_check(self, **kwargs):
        argv = ["--repo-root", self.root,
                "--evidence-dir", kwargs.pop("evidence_dir", self.evidence_dir),
                "--target-sha", kwargs.pop("target_sha", SHA_A),
                "--contract", kwargs.pop("contract", self.contract_path)]
        profile = kwargs.pop("profile", None)
        if profile is not None:
            argv.extend(["--profile", profile])
        assert not kwargs, kwargs
        return evidence_check.run(argv)

    def write_profile(self, text=PROFILE_TEXT):
        path = os.path.join(self.root, "profile.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path


class TestPublishableJudgment(EvidenceCheckHarness):
    def test_both_states_valid_and_bound_to_target_is_publishable(self):
        write_record(self.evidence_dir, "machine_verified")
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 0)

    def test_missing_evidence_directory_is_a_negative_judgment_not_a_skip(self):
        missing = os.path.join(self.root, "no-such-dir")
        self.assertEqual(self.run_check(evidence_dir=missing), 1)

    def test_one_state_absent_blocks_publishable(self):
        write_record(self.evidence_dir, "machine_verified")
        self.assertEqual(self.run_check(), 1)

    def test_new_commit_on_top_of_reviewed_version_expires_the_evidence(self):
        write_record(self.evidence_dir, "machine_verified")
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(target_sha=SHA_B), 1)

    def test_contract_version_mismatch_makes_evidence_invalid(self):
        write_record(self.evidence_dir, "machine_verified", contract_version="0.9.0")
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 1)


class TestInvalidEvidenceIsJudgedNotSkipped(EvidenceCheckHarness):
    def test_malformed_json_record_blocks_publishable(self):
        write_record(self.evidence_dir, "semantic_reviewed")
        path = os.path.join(self.evidence_dir, "machine_verified.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(self.run_check(), 1)

    def test_unknown_schema_version_blocks_publishable(self):
        write_record(self.evidence_dir, "machine_verified", schema_version=2)
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 1)

    def test_state_field_disagreeing_with_filename_blocks_publishable(self):
        write_record(self.evidence_dir, "machine_verified", state="semantic_reviewed")
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 1)

    def test_abbreviated_target_sha_blocks_publishable(self):
        write_record(self.evidence_dir, "machine_verified", target_sha=SHA_A[:12])
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 1)

    def test_empty_grounds_blocks_publishable(self):
        write_record(self.evidence_dir, "machine_verified", grounds="   ")
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 1)

    def test_non_null_profile_blocks_publishable_when_no_profile_is_in_force(self):
        write_record(self.evidence_dir, "machine_verified",
                     profile={"name": "skill-repository", "version": "1.0.0"})
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 1)

    def test_missing_profile_field_blocks_publishable_when_none_is_in_force(self):
        path = write_record(self.evidence_dir, "machine_verified")
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        del record["profile"]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        write_record(self.evidence_dir, "semantic_reviewed")
        self.assertEqual(self.run_check(), 1)


class TestInForceProfileJudgment(EvidenceCheckHarness):
    def setUp(self):
        super().setUp()
        self.profile_path = self.write_profile()

    def write_both(self, profile):
        write_record(self.evidence_dir, "machine_verified", profile=profile)
        write_record(self.evidence_dir, "semantic_reviewed", profile=profile)

    def test_exact_profile_binding_is_publishable_and_visible(self):
        self.write_both({"name": "skill-repository-profile", "version": "1.0.0"})
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.run_check(profile=self.profile_path)
        self.assertEqual(result, 0)
        self.assertIn("in force since", output.getvalue())

    def test_null_profile_blocks_publishable_with_binding_reason(self):
        self.write_both(None)
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.run_check(profile=self.profile_path)
        self.assertEqual(result, 1)
        self.assertIn("binding required", output.getvalue())

    def test_wrong_profile_version_blocks_publishable(self):
        self.write_both({"name": "skill-repository-profile", "version": "0.9.0"})
        self.assertEqual(self.run_check(profile=self.profile_path), 1)

    def test_extra_profile_key_blocks_publishable(self):
        self.write_both({
            "name": "skill-repository-profile", "version": "1.0.0", "extra": True
        })
        self.assertEqual(self.run_check(profile=self.profile_path), 1)

    def test_profile_conforming_to_other_contract_breaks_check(self):
        path = self.write_profile(PROFILE_TEXT.replace(
            "quality-gate-contract 1.0.0", "quality-gate-contract 2.0.0"
        ))
        self.write_both({"name": "skill-repository-profile", "version": "1.0.0"})
        with self.assertRaises(evidence_check.CheckBroken):
            self.run_check(profile=path)

    def test_profile_without_in_force_declaration_retains_null_behavior(self):
        path = self.write_profile(
            "Identity: `skill-repository-profile 1.0.0`\n"
            "Conforms to `quality-gate-contract 1.0.0`.\n"
        )
        self.write_both(None)
        self.assertEqual(self.run_check(profile=path), 0)


class TestReadInForceProfile(EvidenceCheckHarness):
    def test_absent_profile_returns_none(self):
        self.assertIsNone(evidence_check.read_in_force_profile(
            os.path.join(self.root, "absent-profile.md")
        ))

    def test_profile_without_declaration_returns_none(self):
        self.assertIsNone(evidence_check.read_in_force_profile(
            self.write_profile("`skill-repository-profile 1.0.0`\n")
        ))

    def test_valid_profile_returns_all_binding_values(self):
        self.assertEqual(
            evidence_check.read_in_force_profile(self.write_profile()),
            {
                "name": "skill-repository-profile",
                "version": "1.0.0",
                "since": "2026-08-03",
                "contract_version": "1.0.0",
            },
        )

    def test_conflicting_in_force_declarations_break_check(self):
        path = self.write_profile(
            PROFILE_TEXT
            + "`in-force: skill-repository-profile 1.0.1 since 2026-08-04`\n"
        )
        with self.assertRaises(evidence_check.CheckBroken):
            evidence_check.read_in_force_profile(path)

    def test_identity_version_mismatch_breaks_check(self):
        path = self.write_profile(PROFILE_TEXT.replace(
            "skill-repository-profile 1.0.0`\n\nConforms",
            "skill-repository-profile 1.0.1`\n\nConforms",
        ))
        with self.assertRaises(evidence_check.CheckBroken):
            evidence_check.read_in_force_profile(path)

    def test_profile_path_that_is_a_directory_breaks_check(self):
        path = os.path.join(self.root, "profile-as-dir.md")
        os.makedirs(path)
        with self.assertRaises(evidence_check.CheckBroken):
            evidence_check.read_in_force_profile(path)

    def test_dangling_symlink_profile_path_breaks_check(self):
        path = os.path.join(self.root, "dangling-profile.md")
        os.symlink(os.path.join(self.root, "does-not-exist.md"), path)
        with self.assertRaises(evidence_check.CheckBroken):
            evidence_check.read_in_force_profile(path)


class TestBrokenCheckIsDistinguishedFromNegativeJudgment(EvidenceCheckHarness):
    def test_unreadable_contract_file_breaks_the_check(self):
        with self.assertRaises(evidence_check.CheckBroken):
            self.run_check(contract=os.path.join(self.root, "absent.md"))

    def test_contract_without_version_declaration_breaks_the_check(self):
        path = os.path.join(self.root, "versionless.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# Contract with no identity\n")
        with self.assertRaises(evidence_check.CheckBroken):
            self.run_check(contract=path)

    def test_conflicting_version_declarations_break_the_check(self):
        path = os.path.join(self.root, "conflicted.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("`quality-gate-contract 1.0.0` and `quality-gate-contract 1.1.0`\n")
        with self.assertRaises(evidence_check.CheckBroken):
            self.run_check(contract=path)

    def test_malformed_target_sha_argument_breaks_the_check(self):
        write_record(self.evidence_dir, "machine_verified")
        write_record(self.evidence_dir, "semantic_reviewed")
        with self.assertRaises(evidence_check.CheckBroken):
            self.run_check(target_sha="HEAD")

    def test_evidence_dir_path_that_is_a_file_breaks_the_check(self):
        file_path = os.path.join(self.root, "evidence-as-file")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("not a directory")
        with self.assertRaises(evidence_check.CheckBroken):
            self.run_check(evidence_dir=file_path)

    def test_cli_maps_file_evidence_dir_to_exit_2(self):
        file_path = os.path.join(self.root, "evidence-as-file")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("not a directory")
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence_check.py")
        proc = subprocess.run(
            ["python3", script, "--repo-root", self.root,
             "--evidence-dir", file_path,
             "--target-sha", SHA_A,
             "--contract", self.contract_path],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("check broken", proc.stderr)

    def test_cli_maps_broken_check_to_exit_2(self):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence_check.py")
        proc = subprocess.run(
            ["python3", script, "--repo-root", self.root,
             "--contract", os.path.join(self.root, "absent.md")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("check broken", proc.stderr)


class TestDefaultTargetResolution(EvidenceCheckHarness):
    def test_default_target_sha_is_repository_head(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-q", "--allow-empty", "-m", "seed"],
                       cwd=self.root, check=True, env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"})
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root,
                              capture_output=True, text=True, check=True).stdout.strip()
        write_record(self.evidence_dir, "machine_verified", target_sha=head)
        write_record(self.evidence_dir, "semantic_reviewed", target_sha=head)
        rc = evidence_check.run(["--repo-root", self.root,
                                 "--evidence-dir", self.evidence_dir,
                                 "--contract", self.contract_path])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
