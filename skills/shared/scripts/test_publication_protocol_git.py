#!/usr/bin/env python3
"""publication-protocol.md の git 機構を実リポジトリで実行検証する回帰テスト。

プロトコル本文は自然言語であり、test_step4_skill_integration.py の文言・順序
アサーションだけでは「コマンド列が実際に不変条件を満たすか」を検証できない。
ここでは本文が規定するコマンド列そのものを使い捨て git リポジトリに対して実行し、
機械的な不変条件を実測で固定する:

- happy path: prospective merge は main を動かさず、CAS → sync → promotion の後に
  ref・checkout・evidence singleton の三者が新 main に揃う
- CAS 競合: main が動いていたら update-ref が拒否し、main と公開済み evidence と
  staging のすべてが無傷で残る
- commit point 後の冪等修復: CAS と reset の間で停止しても、reset の再実行
  （複数回でも安全）で checkout が追いつく
- staging 隔離: prospective evidence は promotion まで default evidence dir に
  一切触れない
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


def git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=check,
    )


class PublicationProtocolGitTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pubproto-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.main = self.root / "main"
        self.main.mkdir()
        git(self.main, "init", "-q", "-b", "main")
        git(self.main, "config", "user.email", "test@example.com")
        git(self.main, "config", "user.name", "test")
        (self.main / ".gitignore").write_text(".agents/\n")
        (self.main / "a.txt").write_text("base\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "base")
        git(self.main, "branch", "satellite")
        sat = self.root / "sat"
        git(self.main, "worktree", "add", "-q", str(sat), "satellite")
        (sat / "b.txt").write_text("feature\n")
        git(sat, "add", ".")
        git(sat, "commit", "-qm", "feature")
        self.default_dir = self.main / ".agents/artifacts/reviews/evidence"

    def prospective_merge(self):
        """Step 1 as written: detached temp worktree + merge --no-ff."""
        expected = git(self.main, "rev-parse", "main").stdout.strip()
        tmp = self.root / "tmp-merge"
        git(self.main, "worktree", "add", "--detach", "-q", str(tmp), expected)
        git(tmp, "merge", "--no-ff", "-q", "-m", "merge satellite", "satellite")
        post = git(tmp, "rev-parse", "HEAD").stdout.strip()
        return expected, post, tmp

    def stage_evidence(self, post, states=("machine_verified", "semantic_reviewed")):
        """Step 2 as written: run-scoped staging keyed by the prospective SHA."""
        staging = self.main / f".agents/artifacts/reviews/evidence-staging/{post}"
        staging.mkdir(parents=True)
        for state in states:
            (staging / f"{state}.json").write_text(json.dumps({"target_sha": post}))
        return staging

    def publish_old_evidence(self, sha):
        self.default_dir.mkdir(parents=True)
        (self.default_dir / "machine_verified.json").write_text(
            json.dumps({"target_sha": sha})
        )

    def read_published_sha(self):
        return json.loads(
            (self.default_dir / "machine_verified.json").read_text()
        )["target_sha"]

    def test_happy_path_advances_syncs_and_promotes_after_cas(self):
        expected, post, _ = self.prospective_merge()
        # Step 1 must not advance main
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), expected)
        self.publish_old_evidence(expected)
        staging = self.stage_evidence(post)
        # staging isolation: the singleton still describes the old main
        self.assertEqual(self.read_published_sha(), expected)
        # Exit 0: clean check → CAS → sync → promotion
        self.assertEqual(git(self.main, "status", "--porcelain").stdout, "")
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        for state in ("machine_verified", "semantic_reviewed"):
            os.replace(staging / f"{state}.json", self.default_dir / f"{state}.json")
        staging.rmdir()
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), post)
        self.assertTrue((self.main / "b.txt").exists())
        self.assertEqual(self.read_published_sha(), post)

    def test_cas_conflict_refuses_and_preserves_main_evidence_and_staging(self):
        expected, post, _ = self.prospective_merge()
        self.publish_old_evidence(expected)
        staging = self.stage_evidence(post, states=("machine_verified",))
        # main moves concurrently before the CAS
        (self.main / "c.txt").write_text("concurrent\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "concurrent")
        moved = git(self.main, "rev-parse", "main").stdout.strip()
        result = git(
            self.main, "update-ref", "refs/heads/main", post, expected, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), moved)
        self.assertEqual(self.read_published_sha(), expected)
        self.assertTrue((staging / "machine_verified.json").exists())

    def test_completion_is_idempotent_after_crash_between_cas_and_sync(self):
        expected, post, _ = self.prospective_merge()
        self.assertEqual(git(self.main, "status", "--porcelain").stdout, "")
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        # crash window: ref advanced, checkout still at the old commit
        self.assertFalse((self.main / "b.txt").exists())
        # repair-forward: re-running the prescribed sync converges, twice is safe
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        self.assertTrue((self.main / "b.txt").exists())
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), post)


if __name__ == "__main__":
    unittest.main()
