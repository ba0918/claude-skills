import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from workspace_isolation import (  # noqa: E402
    WorkspaceIsolationError,
    identify_workspace,
    resolve_isolation,
)


class WorkspaceIsolationTest(unittest.TestCase):
    def repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "main"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        (root / "tracked").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "tracked"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
        return root

    def test_policy_resolution_precedence_and_missing_default(self):
        root = self.repo()
        self.assertEqual("inplace", resolve_isolation(root))
        policy = root / ".agents/workspace.yml"
        policy.parent.mkdir()
        policy.write_text("isolation: worktree\n", encoding="utf-8")
        self.assertEqual("worktree", resolve_isolation(root))
        self.assertEqual("inplace", resolve_isolation(root, override="inplace"))
        self.assertEqual("worktree", resolve_isolation(root))

    def test_invalid_policy_and_override_fail_closed(self):
        root = self.repo()
        policy = root / ".agents/workspace.yml"
        policy.parent.mkdir()
        for text in ("isolation: other\n", "isolation: worktree\nextra: x\n", "bad yaml\n"):
            policy.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(WorkspaceIsolationError):
                resolve_isolation(root)
        with self.assertRaises(WorkspaceIsolationError):
            resolve_isolation(root, override="other")

    def test_dangling_policy_symlink_fails_closed(self):
        root = self.repo()
        policy = root / ".agents/workspace.yml"
        policy.parent.mkdir()
        policy.symlink_to(root / "missing-policy")
        with self.assertRaisesRegex(WorkspaceIsolationError, "regular file"):
            resolve_isolation(root)

    def test_linked_worktree_identity_comes_from_git_metadata(self):
        main = self.repo()
        linked = main.parent / "linked"
        subprocess.run(["git", "worktree", "add", "-q", str(linked)], cwd=main, check=True)
        identity = identify_workspace(linked)
        self.assertTrue(identity.is_linked_worktree)
        self.assertFalse(identity.is_submodule)
        self.assertEqual(main.resolve(), identity.main_tree_path)
        self.assertEqual(linked.resolve(), identity.worktree_path)
        self.assertTrue(identity.worktree_id)
        self.assertEqual(identity.worktree_id, identify_workspace(linked).worktree_id)

    def test_main_checkout_is_not_a_linked_worktree(self):
        main = self.repo()
        identity = identify_workspace(main)
        self.assertFalse(identity.is_linked_worktree)
        self.assertEqual(main.resolve(), identity.main_tree_path)

    def test_submodule_is_explicitly_excluded(self):
        main = self.repo()
        subrepo = self.repo()
        subprocess.run(
            ["git", "-c", "protocol.file.allow=always", "submodule", "add", "-q",
             str(subrepo), "vendor/sub"],
            cwd=main, check=True,
        )
        identity = identify_workspace(main / "vendor/sub")
        self.assertTrue(identity.is_submodule)
        with self.assertRaisesRegex(WorkspaceIsolationError, "submodule"):
            identify_workspace(main / "vendor/sub", require_linked=True)


if __name__ == "__main__":
    unittest.main()
