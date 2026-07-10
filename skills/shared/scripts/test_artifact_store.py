import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from artifact_store import (  # noqa: E402
    ArtifactStoreError,
    finalize_migration,
    initialize,
    inspect,
    load_policy,
    migration_inventory,
    parse_policy,
    require_writable,
    stage_migration,
)


class ArtifactStoreTest(unittest.TestCase):
    def repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".gitignore").write_text("/.agents/artifacts/\n", encoding="utf-8")
        return root

    def write_policy(self, repo, **changes):
        policy = {
            "schema_version": 1,
            "root": ".agents/artifacts",
            "visibility": "local",
            "worktree_scope": "worktree",
        }
        policy.update(changes)
        path = repo / ".agents/artifacts.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{k}: {v}\n" for k, v in policy.items()), encoding="utf-8")

    def test_missing_policy_uses_safe_local_default(self):
        root = self.repo()
        policy, explicit = load_policy(root)
        self.assertFalse(explicit)
        self.assertEqual("local", policy["visibility"])
        self.assertEqual(".agents/artifacts", policy["root"])

    def test_unknown_schema_and_key_fail_closed(self):
        root = self.repo()
        self.write_policy(root, schema_version=2)
        with self.assertRaisesRegex(ArtifactStoreError, "schema_version"):
            load_policy(root)
        (root / ".agents/artifacts.yml").write_text(
            "schema_version: 1\nroot: .agents/artifacts\nvisibility: local\n"
            "worktree_scope: worktree\nsecret: value\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ArtifactStoreError, "unknown policy keys"):
            load_policy(root)

    def test_noncanonical_and_absolute_roots_are_rejected(self):
        root = self.repo()
        self.write_policy(root, root="../outside")
        with self.assertRaisesRegex(ArtifactStoreError, "root"):
            load_policy(root)
        self.write_policy(root, root="/tmp/outside")
        with self.assertRaisesRegex(ArtifactStoreError, "root"):
            load_policy(root)

    def test_legacy_store_blocks_writes(self):
        root = self.repo()
        (root / "docs/plans").mkdir(parents=True)
        (root / "docs/plans/a.md").write_text("plan", encoding="utf-8")
        result = inspect(root)
        self.assertEqual("legacy", result["state"])
        with self.assertRaisesRegex(ArtifactStoreError, "migration"):
            require_writable(root)

    def test_split_brain_is_reported(self):
        root = self.repo()
        self.write_policy(root)
        (root / "docs/issues").mkdir(parents=True)
        (root / "docs/issues/a.md").write_text("issue", encoding="utf-8")
        (root / ".agents/artifacts/issues").mkdir(parents=True)
        (root / ".agents/artifacts/issues/b.md").write_text("issue", encoding="utf-8")
        result = inspect(root)
        self.assertEqual("split-brain", result["state"])
        self.assertFalse(result["writable"])

    def test_local_store_must_be_ignored_and_untracked(self):
        root = self.repo()
        self.write_policy(root)
        self.assertEqual([], inspect(root)["errors"])
        (root / ".gitignore").write_text("", encoding="utf-8")
        self.assertIn("local artifact store is not ignored by Git", inspect(root)["errors"])

    def test_public_store_must_not_be_ignored(self):
        root = self.repo()
        self.write_policy(root, visibility="public")
        self.assertIn("public artifact store is ignored by Git", inspect(root)["errors"])
        (root / ".gitignore").write_text("", encoding="utf-8")
        self.assertEqual([], inspect(root)["errors"])

    def test_policy_must_not_be_ignored(self):
        root = self.repo()
        self.write_policy(root)
        (root / ".gitignore").write_text("/.agents/\n", encoding="utf-8")
        self.assertIn("artifact policy is ignored by Git", inspect(root)["errors"])

    def test_symlink_root_is_rejected(self):
        root = self.repo()
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: outside.rmdir())
        (root / ".agents").mkdir()
        os.symlink(outside, root / ".agents/artifacts")
        with self.assertRaisesRegex(ArtifactStoreError, "symlink"):
            inspect(root, validate_git=False)

    def test_init_is_idempotent_and_refuses_legacy(self):
        root = self.repo()
        first = initialize(root)
        second = initialize(root)
        self.assertEqual(first["policy"], second["policy"])
        self.assertTrue((root / ".agents/artifacts/plans").is_dir())

        legacy = self.repo()
        (legacy / "docs/ideas").mkdir(parents=True)
        (legacy / "docs/ideas/a.md").write_text("idea", encoding="utf-8")
        with self.assertRaisesRegex(ArtifactStoreError, "migration"):
            initialize(legacy)

    def test_migration_requires_decisions_and_is_two_phase(self):
        root = self.repo()
        (root / "docs/plans").mkdir(parents=True)
        source = root / "docs/plans/a.md"
        source.write_text("plan", encoding="utf-8")
        inventory = migration_inventory(root)
        self.assertEqual("review", inventory["entries"][0]["action"])
        decisions = root / "decisions.json"
        decisions.write_text(__import__("json").dumps(inventory), encoding="utf-8")
        with self.assertRaisesRegex(ArtifactStoreError, "unresolved"):
            stage_migration(root, decisions)

        inventory["entries"][0]["action"] = "move"
        decisions.write_text(__import__("json").dumps(inventory), encoding="utf-8")
        staged = stage_migration(root, decisions)
        self.assertFalse(staged["source_removed"])
        self.assertTrue(source.exists())
        self.assertTrue((root / ".agents/artifacts/plans/a.md").exists())
        with self.assertRaisesRegex(ArtifactStoreError, "confirmations"):
            finalize_migration(root)
        finalized = finalize_migration(
            root, confirm_remove_source=True, confirm_public_history=True,
        )
        self.assertTrue(finalized["verified"])
        self.assertFalse(source.exists())


if __name__ == "__main__":
    unittest.main()
