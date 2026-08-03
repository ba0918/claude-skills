"""release_tool.py のユニットテスト。

実行: python3 -m unittest discover scripts
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)
RELEASE_TOOL = os.path.join(SCRIPTS_DIR, "release_tool.py")
EVIDENCE_CHECK = os.path.join(
    REPO_ROOT, "skills", "shared", "scripts", "evidence_check.py"
)
REAL_CONTRACT = os.path.join(
    REPO_ROOT, "skills", "shared", "references", "quality-gate-contract.md"
)
MANIFEST_PATHS = (
    os.path.join(".claude-plugin", "plugin.json"),
    os.path.join(".claude-plugin", "marketplace.json"),
    os.path.join(".codex-plugin", "plugin.json"),
    "package.json",
)


class ReleaseToolTest(unittest.TestCase):
    """最小 fixture リポジトリに対する release 操作を検証する。"""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        self._write_fixture()

    def tearDown(self):
        self.tempdir.cleanup()

    def _write(self, relpath, text):
        path = os.path.join(self.root, relpath)
        os.makedirs(os.path.dirname(path) or self.root, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def _write_json(self, relpath, value):
        self._write(relpath, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def _write_fixture(self):
        self._write(
            "CHANGELOG.md",
            "# Changelog\n\n説明。\n\n## Unreleased\n\n"
            "### Added: fixture\n\n- detail\n\n## 1.72.0\n\n- old\n",
        )
        self._write_json(
            os.path.join(".claude-plugin", "plugin.json"),
            {"name": "fixture", "version": "1.72.0"},
        )
        self._write_json(
            os.path.join(".claude-plugin", "marketplace.json"),
            {
                "plugins": [
                    {"name": "fixture-a", "version": "1.72.0"},
                    {"name": "fixture-b", "version": "1.72.0"},
                ]
            },
        )
        self._write_json(
            os.path.join(".codex-plugin", "plugin.json"),
            {"name": "fixture", "version": "1.72.0"},
        )
        self._write_json("package.json", {"name": "fixture", "version": "1.72.0"})
        self._write(
            os.path.join(
                "skills", "shared", "references", "quality-gate-contract.md"
            ),
            "# Contract\n\nPublished: `quality-gate-contract 1.0.0`.\n",
        )

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, RELEASE_TOOL, *args, "--repo-root", self.root],
            capture_output=True,
            text=True,
        )

    def _snapshot_release_files(self):
        paths = ("CHANGELOG.md", *MANIFEST_PATHS)
        snapshot = {}
        for path in paths:
            with open(os.path.join(self.root, path), encoding="utf-8") as handle:
                snapshot[path] = handle.read()
        return snapshot

    def test_sync_updates_changelog_and_all_manifests(self):
        """正常系では見出しと全 version を一括更新する。"""
        proc = self._run("sync", "--version", "1.73.0")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout),
            {"changed": True, "previous_version": "1.72.0", "version": "1.73.0"},
        )
        with open(os.path.join(self.root, "CHANGELOG.md"), encoding="utf-8") as handle:
            changelog = handle.read()
        self.assertIn("## 1.73.0", changelog)
        self.assertIn("## 1.73.0\n\n### Added: fixture", changelog)
        self.assertNotIn("## Unreleased", changelog)
        for relpath in MANIFEST_PATHS:
            with open(os.path.join(self.root, relpath), encoding="utf-8") as handle:
                raw = handle.read()
            document = json.loads(raw)
            self.assertEqual(
                raw, json.dumps(document, ensure_ascii=False, indent=2) + "\n"
            )
            if relpath.endswith("marketplace.json"):
                self.assertEqual(
                    [plugin["version"] for plugin in document["plugins"]],
                    ["1.73.0", "1.73.0"],
                )
            else:
                self.assertEqual(document["version"], "1.73.0")

    def test_sync_is_idempotent_without_rewriting_files(self):
        """同期済み状態では changed=false を返し内容を変更しない。"""
        first = self._run("sync", "--version", "1.73.0")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_release_files()

        second = self._run("sync", "--version", "1.73.0")

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(
            json.loads(second.stdout),
            {"changed": False, "previous_version": "1.73.0", "version": "1.73.0"},
        )
        self.assertEqual(self._snapshot_release_files(), before)

    def test_sync_rejects_version_regression(self):
        """現行 version 以下への更新を拒否する。"""
        proc = self._run("sync", "--version", "1.71.0")

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("greater than current version", proc.stderr)

    def test_sync_rejects_missing_unreleased_heading(self):
        """非冪等状態で Unreleased 見出しが無ければ拒否する。"""
        self._write("CHANGELOG.md", "# Changelog\n\n## 1.72.0\n\n- old\n")

        proc = self._run("sync", "--version", "1.73.0")

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("## Unreleased", proc.stderr)

    def test_sync_rejects_manifest_version_drift(self):
        """manifest の現行 version がドリフトしたままなら拒否する。"""
        self._write_json(
            os.path.join(".codex-plugin", "plugin.json"),
            {"name": "fixture", "version": "1.71.0"},
        )

        proc = self._run("sync", "--version", "1.73.0")

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("manifest version drift", proc.stderr)

    def test_evidence_records_are_publishable_by_real_checker(self):
        """生成した 2 証跡を実物の evidence_check.py が publishable と判定する。"""
        target_sha = "a" * 40
        evidence_dir = os.path.join(self.root, "evidence")
        proc = self._run(
            "evidence",
            "--version", "1.73.0",
            "--target-sha", target_sha,
            "--actor", "release-operator",
            "--run-url", "https://example.test/runs/123",
            "--semantic-attested", "true",
            "--evidence-dir", evidence_dir,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(len(result["files"]), 2)
        checker = subprocess.run(
            [
                sys.executable,
                EVIDENCE_CHECK,
                "--repo-root", self.root,
                "--evidence-dir", evidence_dir,
                "--target-sha", target_sha,
                "--contract", REAL_CONTRACT,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(checker.returncode, 0, checker.stdout + checker.stderr)
        self.assertIn("publishable: yes", checker.stdout)

    def test_evidence_rejects_false_attestation_without_writing(self):
        """semantic attestation が false なら record を作らず fail-closed にする。"""
        evidence_dir = os.path.join(self.root, "evidence")
        proc = self._run(
            "evidence",
            "--version", "1.73.0",
            "--target-sha", "a" * 40,
            "--actor", "release-operator",
            "--run-url", "https://example.test/runs/123",
            "--semantic-attested", "false",
            "--evidence-dir", evidence_dir,
        )

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("semantic-attested must be true", proc.stderr)
        self.assertFalse(os.path.exists(evidence_dir))

    def test_notes_extracts_only_requested_version_section(self):
        """notes は指定版の節だけを次の version 見出し手前まで抽出する。"""
        synced = self._run("sync", "--version", "1.73.0")
        self.assertEqual(synced.returncode, 0, synced.stderr)

        proc = self._run("notes", "--version", "1.73.0")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("## 1.73.0", proc.stdout)
        self.assertIn("### Added: fixture", proc.stdout)
        self.assertNotIn("## 1.72.0", proc.stdout)


if __name__ == "__main__":
    unittest.main()
